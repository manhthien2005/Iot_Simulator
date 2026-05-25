"""FallService — extracted from SimulatorRuntime.

Owns the full fall-detection flow: AI invocation, pre-trigger evidence,
motion window capturing, event injection, fall state querying, and
countdown auto-resolution.

Thread-safety: methods that touch shared state either receive the caller's
lock context (``_locked`` suffix) or acquire ``self._lock`` themselves.
The lock instance is the same ``threading.RLock`` shared with
``SimulatorRuntime`` so re-entrant callers that already hold it are safe.
"""
from __future__ import annotations

import collections
import logging
import math
from datetime import datetime, timezone
from threading import RLock
from typing import TYPE_CHECKING, Any, Callable

from api_server.fall_policy import (
    FallVariantPolicy as _FallVariantPolicy,
    FALL_VARIANT_POLICIES as _FALL_VARIANT_POLICIES,
    FALL_VARIANT_DEFAULT_POLICY as _FALL_VARIANT_DEFAULT_POLICY,
    FALL_VARIANT_TO_PERSONA as _FALL_VARIANT_TO_PERSONA,
)
from api_server.schemas import (
    AIPrediction,
    CountdownPolicy,
    FallEventEntry,
    FallState,
    FallStateValue,
    MotionLatest,
    MotionWindowRef,
    PreTriggerEvidence,
)
from api_server.utils import _utc_now_iso, _safe_float
from simulator_core.fall_ai_client import (
    FALL_VARIANT_CONTEXT,
    FALL_VARIANT_DEFAULT_CONTEXT,
    motion_window_to_samples as _motion_window_to_samples,
)

if TYPE_CHECKING:
    from pre_model_trigger import FallPreTrigger, SystemSettingsProvider
    from pre_model_trigger.mobile_telemetry_client import MobileTelemetryClient
    from api_server.models import DeviceRecord, EventRecord, SessionRecord

from api_server.imu_utils import (
    _BAND_TO_RISK_BAND,
    _BAND_TO_LABEL,
    _BAND_PHRASE_VI,
    _build_synthetic_fall_explanation,
    _normalise_imu_window_response,
    _coerce_float_list,
)

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------

class FallService:
    """Manages the full fall detection flow for SimulatorRuntime.

    All mutable dicts (``devices``, ``sessions``, ``event_history``,
    ``fall_predictions``, etc.) are passed **by reference** so mutations
    made here are immediately visible to the runtime and vice-versa.
    """

    _SOS_COUNTDOWN_SECONDS = 30

    def __init__(
        self,
        *,
        devices: "dict[str, DeviceRecord]",
        sessions: "dict[str, SessionRecord]",
        device_scenarios: dict[str, str],
        event_history: "collections.deque[EventRecord]",
        lock: RLock,
        fall_predictions: dict[str, AIPrediction],
        fall_motion_refs: dict[str, MotionWindowRef],
        fall_countdown_policies: dict[str, CountdownPolicy],
        fall_pre_trigger_results: dict[str, PreTriggerEvidence],
        health_backend_url: str,
        mobile_telemetry_client: "MobileTelemetryClient",
        fall_pre_trigger: "FallPreTrigger | None",
        settings_provider: "SystemSettingsProvider | None",
        http_sender_fn: Callable,
        publish_device_log_fn: Callable,
        record_event_fn: Callable,
        run_session_side_effects_fn: Callable,
        run_session_side_effects_async_fn: Callable,
        publish_flow_event_fn: Callable,
        tick_session_locked_fn: Callable,
        require_session_fn: Callable,
        internal_secret: str | None,
    ) -> None:
        self.devices = devices
        self.sessions = sessions
        self.device_scenarios = device_scenarios
        self.event_history = event_history
        self._lock = lock
        self._fall_predictions = fall_predictions
        self._fall_motion_refs = fall_motion_refs
        self._fall_countdown_policies = fall_countdown_policies
        self._fall_pre_trigger_results = fall_pre_trigger_results
        self._health_backend_url = health_backend_url
        self._mobile_telemetry_client = mobile_telemetry_client
        self._fall_pre_trigger = fall_pre_trigger
        self._settings_provider = settings_provider
        self._http_sender = http_sender_fn
        self._publish_device_log = publish_device_log_fn
        self._record_event = record_event_fn
        self._run_session_side_effects = run_session_side_effects_fn
        self._run_session_side_effects_async = run_session_side_effects_async_fn
        self._publish_flow_event = publish_flow_event_fn
        self._tick_session_locked = tick_session_locked_fn
        self._require_session = require_session_fn
        self._internal_secret = internal_secret

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _has_recent_fall_event_locked(
        self, device_id: str, *, seconds: float = 5.0
    ) -> bool:
        """Return True if a ``fall_detected`` event fired for this device recently.

        Used by the tick loop to dedupe its "fall via dataset annotation"
        recording against the canonical ``inject_event`` recording. The
        check walks ``event_history`` from newest to oldest and stops as
        soon as it finds an event older than ``seconds`` for the target
        device — bounded latency under the operating maxlen=2000 deque.
        """
        for event in reversed(self.event_history):
            if event.device_id != device_id:
                continue
            if event.event_type != "fall_detected":
                continue
            if self._iso_age_seconds(event.timestamp) <= seconds:
                return True
            return False
        return False

    @staticmethod
    def _resolve_fall_variant_policy(
        fe_variant: str | None,
    ) -> tuple[_FallVariantPolicy, str]:
        """Return ``(policy, persona_variant)`` for an operator-supplied variant.

        Falls back to ``confirmed`` policy + ``fall_1`` persona for any
        unknown variant string so legacy callers keep working.  The
        persona variant is what the PersonaEngine + signal generator key
        off for vitals/motion deltas; the FE-facing variant is what
        appears in events + recent_fall_events.
        """
        key = (fe_variant or "confirmed").strip().lower()
        policy = _FALL_VARIANT_POLICIES.get(key, _FALL_VARIANT_DEFAULT_POLICY)
        persona = _FALL_VARIANT_TO_PERSONA.get(key, "fall_1")
        return policy, persona

    def _call_fall_ai_locked(
        self,
        motion: dict[str, Any] | None,
        device_id: str,
        fe_variant: str,
    ) -> AIPrediction:
        """Post the most recent IMU window to the mobile BE for fall inference.

        ADR-019 Phase 7 S9: the simulator used to call the model-api
        directly via :class:`FallAIClient`. It now dispatches through
        :class:`MobileTelemetryClient` so the backend can persist the
        raw window (``imu_windows``), the fall event (``fall_events``),
        auto-trigger risk, and fan FCM out — same trust boundary as a
        production smartwatch -> phone -> BE -> model-api path.

        Returns an ``AIPrediction`` even on failure so the FE always has
        a deterministic shape: ``modelStatus`` distinguishes ``ok`` from
        ``offline`` from ``no_window`` from ``skipped`` (no bound DB
        device). No exception escapes.
        """
        predicted_at = _utc_now_iso()
        sample_count = 0
        if isinstance(motion, dict):
            # NOTE: motion arrays may be numpy ndarrays so `arr or []`
            # raises "truth value ambiguous".  Coerce via explicit None
            # checks + len() — same pattern as fall_ai_client._coerce.
            ax = motion.get("accel_x")
            ay = motion.get("accel_y")
            az = motion.get("accel_z")
            sample_count = min(
                len(ax) if ax is not None else 0,
                len(ay) if ay is not None else 0,
                len(az) if az is not None else 0,
            )
        if sample_count < 50:
            return AIPrediction(
                label="normal",
                probability=0.0,
                confidence=0.0,
                riskBand="normal",
                requiresAttention=False,
                highPriorityAlert=False,
                explanationSummary=(
                    f"Không đủ mẫu chuyển động để đánh giá (có {sample_count}, cần 50). "
                    "Hệ thống đang dùng pre-trigger fallback."
                ),
                topFeatures=[],
                predictedAt=predicted_at,
                modelStatus="no_window",
            )

        # Resolve the backend device PK — the BE rejects ``/imu-window``
        # without it because the persistence path needs a ``devices.id``
        # to attach the row to. Unbound simulator devices skip the call
        # entirely and surface ``modelStatus=skipped``.
        device = self.devices.get(device_id)
        bound_db_device_id = device.bound_db_device_id if device is not None else None
        if bound_db_device_id is None:
            return AIPrediction(
                label="normal",
                probability=0.0,
                confidence=0.0,
                riskBand="normal",
                requiresAttention=False,
                highPriorityAlert=False,
                explanationSummary=(
                    "Thiết bị mô phỏng chưa bind backend — bỏ qua dispatch IMU window."
                ),
                topFeatures=[],
                predictedAt=predicted_at,
                modelStatus="skipped",
                failureReason="device_unbound",
            )

        fall_context = FALL_VARIANT_CONTEXT.get(fe_variant, FALL_VARIANT_DEFAULT_CONTEXT)
        samples = _motion_window_to_samples(motion, fall_context=fall_context)
        if len(samples) < 50:
            return AIPrediction(
                label="normal",
                probability=0.0,
                confidence=0.0,
                riskBand="normal",
                requiresAttention=False,
                highPriorityAlert=False,
                explanationSummary=(
                    "Không đủ mẫu sau khi chuyển đổi window — pre-trigger fallback."
                ),
                topFeatures=[],
                predictedAt=predicted_at,
                modelStatus="no_window",
                failureReason="insufficient_samples",
            )

        logger.info(
            "submit_imu_window → device=%s db_device=%s samples=%d url=%s",
            device_id,
            bound_db_device_id,
            len(samples),
            getattr(self._mobile_telemetry_client, "_base_url", "?"),
        )
        try:
            response = self._mobile_telemetry_client.submit_imu_window(
                device_id=device_id,
                db_device_id=int(bound_db_device_id),
                window_data=samples,
            )
        except Exception:  # pragma: no cover — defensive
            logger.warning(
                "Mobile telemetry IMU window submit raised unexpectedly",
                exc_info=True,
            )
            response = None
        logger.info(
            "submit_imu_window ← response=%s",
            None if response is None else {k: v for k, v in response.items() if k in ("status", "fall_event_id", "fall_probability")},
        )

        return _normalise_imu_window_response(
            response,
            predicted_at=predicted_at,
        )

    def _build_motion_window_ref(
        self,
        payload: dict[str, Any] | None,
        fe_variant: str,
    ) -> MotionWindowRef | None:
        """Capture a ref to the motion window the AI was called on."""
        if not payload:
            return None
        motion = payload.get("motion") or {}
        # NOTE: numpy arrays — see _call_fall_ai_locked for context.
        ax = motion.get("accel_x")
        ay = motion.get("accel_y")
        az = motion.get("accel_z")
        sample_count = min(
            len(ax) if ax is not None else 0,
            len(ay) if ay is not None else 0,
            len(az) if az is not None else 0,
        )
        if sample_count == 0:
            return None
        return MotionWindowRef(
            emittedAt=str(payload.get("emitted_at") or _utc_now_iso()),
            sampleCount=sample_count,
            sampleRate=_safe_float(motion.get("sample_rate"), None),
            fallVariant=fe_variant or None,
        )

    def _compute_pre_trigger_evidence(
        self,
        motion: dict[str, Any] | None,
    ) -> PreTriggerEvidence | None:
        """Run pre-trigger evaluation against the inject-time motion window.

        Phase 2 wiring — exposes the BE's hard/soft trigger reasoning
        to the FE Fall Lab pipeline strip (Section B stage 2).  We
        adapt the column-array motion shape from MotionGenerator into
        the per-sample dict that :class:`FallPreTrigger` consumes by
        reading the most recent sample's accel/gyro values, plus the
        precomputed peak / posture / low-motion fields the persona
        engine attaches to the window metadata.

        Returns ``None`` only when the runtime has no FallPreTrigger
        configured (pre-trigger disabled at startup).  In that case the
        FE strip falls back to its FE-derived peak-vs-threshold view.
        """
        if not motion:
            return None
        pre_trigger = self._fall_pre_trigger
        if pre_trigger is None:
            return None

        # Build the per-sample dict the evaluator expects.  Use the LAST
        # sample (impact tail) for accel/gyro instantaneous values and
        # forward the window-level peak/posture/low-motion metadata
        # MotionGenerator already attaches.
        # NOTE: motion arrays are numpy ndarrays from MotionGenerator's
        # parquet pipeline so we MUST avoid `arr or []` and `not arr`
        # which both raise `ValueError: truth value of an array is
        # ambiguous`.  Mirrors the same pattern in
        # ``simulator_core.fall_ai_client.motion_window_to_samples``.
        def _coerce(value: Any) -> list[Any]:
            if value is None:
                return []
            try:
                return list(value)
            except TypeError:
                return []

        ax_arr = _coerce(motion.get("accel_x"))
        ay_arr = _coerce(motion.get("accel_y"))
        az_arr = _coerce(motion.get("accel_z"))
        gx_arr = _coerce(motion.get("gyro_x"))
        gy_arr = _coerce(motion.get("gyro_y"))
        gz_arr = _coerce(motion.get("gyro_z"))

        def _last(arr: Any) -> float | None:
            try:
                length = len(arr)
            except TypeError:
                return None
            if length == 0:
                return None
            try:
                return float(arr[length - 1])
            except (TypeError, ValueError):
                return None

        # Phase 3 fix — derive window-level peaks ourselves so the
        # evaluator does not fall back to the LAST-sample magnitude.
        # Accel raw values are in m/s²; convert to g to match the
        # 3.0g / 2.5g thresholds on `FallPreTrigger`.  Gyro is already
        # in dps so passes through unchanged.
        #
        # Without this fix, when the source motion window does not carry
        # an `accel_mag_peak_g` metadata key, the evaluator computed
        # sqrt(x²+y²+z²) of the LAST sample (~22 m/s² typical) and
        # compared to 3.0g — falsely tripping the HARD trigger for every
        # variant.
        _G_TO_MS2 = 9.80665

        def _peak_g_from_arrays(ax: list[Any], ay: list[Any], az: list[Any]) -> float | None:
            n = min(len(ax), len(ay), len(az))
            if n == 0:
                return None
            peak_ms2 = 0.0
            for i in range(n):
                try:
                    x = float(ax[i]); y = float(ay[i]); z = float(az[i])
                except (TypeError, ValueError):
                    continue
                mag = math.sqrt(x * x + y * y + z * z)
                if mag > peak_ms2:
                    peak_ms2 = mag
            return peak_ms2 / _G_TO_MS2 if peak_ms2 > 0 else 0.0

        def _peak_dps_from_arrays(gx: list[Any], gy: list[Any], gz: list[Any]) -> float | None:
            n = min(len(gx), len(gy), len(gz))
            if n == 0:
                return None
            peak = 0.0
            for i in range(n):
                try:
                    x = float(gx[i]); y = float(gy[i]); z = float(gz[i])
                except (TypeError, ValueError):
                    continue
                mag = math.sqrt(x * x + y * y + z * z)
                if mag > peak:
                    peak = mag
            return peak

        # Prefer metadata when present (some parquet windows already carry
        # the correctly-scaled peak), else compute from arrays.
        accel_peak_g = motion.get("accel_mag_peak_g")
        if accel_peak_g is None:
            accel_peak_g = _peak_g_from_arrays(ax_arr, ay_arr, az_arr)
        gyro_peak_dps = motion.get("gyro_mag_peak_dps")
        if gyro_peak_dps is None:
            gyro_peak_dps = _peak_dps_from_arrays(gx_arr, gy_arr, gz_arr)

        sample = {
            "accel": {
                "x": _last(ax_arr) or 0.0,
                "y": _last(ay_arr) or 0.0,
                "z": _last(az_arr) or 0.0,
            },
            "gyro": {
                "x": _last(gx_arr) or 0.0,
                "y": _last(gy_arr) or 0.0,
                "z": _last(gz_arr) or 0.0,
            },
            "accel_mag_peak_g": accel_peak_g,
            "gyro_mag_peak_dps": gyro_peak_dps,
            "posture_change_angle_deg": motion.get("posture_change_angle_deg"),
            "post_impact_low_motion_duration_s": motion.get(
                "post_impact_low_motion_duration_s"
            ),
        }
        evidence_dict = pre_trigger.evaluate_with_evidence(sample)
        return PreTriggerEvidence(**evidence_dict)

    def _override_severity_from_verdict(
        self,
        policy: _FallVariantPolicy,
        verdict: AIPrediction,
    ) -> str:
        """Decide alert severity from policy default + AI verdict band.

        AI "critical" always escalates; AI "normal" downgrades a
        ``warning`` policy default to "warning" still (don't suppress
        alerts entirely without operator decision); ``critical`` policy
        defaults stay critical regardless of AI band so the worst-case
        path (``fall_no_response``) is preserved.
        """
        if policy.default_severity == "critical":
            return "critical"
        if verdict.riskBand == "critical":
            return "critical"
        if verdict.riskBand == "warning":
            return "warning"
        return policy.default_severity

    @staticmethod
    def _latest_motion_payload_locked(
        record: "SessionRecord", device_id: str
    ) -> dict[str, Any] | None:
        """Return the most recent tick payload for `device_id`, if any."""
        for payload in reversed(record.last_tick_outputs):
            if payload.get("device_id") == device_id:
                return payload
        return None

    @staticmethod
    def _iso_age_seconds(iso_ts: str) -> float:
        """Seconds between now (UTC) and `iso_ts` — robust to ``Z`` suffix."""
        try:
            ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        return (datetime.now(timezone.utc) - ts).total_seconds()

    @staticmethod
    def _fall_state_locked(
        *,
        device_state: str,
        last_fall_event: "EventRecord | None",
        last_cancel_event: "EventRecord | None",
        countdown_remaining: int,
    ) -> FallStateValue:
        """Reduce runtime signals into the FE-friendly fall lifecycle.

        ``idle``           — no recent fall events.
        ``fall_detected``  — fall event recorded but FSM has cleared (e.g.
                             a brief or false-alarm variant that didn't
                             escalate).
        ``fall_countdown`` — FSM is in `fall_countdown` and the SOS
                             window has not elapsed.
        ``sos_active``     — FSM is in `sos_active` (operator did not
                             respond and the device escalated).
        ``fall_resolved``  — operator pressed "Tôi ổn" after a fall event.
        """
        if last_cancel_event is not None and (
            last_fall_event is None or last_cancel_event.timestamp >= last_fall_event.timestamp
        ):
            return "fall_resolved"
        if device_state == "sos_active":
            return "sos_active"
        if device_state == "fall_countdown" and countdown_remaining > 0:
            return "fall_countdown"
        if last_fall_event is not None:
            return "fall_detected"
        return "idle"

    # -----------------------------------------------------------------------
    # Public API (mirrored on SimulatorRuntime)
    # -----------------------------------------------------------------------

    def inject_event(self, device_id: str, event_type: str, variant: str | None) -> None:
        """Inject event into simulator. AI inference runs OUTSIDE the global lock.

        Architecture (fall_detected path):
        Phase 1 [lock]: simulator state changes, canonical event pre-record, tick
        Phase 2 [no lock]: HTTP AI inference (blocking I/O, can take 100ms-1s)
        Phase 3 [lock]: store AI verdict, update device state, build alert effects
        """
        from api_server.models import SessionSideEffects, PendingAlertCall
        effects = SessionSideEffects()
        # Data collected in Phase 1 for use in Phase 2/3
        _p2_device_id: str = device_id
        _p2_motion: dict | None = None
        _p2_variant: str = variant or ""
        _p2_canonical_event: "EventRecord | None" = None
        _p2_policy: _FallVariantPolicy | None = None
        _p2_need_ai = False
        _p2_payload: dict | None = None
        _p2_record_id: str | None = None
        _p2_persona_variant: str | None = None
        with self._lock:
            for record in self.sessions.values():
                if device_id not in record.device_ids:
                    continue

                # ---- Module FA — fall_detected ordering ------------------------
                # The tick loop has its own "if activity_state==fall: record"
                # branch (it's the canonical recorder for replay-mode falls
                # where activity arrives from the dataset).  To avoid
                # duplicating the event for operator-injected falls we have
                # to record the canonical event *before* ticking, so the
                # tick loop's `_has_recent_fall_event_locked` dedupe sees
                # it and skips.  AI verdict metadata is then merged into
                # that same event via in-place mutation after the tick +
                # AI call complete.
                #
                # For non-fall events the original pre-tick inject + post-
                # tick record order is preserved.
                policy: _FallVariantPolicy | None = None
                persona_variant: str | None = None
                canonical_fall_event: "EventRecord | None" = None

                if event_type == "fall_detected":
                    policy, persona_variant = self._resolve_fall_variant_policy(variant)
                    record.simulator.inject_event(device_id, event_type, persona_variant)
                    record.alert_received = True
                    # Pre-record with provisional severity (policy default).
                    # We mutate severity + metadata after AI verdict below.
                    self._record_event(
                        device_id=device_id,
                        event_type="fall_detected",
                        severity=policy.default_severity,
                        message="Injected event fall_detected",
                        metadata={
                            "variant": variant or "",
                            "persona_variant": persona_variant or "",
                            "source": "inject_event",
                        },
                    )
                    canonical_fall_event = self.event_history[-1]
                elif event_type == "sos_cancel":
                    # Module C: runtime-only event — PersonaEngine has no
                    # concept of it, so we handle the FSM transition here.
                    if device_id in self.devices and self.devices[device_id].state in {
                        "fall_countdown",
                        "sos_active",
                    }:
                        self.devices[device_id].state = "streaming"
                    for sim_device in record.simulator.devices:
                        if sim_device.device_id == device_id:
                            if sim_device.engine.state.activity_state == "fall":
                                sim_device.engine.transition_to("recovery")
                            break
                    # Drop any stale AI verdict + countdown policy now that
                    # the operator dismissed the SOS — keeps the FE clean.
                    self._fall_predictions.pop(device_id, None)
                    self._fall_motion_refs.pop(device_id, None)
                    self._fall_countdown_policies.pop(device_id, None)
                    self._fall_pre_trigger_results.pop(device_id, None)
                else:
                    record.simulator.inject_event(device_id, event_type, variant)

                if event_type == "device_offline" and device_id in self.devices:
                    self.devices[device_id].state = "offline"
                    self.devices[device_id].is_online = False
                if event_type == "device_online" and device_id in self.devices:
                    self.devices[device_id].state = "streaming"
                    self.devices[device_id].is_online = True

                # ---- Tick to generate motion (and vitals) for this event ----
                if record.status == "running":
                    effects.extend(self._tick_session_locked(record, force=True))

                # ---- Collect data for Phase 2 (AI call, outside lock) ----
                ai_verdict: AIPrediction | None = None
                motion_ref: MotionWindowRef | None = None
                pre_trigger_evidence: PreTriggerEvidence | None = None
                severity = "warning"
                if event_type == "fall_detected" and policy is not None:
                    _p2_payload = self._latest_motion_payload_locked(record, device_id)
                    _p2_motion = (_p2_payload or {}).get("motion") or {}
                    _p2_policy = policy
                    _p2_canonical_event = canonical_fall_event
                    _p2_need_ai = True
                    _p2_record_id = record.id
                    _p2_persona_variant = persona_variant
                    # Set device state immediately (before AI — keeps FE responsive)
                    if device_id in self.devices:
                        self.devices[device_id].state = policy.device_state_on_inject  # type: ignore[assignment]
                    self._fall_countdown_policies[device_id] = CountdownPolicy(
                        totalSec=int(policy.countdown_sec),
                        autoResolve=bool(policy.auto_resolve),
                        allowsCancel=bool(policy.allows_cancel),
                    )

                # ---- Non-fall event recording (single source of truth) ----
                if event_type != "fall_detected":
                    severity = "warning"
                    if event_type == "sos_cancel":
                        severity = "normal"
                    elif event_type == "device_offline":
                        severity = "offline"
                    elif event_type == "device_online":
                        severity = "normal"
                    self._record_event(
                        device_id=device_id,
                        event_type=event_type,
                        severity=severity,
                        message=(
                            "Operator cancelled SOS countdown"
                            if event_type == "sos_cancel"
                            else f"Injected event {event_type}"
                        ),
                        metadata={"variant": variant or ""},
                    )

                break
            else:
                raise KeyError(f"Device not found in active sessions: {device_id}")

        # ── Phase 2: AI inference (OUTSIDE lock) ─────────────────────────
        # HTTP call to mobile BE — can take 100ms-1s. Must NOT hold global lock.
        if _p2_need_ai and _p2_policy is not None:
            pre_trigger_evidence = self._compute_pre_trigger_evidence(_p2_motion)
            ai_verdict = self._call_fall_ai_locked(_p2_motion, _p2_device_id, _p2_variant)
            motion_ref = self._build_motion_window_ref(_p2_payload, _p2_variant)

            # ── Phase 3: Store results (re-acquire lock) ──────────────────
            with self._lock:
                if pre_trigger_evidence is not None:
                    self._fall_pre_trigger_results[_p2_device_id] = pre_trigger_evidence
                self._fall_predictions[_p2_device_id] = ai_verdict
                if motion_ref is not None:
                    self._fall_motion_refs[_p2_device_id] = motion_ref
                severity = self._override_severity_from_verdict(_p2_policy, ai_verdict)
                if _p2_canonical_event is not None:
                    _p2_canonical_event.severity = severity
                    _p2_canonical_event.metadata["ai_label"] = ai_verdict.label
                    _p2_canonical_event.metadata["ai_probability"] = f"{ai_verdict.probability:.4f}"
                    _p2_canonical_event.metadata["ai_band"] = ai_verdict.riskBand
                    _p2_canonical_event.metadata["ai_status"] = ai_verdict.modelStatus

            if _p2_record_id:
                self._publish_flow_event(_p2_record_id, {
                    "step": "imu_predict",
                    "device_id": _p2_device_id,
                    "status": "done" if ai_verdict.modelStatus == "ok" else "error",
                    "payload": {
                        "label": ai_verdict.label,
                        "confidence": round(ai_verdict.confidence, 3),
                        "model_status": ai_verdict.modelStatus,
                    },
                })

            # Build alert effects with AI verdict (outside lock — just list construction)
            should_push = _p2_policy.push_alert
            if ai_verdict.highPriorityAlert:
                should_push = True
            if should_push:
                ai_prob = float(ai_verdict.probability) if ai_verdict else 0.0
                confidence_value = max(ai_prob, float(_p2_policy.simulated_confidence))
                effects.pending_alerts.append(
                    PendingAlertCall(
                        sim_device_id=_p2_device_id,
                        event_type="fall_detected",
                        severity=severity,
                        metadata={
                            "variant": _p2_variant,
                            "persona_variant": _p2_persona_variant or "",
                            "source": "inject_event",
                            "timestamp": _utc_now_iso(),
                            "ai_label": ai_verdict.label,
                            "ai_probability": f"{ai_verdict.probability:.4f}",
                            "ai_band": ai_verdict.riskBand,
                            "confidence": f"{confidence_value:.4f}",
                            "simulated_confidence": f"{_p2_policy.simulated_confidence:.4f}",
                            **({"fall_event_id": str(ai_verdict.fallEventId)} if ai_verdict.fallEventId else {}),
                            **({"model_request_id": ai_verdict.modelRequestId} if ai_verdict.modelRequestId else {}),
                        },
                    )
                )

        # Use async (fire-and-forget) variant so inject_event returns
        # immediately after state mutation — HTTP publish/alerts run in
        # background threads without blocking the API response.
        self._run_session_side_effects_async(effects)

    def fall_state(self, session_id: str, device_id: str) -> FallState:
        """Operator-visible fall pipeline state derived from runtime truth.

        Sources:
          * `device.state` — canonical FSM (`fall_countdown` / `sos_active`).
          * Most recent `fall_detected` event in `event_history`.
          * `record.last_tick_outputs[i].state.{activity_state,fall_variant}`.
        """
        with self._lock:
            record = self._require_session(session_id)
            if device_id not in record.device_ids:
                raise KeyError(f"Device {device_id} not in session {session_id}")
            device = self.devices.get(device_id)
            tick_state = (
                (self._latest_motion_payload_locked(record, device_id) or {}).get("state") or {}
            )
            recent_fall_events = [
                event
                for event in reversed(self.event_history)
                if event.device_id == device_id
                and event.event_type in {"fall_detected", "sos_cancel", "fall_no_response"}
            ][:5]
            last_fall_event = next(
                (event for event in recent_fall_events if event.event_type == "fall_detected"),
                None,
            )
            last_cancel_event = next(
                (event for event in recent_fall_events if event.event_type == "sos_cancel"),
                None,
            )

            # Module FA: countdown total is now variant-aware.  Falls back
            # to the legacy 30s constant when no policy was cached (e.g.
            # legacy event injected before the runtime started caching).
            cached_policy = self._fall_countdown_policies.get(device_id)
            countdown_total = (
                cached_policy.totalSec if cached_policy else int(self._SOS_COUNTDOWN_SECONDS)
            )
            countdown_remaining = 0
            countdown_started_at: str | None = None
            sos_active = False
            if device is not None and device.state in {"fall_countdown", "sos_active"} and last_fall_event:
                countdown_started_at = last_fall_event.timestamp
                # If the operator already cancelled after this fall event,
                # the countdown is logically zero even if the FSM hasn't
                # advanced yet (it will on the next tick).
                cancelled_after_fall = (
                    last_cancel_event is not None
                    and last_cancel_event.timestamp >= last_fall_event.timestamp
                )
                if not cancelled_after_fall:
                    elapsed = self._iso_age_seconds(last_fall_event.timestamp)
                    countdown_remaining = max(
                        0, int(round(countdown_total - elapsed))
                    )
                    sos_active = device.state == "sos_active" or countdown_remaining > 0

            fall_state_value = self._fall_state_locked(
                device_state=(device.state if device else "streaming"),
                last_fall_event=last_fall_event,
                last_cancel_event=last_cancel_event,
                countdown_remaining=countdown_remaining,
            )

            return FallState(
                deviceId=device_id,
                sessionId=session_id,
                deviceState=(device.state if device else "streaming"),  # type: ignore[arg-type]
                activityState=str(tick_state.get("activity_state") or "unknown"),
                fallVariant=(str(tick_state.get("fall_variant")) if tick_state.get("fall_variant") else None),
                fallState=fall_state_value,  # type: ignore[arg-type]
                lastFallEventAt=last_fall_event.timestamp if last_fall_event else None,
                countdownStartedAt=countdown_started_at,
                countdownRemainingSec=countdown_remaining,
                countdownTotalSec=int(countdown_total),
                sosActive=sos_active,
                recentFallEvents=[
                    FallEventEntry(
                        id=event.id,
                        timestamp=event.timestamp,
                        eventType=event.event_type,
                        severity=event.severity,  # type: ignore[arg-type]
                        variant=event.metadata.get("variant") or None,
                    )
                    for event in recent_fall_events
                ],
                aiPrediction=self._fall_predictions.get(device_id),
                motionWindowRef=self._fall_motion_refs.get(device_id),
                countdownPolicy=cached_policy,
                preTriggerResult=self._fall_pre_trigger_results.get(device_id),
            )

    def motion_latest(self, session_id: str, device_id: str) -> MotionLatest:
        """Return the most recent motion window emitted for `device_id`.

        We pull straight from `record.last_tick_outputs` so the FE can
        render the same arrays the dataset registry produced — no
        synthetic preview, no client-side fabrication.
        """
        with self._lock:
            record = self._require_session(session_id)
            if device_id not in record.device_ids:
                raise KeyError(f"Device {device_id} not in session {session_id}")
            payload = self._latest_motion_payload_locked(record, device_id)
            state = (payload or {}).get("state") or {}
            motion = (payload or {}).get("motion") or {}
            return MotionLatest(
                deviceId=device_id,
                sessionId=session_id,
                emittedAt=str((payload or {}).get("emitted_at") or _utc_now_iso()),
                activityState=str(state.get("activity_state") or "unknown"),
                fallVariant=(str(state.get("fall_variant")) if state.get("fall_variant") else None),
                sampleRate=_safe_float(motion.get("sample_rate"), None),
                accelX=_coerce_float_list(motion.get("accel_x")),
                accelY=_coerce_float_list(motion.get("accel_y")),
                accelZ=_coerce_float_list(motion.get("accel_z")),
                accelMag=_coerce_float_list(motion.get("accel_mag")),
                gyroX=_coerce_float_list(motion.get("gyro_x")),
                gyroY=_coerce_float_list(motion.get("gyro_y")),
                gyroZ=_coerce_float_list(motion.get("gyro_z")),
            )

    def _auto_resolve_fall_countdowns_locked(self, record: "SessionRecord") -> None:
        """Module FA: clear ``fall_countdown`` devices whose policy auto-resolves.

        ``fall_brief`` is the canonical case: a 10s countdown that ends
        without operator intervention.  We synthesise a ``sos_cancel``
        event so the recent-events feed + FE banner show the resolution
        consistently with the operator-driven cancel path.
        """
        for device_id in list(record.device_ids):
            policy = self._fall_countdown_policies.get(device_id)
            if policy is None or not policy.autoResolve:
                continue
            device = self.devices.get(device_id)
            if device is None or device.state not in {"fall_countdown", "sos_active"}:
                continue
            # Find the most recent fall_detected to compute elapsed time.
            last_fall_event = next(
                (
                    event
                    for event in reversed(self.event_history)
                    if event.device_id == device_id and event.event_type == "fall_detected"
                ),
                None,
            )
            if last_fall_event is None:
                continue
            elapsed = self._iso_age_seconds(last_fall_event.timestamp)
            if elapsed < float(policy.totalSec):
                continue
            # Auto-resolve: revert FSM + persona + emit a synthetic cancel.
            device.state = "streaming"
            for sim_device in record.simulator.devices:
                if sim_device.device_id == device_id:
                    if sim_device.engine.state.activity_state == "fall":
                        sim_device.engine.transition_to("recovery")
                    break
            self._record_event(
                device_id=device_id,
                event_type="sos_cancel",
                severity="normal",
                message="Auto-resolved short fall (variant policy)",
                metadata={"variant": "auto_resolve", "source": "tick_auto_resolve"},
            )
            # Drop AI verdict + policy so the FE doesn't keep rendering the
            # countdown card after auto-resolve.
            self._fall_predictions.pop(device_id, None)
            self._fall_motion_refs.pop(device_id, None)
            self._fall_countdown_policies.pop(device_id, None)
            self._fall_pre_trigger_results.pop(device_id, None)
