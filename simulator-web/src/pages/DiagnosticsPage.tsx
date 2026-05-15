import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileJson, Gauge, ListChecks, Watch } from "lucide-react";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorCard } from "../components/ui/ErrorCard";
import { PageHeader } from "../components/ui/PageHeader";
import { Select } from "../components/ui/Select";
import { Skeleton } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { RiskInjectorPanel } from "../components/domain/RiskInjectorPanel";
import { ThresholdInspectorPanel } from "../components/domain/ThresholdInspectorPanel";
import { TriggerConfigPanel } from "../components/domain/TriggerConfigPanel";
import { useDevices } from "../hooks/useDevices";
import { fetchSettings } from "../services/settingsApi";

// ---------------------------------------------------------------------------
// DiagnosticsPage — Module D.1.
//
// Operator-only surface for tooling that mutates state (`risk-tools`),
// inspects truth (`thresholds`), or surfaces low-level config
// (`trigger-config`).  Lives at `/diagnostics` so `/analytics` stays
// safe-to-browse for clinical viewers (D.4).
//
// Three tabs:
//   1. Risk Tools         → on-demand calc + risk inject + XAI (extracted in D.2/D.5)
//   2. Threshold Inspector→ read-only DB vs fallback (moved from Settings — F.9)
//   3. Trigger Config     → rules + fall JSON viewer (moved from Settings — F.10)
//
// Each tab manages its own data fetching to keep Diagnostics independent
// of the dashboard polling cadence.
// ---------------------------------------------------------------------------

type DiagnosticsTab = "risk-tools" | "thresholds" | "trigger-config";

const TAB_ITEMS = [
  { key: "risk-tools" as const, label: "Risk Tools", icon: <Gauge size={14} /> },
  { key: "thresholds" as const, label: "Threshold Inspector", icon: <ListChecks size={14} /> },
  { key: "trigger-config" as const, label: "Trigger Config", icon: <FileJson size={14} /> },
];

const VALID_TABS = new Set<DiagnosticsTab>(["risk-tools", "thresholds", "trigger-config"]);

export function DiagnosticsPage() {
  const [tab, setTab] = useState<DiagnosticsTab>(() => initialTabFromHash());
  const queryClient = useQueryClient();

  // Persist the active tab in the URL hash so deep links from the Analytics
  // hint card (`#risk-tools`) jump to the right tab without extra routing.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const next = `#${tab}`;
    if (window.location.hash !== next) {
      window.history.replaceState(null, "", next);
    }
  }, [tab]);

  const { data: devices = [], isLoading: devicesLoading } = useDevices();
  const [deviceId, setDeviceId] = useState<string>("");

  useEffect(() => {
    if (!devices.length) {
      setDeviceId("");
      return;
    }
    if (!deviceId || !devices.some((device) => device.id === deviceId)) {
      setDeviceId(devices[0].id);
    }
  }, [deviceId, devices]);

  // Settings query feeds both Threshold Inspector and Trigger Config tabs.
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 30_000,
  });

  const handleRiskMutated = useMemo(
    () => () => {
      queryClient.invalidateQueries({ queryKey: ["analytics", "risk", deviceId] });
    },
    [queryClient, deviceId],
  );

  return (
    <section className="page-section">
      <PageHeader
        title="Diagnostics"
        subtitle="Công cụ vận hành cho operator: chạy tính toán theo yêu cầu, tiêm dữ liệu thử nghiệm, kiểm tra ngưỡng + cấu hình rule mà mô phỏng đang dùng. Trang Phân tích vẫn ở chế độ chỉ đọc."
      />

      <Tabs items={TAB_ITEMS} activeKey={tab} onChange={(key) => setTab(key as DiagnosticsTab)} />

      {tab === "risk-tools" ? (
        <RiskToolsTab
          devices={devices}
          devicesLoading={devicesLoading}
          deviceId={deviceId}
          onDeviceChange={setDeviceId}
          onMutated={handleRiskMutated}
        />
      ) : tab === "thresholds" ? (
        <SettingsBackedTab
          query={settingsQuery}
          render={(data) => <ThresholdInspectorPanel data={data} />}
          emptyTitle="Chưa nạp được settings"
        />
      ) : (
        <SettingsBackedTab
          query={settingsQuery}
          render={(data) => <TriggerConfigPanel data={data} />}
          emptyTitle="Chưa nạp được settings"
        />
      )}
    </section>
  );
}

// ── Tab content ─────────────────────────────────────────────────────────

function RiskToolsTab({
  devices,
  devicesLoading,
  deviceId,
  onDeviceChange,
  onMutated,
}: {
  devices: { id: string; name: string }[];
  devicesLoading: boolean;
  deviceId: string;
  onDeviceChange: (id: string) => void;
  onMutated: () => void;
}) {
  if (devicesLoading) {
    return <Skeleton style={{ height: "260px" }} />;
  }
  if (!devices.length) {
    return (
      <EmptyState
        icon={Watch}
        title="Chưa có thiết bị"
        description="Tạo ít nhất một thiết bị để chạy tính toán hoặc tiêm rủi ro."
      />
    );
  }
  return (
    <div style={{ display: "grid", gap: "14px" }}>
      <Card>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
          <div>
            <strong style={{ fontSize: "13px" }}>Thiết bị mục tiêu</strong>
            <p style={{ margin: "2px 0 0 0", fontSize: "12px", color: "var(--text-secondary)" }}>
              Toàn bộ thao tác Risk Tools ghi vào DB cho thiết bị đang chọn.
            </p>
          </div>
          <Select
            value={deviceId}
            onChange={(event) => onDeviceChange(event.target.value)}
            aria-label="Chọn thiết bị cho Risk Tools"
          >
            {devices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      <RiskInjectorPanel deviceId={deviceId} onMutated={onMutated} />
    </div>
  );
}

interface SettingsBackedTabProps<T> {
  query: { data?: T; isLoading: boolean; isError: boolean; error: unknown };
  render: (data: T) => React.ReactNode;
  emptyTitle: string;
}

function SettingsBackedTab<T>({ query, render, emptyTitle }: SettingsBackedTabProps<T>) {
  if (query.isLoading) {
    return <Skeleton style={{ height: "320px" }} />;
  }
  if (query.isError || !query.data) {
    return (
      <ErrorCard
        message={
          query.error instanceof Error
            ? query.error.message
            : `${emptyTitle} — kiểm tra log mô phỏng.`
        }
      />
    );
  }
  return <>{render(query.data)}</>;
}

// ── Helpers ─────────────────────────────────────────────────────────────

function initialTabFromHash(): DiagnosticsTab {
  if (typeof window === "undefined") return "risk-tools";
  const raw = window.location.hash.replace(/^#/, "") as DiagnosticsTab;
  return VALID_TABS.has(raw) ? raw : "risk-tools";
}
