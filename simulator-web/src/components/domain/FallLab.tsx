import { useEffect, useMemo, useRef, useState } from "react";
import type { SimulatedDevice } from "../../types/device";
import { injectEvent, injectFallEvent } from "../../services/eventApi";
import { useRecentEvents } from "../../hooks/useRecentEvents";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { notify } from "../../utils/toast";

interface FallLabProps {
  devices: SimulatedDevice[];
}

export function FallLab({ devices }: FallLabProps) {
  const [targetId, setTargetId] = useState<string>("");
  const [countdown, setCountdown] = useState(0);
  const [lastVariant, setLastVariant] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const resolvedTarget = useMemo(() => targetId || (devices[0]?.id ?? ""), [devices, targetId]);
  const targetRef = useRef(resolvedTarget);
  useEffect(() => { targetRef.current = resolvedTarget; }, [resolvedTarget]);

  const { data: recentEvents = [] } = useRecentEvents(30, 1500, {
    enabled: Boolean(resolvedTarget),
    select: (events) => events.filter((event) => event.deviceId === resolvedTarget).slice(0, 15),
  });

  const cancelCountdown = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setCountdown(0);
  };

  const startCountdown = () => {
    if (!resolvedTarget) {
      return;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    setCountdown(30);
    timerRef.current = setInterval(() => {
      setCountdown((value) => {
        if (value <= 1) {
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
          injectFallEvent(targetRef.current, "fall_no_response").catch(() => {
            notify.error("Gửi sự kiện fall_no_response thất bại");
          });
          return 0;
        }
        return value - 1;
      });
    }, 1000);
  };

  useEffect(() => () => cancelCountdown(), []);

  return (
    <Card header={<strong>Phòng thí nghiệm té ngã</strong>}>
      <div style={{ display: "grid", gap: "10px" }}>
        <select
          value={resolvedTarget}
          onChange={(event) => setTargetId(event.target.value)}
          style={{
            background: "var(--bg-base)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-md)",
            padding: "8px",
          }}
        >
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </select>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          <Button
            variant="secondary"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("false_fall");
              try {
                setLastVariant("false_fall");
                await injectFallEvent(resolvedTarget, "false_fall");
              } catch {
                notify.error("Gửi sự kiện 'Té ngã giả' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "false_fall" ? "Đang gửi…" : "Té ngã giả"}
          </Button>
          <Button
            variant="secondary"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("fall_brief");
              try {
                setLastVariant("fall_brief");
                await injectFallEvent(resolvedTarget, "fall_brief");
              } catch {
                notify.error("Gửi sự kiện 'Té ngã nhẹ' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "fall_brief" ? "Đang gửi…" : "Té ngã nhẹ"}
          </Button>
          <Button
            variant="danger"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("confirmed");
              try {
                setLastVariant("confirmed");
                await injectFallEvent(resolvedTarget, "confirmed");
                startCountdown();
              } catch {
                notify.error("Gửi sự kiện 'Té ngã xác nhận' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "confirmed" ? "Đang gửi…" : "Té ngã xác nhận"}
          </Button>
          <Button
            variant="danger"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("fall_no_response");
              try {
                setLastVariant("fall_no_response");
                await injectFallEvent(resolvedTarget, "fall_no_response");
              } catch {
                notify.error("Gửi sự kiện 'Không phản hồi' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "fall_no_response" ? "Đang gửi…" : "Không phản hồi"}
          </Button>
          <Button
            variant="outline"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("stress");
              try {
                await injectEvent(resolvedTarget, "stress");
              } catch {
                notify.error("Gửi sự kiện 'Gây căng thẳng' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "stress" ? "Đang gửi…" : "⚡ Gây căng thẳng"}
          </Button>
          <Button
            variant="ghost"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("neutral");
              try {
                await injectEvent(resolvedTarget, "neutral");
              } catch {
                notify.error("Gửi sự kiện 'Trở về bình thường' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "neutral" ? "Đang gửi…" : "Trở về bình thường"}
          </Button>
          <Button
            variant="outline"
            disabled={!!pendingAction}
            onClick={async () => {
              setPendingAction("sos_triggered");
              try {
                await injectEvent(resolvedTarget, "sos_triggered");
              } catch {
                notify.error("Gửi sự kiện 'SOS thủ công' thất bại");
              } finally {
                setPendingAction(null);
              }
            }}
          >
            {pendingAction === "sos_triggered" ? "Đang gửi…" : "SOS thủ công"}
          </Button>
        </div>
        {lastVariant ? (
          <small style={{ color: "var(--text-secondary)" }}>
            Biến thể hiện tại: <code>{lastVariant}</code>
          </small>
        ) : null}
        {countdown > 0 ? (
          <div style={{ border: "1px solid var(--severity-warning)", borderRadius: "var(--radius-md)", padding: "10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
              <strong>Đếm ngược té ngã</strong>
              <span>{countdown} giây</span>
            </div>
            <div style={{ height: "8px", borderRadius: "999px", background: "var(--bg-base)", overflow: "hidden" }}>
              <div style={{ width: `${(countdown / 30) * 100}%`, height: "100%", background: countdown < 10 ? "var(--severity-critical)" : "var(--severity-warning)" }} />
            </div>
            <div style={{ marginTop: "10px" }}>
              <Button variant="secondary" onClick={cancelCountdown}>
                Tôi ổn - Hủy SOS
              </Button>
            </div>
          </div>
        ) : null}
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
          {recentEvents.length === 0 ? (
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0 }}>Chưa có sự kiện nào.</p>
          ) : (
            <div style={{ display: "grid", gap: "4px", maxHeight: "200px", overflowY: "auto" }}>
              {recentEvents.map((event) => (
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
      </div>
    </Card>
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
