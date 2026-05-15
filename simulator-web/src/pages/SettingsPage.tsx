import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorCard } from "../components/ui/ErrorCard";
import { PersistenceIndicator } from "../components/domain/settings/PersistenceIndicator";
import { ReadOnlyFlagRow } from "../components/domain/settings/ReadOnlyFlagRow";
import { DiagnosticsPointer } from "../components/domain/settings/DiagnosticsPointer";
import {
  fetchSettings,
  restoreRuntimeDefaults,
  updateRuntimeConfig,
} from "../services/settingsApi";
import type {
  RuntimeConfigSaveResponse,
  RuntimeConfigUpdate,
  RuntimePersistenceBlock,
  SimulatorSettingsResponse,
  TriggerMode,
} from "../types/settings";
import { notify } from "../utils/toast";
import { formatSavedAt } from "../utils/format";
import { useConfirm } from "../hooks/useConfirm";
import { useUnsavedGuard } from "../hooks/useUnsavedGuard";

/* ── Section: Runtime Config (editable + persisted to runtime.json) ── */

function RuntimeSection({
  data,
  onMutated,
}: {
  data: SimulatorSettingsResponse;
  onMutated: () => void;
}) {
  // Local form state seeded from server. Re-sync if the underlying query
  // refreshes (e.g. after Restore defaults) — required so the inputs reflect
  // the new values without forcing a full unmount.
  const [tickInterval, setTickInterval] = useState(String(data.runtime.tick_interval_seconds));
  const [pushInterval, setPushInterval] = useState(String(data.runtime.push_interval_seconds));
  const [sleepSpeed, setSleepSpeed] = useState(String(data.runtime.sleep_speed_factor));
  const [persistence, setPersistence] = useState<RuntimePersistenceBlock>(data.persistence);
  const queryClient = useQueryClient();
  // Module G.11 — replaces the previous `window.confirm` shim.
  const [confirm, confirmDialog] = useConfirm();

  useEffect(() => {
    setTickInterval(String(data.runtime.tick_interval_seconds));
    setPushInterval(String(data.runtime.push_interval_seconds));
    setSleepSpeed(String(data.runtime.sleep_speed_factor));
    setPersistence(data.persistence);
  }, [
    data.runtime.tick_interval_seconds,
    data.runtime.push_interval_seconds,
    data.runtime.sleep_speed_factor,
    data.persistence,
  ]);

  // Module G.11 — optimistic save.
  //
  // The "Lưu thay đổi" button used to wait the BE round-trip *and* the
  // settings query refetch before the runtime values reflected on the
  // page (and on every other consumer of `["settings"]`).  We patch the
  // cached `SimulatorSettingsResponse` with the proposed body in
  // `onMutate`, snapshot the previous state for rollback, then let
  // `onSuccess` overwrite with the BE-truth (which now also contains
  // an authoritative `last_saved_at`).  On failure the snapshot
  // restores the cache and the form's `useEffect` resync brings the
  // inputs back.
  const saveMutation = useMutation<
    RuntimeConfigSaveResponse,
    Error,
    RuntimeConfigUpdate,
    { previous?: SimulatorSettingsResponse }
  >({
    mutationFn: (body) => updateRuntimeConfig(body),
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previous = queryClient.getQueryData<SimulatorSettingsResponse>(["settings"]);
      if (previous) {
        const optimistic: SimulatorSettingsResponse = {
          ...previous,
          runtime: {
            ...previous.runtime,
            ...(body.tick_interval_seconds !== undefined && {
              tick_interval_seconds: body.tick_interval_seconds,
            }),
            ...(body.push_interval_seconds !== undefined && {
              push_interval_seconds: body.push_interval_seconds,
            }),
            ...(body.sleep_speed_factor !== undefined && {
              sleep_speed_factor: body.sleep_speed_factor,
            }),
          },
          // Mark the persistence indicator as "đang lưu" — the
          // `<PersistenceIndicator/>` reads `pending` from the mutation
          // state, but if a different page reads `["settings"]` we
          // still want a non-stale `last_saved_at` semantically.
          persistence: { ...previous.persistence, last_error: null },
        };
        queryClient.setQueryData(["settings"], optimistic);
      }
      return { previous };
    },
    onSuccess: (response) => {
      setPersistence(response.persistence);
      notify.success(
        `Đã lưu vào runtime.json — vẫn áp dụng sau khi khởi động lại (${formatSavedAt(response.persistence.last_saved_at)}).`,
      );
      onMutated();
    },
    onError: (err, _body, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(["settings"], ctx.previous);
      notify.error(`Không lưu được runtime config: ${err.message}`);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const resetMutation = useMutation<
    RuntimeConfigSaveResponse,
    Error,
    void,
    { previous?: SimulatorSettingsResponse }
  >({
    mutationFn: () => restoreRuntimeDefaults(),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previous = queryClient.getQueryData<SimulatorSettingsResponse>(["settings"]);
      // We don't know the defaults locally, so we don't optimistically
      // rewrite values — but we *do* take a snapshot so a failure
      // doesn't leave the cache in a half-invalidated state.
      return { previous };
    },
    onSuccess: (response) => {
      setPersistence(response.persistence);
      notify.success("Đã khôi phục về cấu hình mặc định (runtime_defaults.json).");
      onMutated();
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(["settings"], ctx.previous);
      notify.error(`Không khôi phục được mặc định: ${err.message}`);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    saveMutation.mutate({
      tick_interval_seconds: Number(tickInterval),
      push_interval_seconds: Number(pushInterval),
      sleep_speed_factor: Number(sleepSpeed),
    });
  }

  async function handleRestoreDefaults() {
    const ok = await confirm({
      severity: "warning",
      title: "Khôi phục cấu hình mặc định?",
      description:
        "Thao tác này sẽ xoá runtime.json và đưa tick/push/sleep speed về giá trị trong runtime_defaults.json. Mọi điều chỉnh runtime hiện tại sẽ mất.",
      confirmLabel: "Khôi phục mặc định",
    });
    if (!ok) return;
    resetMutation.mutate();
  }

  const isPending = saveMutation.isPending || resetMutation.isPending;

  // Module G.14 — `beforeunload` guard while the form has un-saved
  // edits.  Compare the live input strings against the server-truth
  // numbers (coerced to string for stable equality).  We suppress the
  // guard while a save is in flight so the operator can reload during
  // the brief mutation window without an extra prompt.
  const isDirty =
    !isPending &&
    (tickInterval !== String(data.runtime.tick_interval_seconds) ||
      pushInterval !== String(data.runtime.push_interval_seconds) ||
      sleepSpeed !== String(data.runtime.sleep_speed_factor));
  useUnsavedGuard(isDirty);

  return (
    <Card header={<strong>Simulator Runtime</strong>}>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <PersistenceIndicator persistence={persistence} pending={saveMutation.isPending} />
        <label className="form-field">
          <span className="form-label">Tick Interval (giây)</span>
          <Input type="number" step="0.1" min="0.1" max="60" value={tickInterval} onChange={(e) => setTickInterval(e.target.value)} />
        </label>
        <label className="form-field">
          <span className="form-label">Push Interval (giây)</span>
          <Input type="number" step="1" min="1" max="300" value={pushInterval} onChange={(e) => setPushInterval(e.target.value)} />
        </label>
        <label className="form-field">
          <span className="form-label">Sleep Speed Factor</span>
          <Input type="number" step="1" min="1" max="3600" value={sleepSpeed} onChange={(e) => setSleepSpeed(e.target.value)} />
        </label>
        <div className="form-field">
          <span className="form-label">Health Backend URL (read-only)</span>
          <Input value={data.runtime.health_backend_url} readOnly style={{ opacity: 0.6 }} />
        </div>
        <div style={{ display: "flex", gap: "8px", marginTop: "4px", flexWrap: "wrap" }}>
          <Button type="submit" disabled={isPending}>
            <Save size={14} style={{ marginRight: "6px" }} />
            {saveMutation.isPending ? "Đang lưu…" : "Lưu thay đổi"}
          </Button>
          <Button type="button" variant="ghost" disabled={isPending} onClick={handleRestoreDefaults}>
            <RotateCcw size={14} style={{ marginRight: "6px" }} />
            {resetMutation.isPending ? "Đang khôi phục…" : "Khôi phục mặc định"}
          </Button>
        </div>
      </form>
      {confirmDialog}
    </Card>
  );
}


/* ── Section: Feature Flags (truthful copy, read-only badges) ────────── */

interface TriggerModeMeta {
  label: string;
  description: string;
  tone: { fg: string; bg: string; border: string };
}

const TRIGGER_MODE_META: Record<TriggerMode, TriggerModeMeta> = {
  off: {
    label: "Tắt",
    description:
      "Pre-trigger không chạy. Mô phỏng phát vitals bình thường nhưng không đánh giá rule local hay gọi model.",
    tone: { fg: "var(--text-secondary)", bg: "var(--severity-offline-bg)", border: "var(--severity-offline-border)" },
  },
  shadow: {
    label: "Shadow",
    description:
      "Pre-trigger chạy nhưng KHÔNG gọi model AI. Rule + fall detection chỉ chạy local — phù hợp để quan sát trigger hoạt động trước khi bật model.",
    tone: { fg: "var(--severity-info)", bg: "var(--severity-info-bg)", border: "var(--severity-info-border)" },
  },
  active: {
    label: "Active",
    description:
      "Pre-trigger chạy + escalate sang model AI khi rule bắn. Đây là chế độ đầy đủ — yêu cầu healthguard-model-api online.",
    tone: { fg: "var(--severity-normal)", bg: "var(--severity-normal-bg)", border: "var(--severity-normal-border)" },
  },
};

function FeatureFlagsSection({ data }: { data: SimulatorSettingsResponse }) {
  const flags = data.feature_flags;
  const meta = TRIGGER_MODE_META[flags.trigger_mode];
  const thresholdSource = data.threshold_source;
  const thresholdLabel = thresholdSourceLabel(thresholdSource);

  return (
    <Card
      header={
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <strong>Feature Flags</strong>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            (chỉ đọc — đổi bằng env var hoặc Module D Diagnostics)
          </span>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div
          style={{
            display: "grid",
            gap: "8px",
            padding: "12px",
            borderRadius: "var(--radius-md)",
            border: `1px solid ${meta.tone.border}`,
            background: meta.tone.bg,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Trigger mode
            </span>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                padding: "2px 10px",
                borderRadius: "var(--radius-full)",
                color: meta.tone.fg,
                border: `1px solid ${meta.tone.border}`,
                background: "var(--bg-glass)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {meta.label}
            </span>
            <small style={{ color: "var(--text-muted)", fontSize: "12px" }}>
              enable_model_calls = <code>{String(flags.enable_model_calls)}</code>
            </small>
          </div>
          <small style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
            {meta.description}
          </small>
        </div>

        <ReadOnlyFlagRow
          envVar="PRE_MODEL_TRIGGER_ENABLED"
          checked={flags.pre_model_trigger_enabled}
          hint={
            flags.pre_model_trigger_enabled
              ? "Bật. Quyết định mode shadow vs active dựa vào enable_model_calls."
              : "Tắt. Pre-trigger không chạy bất kể giá trị enable_model_calls."
          }
        />
        <ReadOnlyFlagRow
          envVar="USE_DB_THRESHOLDS"
          checked={flags.use_db_thresholds}
          hint={
            thresholdSource === "db"
              ? `Đang dùng ngưỡng từ DB (${thresholdLabel}).`
              : `Đang dùng ngưỡng dự phòng (${thresholdLabel}). Bật cờ này + đảm bảo DB sẵn sàng để chuyển sang DB thresholds.`
          }
        />
      </div>
    </Card>
  );
}

function thresholdSourceLabel(source: string): string {
  switch (source) {
    case "db":
      return "đọc từ database";
    case "fallback":
      return "ngưỡng dự phòng từ vitals_service";
    case "unavailable":
      return "không truy vấn được provider";
    default:
      return source;
  }
}

/* ── Main Page ──────────────────────────────────────────────────────── */

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 30_000,
  });

  function handleRuntimeMutated() {
    queryClient.invalidateQueries({ queryKey: ["settings"] });
  }

  if (isLoading) {
    return (
      <section className="page-section" style={{ maxWidth: "900px" }}>
        <PageHeader title="Cấu hình runtime" />
        <Skeleton style={{ height: "200px" }} />
        <Skeleton style={{ height: "300px" }} />
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className="page-section" style={{ maxWidth: "900px" }}>
        <PageHeader title="Cấu hình runtime" />
        <ErrorCard message={error instanceof Error ? error.message : "Không thể tải cấu hình runtime."} />
      </section>
    );
  }

  return (
    <section className="page-section" style={{ maxWidth: "900px" }}>
      <PageHeader
        title="Cấu hình runtime"
        subtitle="Các giá trị mutable của IoT Simulator. Tham khảo Diagnostics cho ngưỡng vitals (chỉ đọc) và rule/fall config."
      />
      <RuntimeSection data={data} onMutated={handleRuntimeMutated} />
      <FeatureFlagsSection data={data} />
      <DiagnosticsPointer />
    </section>
  );
}
