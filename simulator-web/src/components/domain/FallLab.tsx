import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import type { SimulatedDevice } from "../../types/device";
import type { FallStateValue } from "../../types/fall";
import { injectEvent, injectFallEvent, injectSosCancel } from "../../services/eventApi";
import { useFallState } from "../../hooks/useFallState";
import { useRecentEvents } from "../../hooks/useRecentEvents";
import { useConfirm } from "../../hooks/useConfirm";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { runWithToast } from "../../utils/toast";
import { FALL_LAB_RECENT_EVENTS_LIMIT, POLL_INTERVALS } from "../../config/defaults";

// ---------------------------------------------------------------------------
// FallLab — Module C.6 rebuild.
//
// The countdown bar, "Tôi ổn — Hủy SOS" button, and current variant chip are
// all driven by the BE-derived `FallState` (`/api/sim/sessions/{id}/
// fall-state`). The previous implementation ran a 30 s `setInterval` purely
// in the browser and the cancel button only cleared that local timer — the
// BE never heard about it.  Now:
//
//   * `countdownRemainingSec` ticks down because the BE clock advances.
//   * "Tôi ổn — Hủy SOS" POSTs `sos_cancel` so the persona engine
//      transitions out of `fall` and `device.state` flips to `streaming`.
//   * `recentFallEvents` and the `fallState` lifecycle reflect what
//     verification + analytics will see.
// ---------------------------------------------------------------------------

interface FallLabProps {
  devices: SimulatedDevice[];
  sessionId: string | null;
  focusDeviceId?: string | null;
}

export function FallLab({ devices, sessionId, focusDeviceId }: FallLabProps) {
  const [targetId, setTargetId] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const resolvedTarget = useMemo(() => {
    if (targetId && devices.some((device) => device.id === targetId)) return targetId;
    if (focusDeviceId && devices.some((device) => device.id === focusDeviceId)) {
      return focusDeviceId;
    }
    return devices[0]?.id ?? "";
  }, [targetId, focusDeviceId, devices]);

  // Reset the local override whenever the focal device disappears so the
  // dropdown stays in sync with `<SessionRunnerPage/>`.
  useEffect(() => {
    if (targetId && !devices.some((device) => device.id === targetId)) {
      setTargetId("");
    }
  }, [devices, targetId]);

  const { data: fallState } = useFallState(sessionId, resolvedTarget || null);

  const { data: recentEvents = [] } = useRecentEvents(
    FALL_LAB_RECENT_EVENTS_LIMIT,
    POLL_INTERVALS.fallLabEvents,
    {
      enabled: Boolean(resolvedTarget),
      select: (events) => events.filter((event) => event.deviceId === resolvedTarget).slice(0, 15),
    },
  );

  const guardDisabled = !sessionId || !resolvedTarget || !!pendingAction;

  // Module G.2 — confirm before destructive fall events.  We surface
  // confirms for the three actions that drive the BE FSM into
  // `sos_active` / `fall_countdown` so an accidental click can't fire
  // a real SOS pipeline.
  const [confirm, confirmDialog] = useConfirm();

  /**
   * Wrapper for the mutation buttons.  Replaces the old `withGuard`:
   *   - optionally awaits a confirm prompt first;
   *   - tracks `pendingAction` so the *clicked* button shows "Đang gửi…"
   *     and other buttons are disabled (this is in addition to sonner's
   *     loading toast — the inline label avoids a "ghost click" feel);
   *   - delegates the success/error toast to `runWithToast` so every
   *     button's UX is consistent across the app.
   */
  async function runAction(
    action: string,
    fn: () => Promise<void>,
    messages: { loading: string; success: string; error: string },
    confirmOptions?: Parameters<typeof confirm>[0],
  ) {
    if (guardDisabled) return;
    if (confirmOptions) {
      const ok = await confirm(confirmOptions);
      if (!ok) return;
    }
    setPendingAction(action);
    try {
      await runWithToast(fn(), messages);
    } catch {
      // runWithToast already surfaced the error toast; swallow so the
      // button doesn't propagate an unhandled rejection.
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <Card header={<FallLabHeader fallState={fallState?.fallState ?? "idle"} />}>
      <div style={{ display: "grid", gap: "10px" }}>
        <select
          value={resolvedTarget}
          onChange={(event) => setTargetId(event.target.value)}
          aria-label="Chọn thiết bị mục tiêu cho phòng thí nghiệm té ngã"
          style={selectStyle}
          disabled={!sessionId}
        >
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </select>

        {!sessionId && (
          <p style={hintStyle}>
            Chưa có phiên đang chạy — bắt đầu một phiên trên Devices/Phiên mô phỏng để mở khoá Fall Lab.
          </p>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          <Button
            variant="secondary"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "false_fall",
                () => injectFallEvent(resolvedTarget, "false_fall"),
                {
                  loading: "Đang gửi té ngã giả…",
                  success: "Đã gửi sự kiện 'Té ngã giả'.",
                  error: "Gửi sự kiện 'Té ngã giả' thất bại.",
                },
              )
            }
          >
            {pendingAction === "false_fall" ? "Đang gửi…" : "Té ngã giả"}
          </Button>
          <Button
            variant="secondary"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "fall_brief",
                () => injectFallEvent(resolvedTarget, "fall_brief"),
                {
                  loading: "Đang gửi té ngã nhẹ…",
                  success: "Đã gửi sự kiện 'Té ngã nhẹ'.",
                  error: "Gửi sự kiện 'Té ngã nhẹ' thất bại.",
                },
              )
            }
          >
            {pendingAction === "fall_brief" ? "Đang gửi…" : "Té ngã nhẹ"}
          </Button>
          <Button
            variant="danger"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "confirmed",
                () => injectFallEvent(resolvedTarget, "confirmed"),
                {
                  loading: "Đang gửi té ngã xác nhận…",
                  success: "Đã gửi sự kiện 'Té ngã xác nhận'. SOS countdown đang chạy.",
                  error: "Gửi sự kiện 'Té ngã xác nhận' thất bại.",
                },
                {
                  severity: "critical",
                  title: "Xác nhận gửi sự kiện té ngã?",
                  description:
                    "Sự kiện này đẩy thiết bị vào fall_countdown ở BE và bắt đầu đếm ngược 30 giây trước khi kích hoạt SOS thực sự. Có chắc chắn không?",
                  confirmLabel: "Gửi té ngã xác nhận",
                },
              )
            }
          >
            {pendingAction === "confirmed" ? "Đang gửi…" : "Té ngã xác nhận"}
          </Button>
          <Button
            variant="danger"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "fall_no_response",
                () => injectFallEvent(resolvedTarget, "fall_no_response"),
                {
                  loading: "Đang gửi té ngã không phản hồi…",
                  success: "Đã gửi sự kiện 'Không phản hồi'. SOS sẽ leo thang khi countdown hết.",
                  error: "Gửi sự kiện 'Không phản hồi' thất bại.",
                },
                {
                  severity: "critical",
                  title: "Mô phỏng té ngã không phản hồi?",
                  description:
                    "Kịch bản này không tự động hủy SOS — countdown sẽ chạy tới 0 giây và BE chuyển sang sos_active. Phù hợp khi muốn test luồng leo thang cảnh báo.",
                  confirmLabel: "Mô phỏng không phản hồi",
                },
              )
            }
          >
            {pendingAction === "fall_no_response" ? "Đang gửi…" : "Không phản hồi"}
          </Button>
          <Button
            variant="outline"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "stress",
                () => injectEvent(resolvedTarget, "stress"),
                {
                  loading: "Đang đặt thiết bị vào trạng thái căng thẳng…",
                  success: "Đã đặt persona vào trạng thái căng thẳng.",
                  error: "Gửi sự kiện 'Gây căng thẳng' thất bại.",
                },
              )
            }
          >
            {pendingAction === "stress" ? "Đang gửi…" : "⚡ Gây căng thẳng"}
          </Button>
          <Button
            variant="ghost"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "neutral",
                () => injectEvent(resolvedTarget, "neutral"),
                {
                  loading: "Đang đưa persona về trạng thái bình thường…",
                  success: "Đã đưa persona về trạng thái bình thường.",
                  error: "Gửi sự kiện 'Trở về bình thường' thất bại.",
                },
              )
            }
          >
            {pendingAction === "neutral" ? "Đang gửi…" : "Trở về bình thường"}
          </Button>
          <Button
            variant="outline"
            disabled={guardDisabled}
            onClick={() =>
              runAction(
                "sos_triggered",
                () => injectEvent(resolvedTarget, "sos_triggered"),
                {
                  loading: "Đang gửi SOS thủ công…",
                  success: "Đã kích hoạt SOS thủ công.",
                  error: "Gửi sự kiện 'SOS thủ công' thất bại.",
                },
                {
                  severity: "critical",
                  title: "Kích hoạt SOS thủ công?",
                  description:
                    "Hành động này đặt thiết bị vào sos_active ngay lập tức (không qua countdown). Chỉ dùng để test luồng cảnh báo.",
                  confirmLabel: "Kích hoạt SOS",
                },
              )
            }
          >
            {pendingAction === "sos_triggered" ? "Đang gửi…" : "SOS thủ công"}
          </Button>
        </div>

        {fallState?.fallVariant && (
          <small style={{ color: "var(--text-secondary)" }}>
            Biến thể hiện tại (BE): <code>{fallState.fallVariant}</code>
          </small>
        )}

        {fallState && fallState.countdownRemainingSec > 0 && (
          <CountdownBanner
            remaining={fallState.countdownRemainingSec}
            total={fallState.countdownTotalSec}
            disabled={!!pendingAction}
            onCancel={() =>
              runAction(
                "sos_cancel",
                () => injectSosCancel(resolvedTarget),
                {
                  loading: "Đang gửi sos_cancel…",
                  success: "Đã gửi sos_cancel — BE FSM đã clear.",
                  error: "Gửi sos_cancel thất bại — BE FSM có thể vẫn còn ở fall_countdown.",
                },
              )
            }
          />
        )}

        {fallState?.fallState === "fall_resolved" && fallState.countdownRemainingSec === 0 && (
          <ResolvedBanner />
        )}

        <RecentEventsSection events={recentEvents} />
      </div>
      {confirmDialog}
    </Card>
  );
}

// ── Header ───────────────────────────────────────────────────────────────

function FallLabHeader({ fallState }: { fallState: FallStateValue }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" }}>
      <strong>Phòng thí nghiệm té ngã</strong>
      <Badge severity={fallStateSeverity(fallState)}>{fallStateLabel(fallState)}</Badge>
    </div>
  );
}

function fallStateLabel(state: FallStateValue): string {
  switch (state) {
    case "fall_countdown":
      return "Đang đếm ngược SOS";
    case "sos_active":
      return "SOS đã kích hoạt";
    case "fall_detected":
      return "Đã ghi nhận té ngã";
    case "fall_resolved":
      return "Đã hủy / phục hồi";
    case "idle":
    default:
      return "Sẵn sàng";
  }
}

function fallStateSeverity(state: FallStateValue) {
  if (state === "sos_active") return "critical" as const;
  if (state === "fall_countdown") return "warning" as const;
  if (state === "fall_detected") return "warning" as const;
  if (state === "fall_resolved") return "normal" as const;
  return "offline" as const;
}

// ── Countdown banner (BE-driven) ─────────────────────────────────────────

function CountdownBanner({
  remaining,
  total,
  disabled,
  onCancel,
}: {
  remaining: number;
  total: number;
  disabled: boolean;
  onCancel: () => void;
}) {
  const percent = total > 0 ? Math.max(0, Math.min(100, (remaining / total) * 100)) : 0;
  const critical = remaining < 10;
  return (
    <div
      style={{
        border: `1px solid ${critical ? "var(--severity-critical)" : "var(--severity-warning)"}`,
        borderRadius: "var(--radius-md)",
        padding: "10px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <AlertTriangle size={14} style={{ color: critical ? "var(--severity-critical)" : "var(--severity-warning)" }} />
          <strong>Đếm ngược SOS (BE)</strong>
        </span>
        <span style={{ fontFamily: "var(--font-mono)" }}>
          {remaining} / {total} giây
        </span>
      </div>
      <div style={{ height: "8px", borderRadius: "999px", background: "var(--bg-base)", overflow: "hidden" }}>
        <div
          style={{
            width: `${percent}%`,
            height: "100%",
            background: critical ? "var(--severity-critical)" : "var(--severity-warning)",
            transition: "width 0.4s linear",
          }}
        />
      </div>
      <div style={{ marginTop: "10px" }}>
        <Button variant="secondary" disabled={disabled} onClick={onCancel}>
          Tôi ổn — Hủy SOS
        </Button>
      </div>
    </div>
  );
}

function ResolvedBanner() {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontSize: "12px",
        color: "var(--severity-normal)",
        background: "rgba(34,197,94,0.10)",
        border: "1px solid rgba(34,197,94,0.35)",
        borderRadius: "var(--radius-sm)",
        padding: "6px 10px",
      }}
    >
      <ShieldCheck size={14} />
      Operator đã hủy SOS — BE FSM đã trở lại trạng thái streaming.
    </div>
  );
}

// ── Recent events (existing helper, unchanged) ───────────────────────────

interface RecentEventsSectionProps {
  events: { id: string; timestamp: string; eventType: string; severity: string; message?: string | null }[];
}

function RecentEventsSection({ events }: RecentEventsSectionProps) {
  return (
    <div style={{ marginTop: "12px" }}>
      <div
        style={{
          fontSize: "11px",
          color: "var(--text-muted)",
          marginBottom: "6px",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        Nhật ký sự kiện
      </div>
      {events.length === 0 ? (
        <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0 }}>Chưa có sự kiện nào.</p>
      ) : (
        <div style={{ display: "grid", gap: "4px", maxHeight: "200px", overflowY: "auto" }}>
          {events.map((event) => (
            <div
              key={event.id}
              style={{
                display: "grid",
                gridTemplateColumns: "56px 1fr",
                gap: "8px",
                fontSize: "12px",
                padding: "5px 8px",
                borderRadius: "var(--radius-sm)",
                background: severityBackground(event.severity),
                borderLeft: `3px solid ${severityColor(event.severity)}`,
              }}
            >
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: "11px" }}>
                {formatEventTime(event.timestamp)}
              </span>
              <span style={{ color: "var(--text-primary)" }}>
                {eventIcon(event.eventType)} {event.message ?? event.eventType}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatEventTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return "--:--:--";
  }
}

function eventIcon(type: string): string {
  if (type === "sos_cancel") return "🟢";
  if (type.includes("fall")) return "🔴";
  if (type === "sos_triggered") return "🚨";
  if (type === "stress") return "⚡";
  if (type === "low_battery") return "🔋";
  if (type === "risk_scored") return "📊";
  return "ℹ️";
}

function severityBackground(sev: string): string {
  if (sev === "critical") return "rgba(239,68,68,0.08)";
  if (sev === "warning") return "rgba(245,158,11,0.08)";
  return "rgba(255,255,255,0.03)";
}

function severityColor(sev: string): string {
  if (sev === "critical") return "var(--severity-critical)";
  if (sev === "warning") return "var(--severity-warning)";
  return "var(--border-default)";
}

const selectStyle = {
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-md)",
  padding: "8px",
} as const;

const hintStyle = {
  margin: 0,
  padding: "6px 10px",
  fontSize: "12px",
  color: "var(--text-secondary)",
  background: "var(--bg-elevated)",
  border: "1px dashed var(--border-default)",
  borderRadius: "var(--radius-sm)",
} as const;
