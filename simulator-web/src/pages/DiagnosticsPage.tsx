import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileJson, ListChecks } from "lucide-react";
import { ErrorCard } from "../components/ui/ErrorCard";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { ThresholdInspectorPanel } from "../components/domain/ThresholdInspectorPanel";
import { TriggerConfigPanel } from "../components/domain/TriggerConfigPanel";
import { fetchSettings } from "../services/settingsApi";

// ---------------------------------------------------------------------------
// DiagnosticsPage — Module D.1 (post Risk-Tools removal).
//
// Operator-only surface for read-only diagnostics:
//   1. Threshold Inspector → DB vs fallback ngưỡng vitals (F.9)
//   2. Trigger Config      → cấu hình rule + fall pipeline (F.10)
//
// Tab `risk-tools` đã bị bỏ vì BE đã dispose `POST /analytics/risk/trigger`
// (ADR-020 Phase 7 S7) và `risk-inject` chỉ dùng cho dựng kịch bản test —
// không phù hợp với operator hằng ngày.
// ---------------------------------------------------------------------------

type DiagnosticsTab = "thresholds" | "trigger-config";

const TAB_ITEMS = [
  { key: "thresholds" as const, label: "Threshold Inspector", icon: <ListChecks size={14} /> },
  { key: "trigger-config" as const, label: "Trigger Config", icon: <FileJson size={14} /> },
];

const VALID_TABS = new Set<DiagnosticsTab>(["thresholds", "trigger-config"]);

export function DiagnosticsPage() {
  const [tab, setTab] = useState<DiagnosticsTab>(() => initialTabFromHash());

  useEffect(() => {
    if (typeof window === "undefined") return;
    const next = `#${tab}`;
    if (window.location.hash !== next) {
      window.history.replaceState(null, "", next);
    }
  }, [tab]);

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 30_000,
  });

  return (
    <section className="page-section">
      <PageHeader
        title="Diagnostics"
        subtitle="Công cụ chỉ-đọc cho operator: kiểm tra ngưỡng vitals và cấu hình rule mà mô phỏng đang dùng. Dữ liệu đến từ DB và file JSON trên disk."
      />

      <Tabs items={TAB_ITEMS} activeKey={tab} onChange={(key) => setTab(key as DiagnosticsTab)} />

      {tab === "thresholds" ? (
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

function initialTabFromHash(): DiagnosticsTab {
  if (typeof window === "undefined") return "thresholds";
  const raw = window.location.hash.replace(/^#/, "") as DiagnosticsTab;
  return VALID_TABS.has(raw) ? raw : "thresholds";
}
