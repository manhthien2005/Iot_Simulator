import { Pause, Play, Square } from "lucide-react";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";

interface SessionToolbarProps {
  hasSession: boolean;
  running: boolean;
  paused: boolean;
  sessionId: string | null;
  speed: 5 | 15 | 30 | 60;
  onStart: () => void;
  onStop: () => void;
  onPause: () => void;
  onResume: () => void;
  onSpeedChange: (speed: 5 | 15 | 30 | 60) => void;
}

export function SessionToolbar(props: SessionToolbarProps) {
  return (
    <div className="surface-card" style={{ padding: "14px", display: "grid", gap: "10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {props.running ? <Badge severity="normal" dot pulse>Đang chạy</Badge> : props.paused ? <Badge severity="warning">Tạm dừng</Badge> : <Badge severity="offline">Nhàn rỗi</Badge>}
          <span style={{ color: "var(--text-secondary)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>{props.sessionId ?? "chưa-có-phiên"}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {!props.running && !props.paused ? (
            <Button variant="primary" leftIcon={<Play size={14} />} onClick={props.onStart} disabled={!props.hasSession}>
              Bắt đầu
            </Button>
          ) : null}
          {props.running ? (
            <Button variant="secondary" leftIcon={<Pause size={14} />} onClick={props.onPause}>
              Tạm dừng
            </Button>
          ) : null}
          {props.paused ? (
            <Button variant="secondary" leftIcon={<Play size={14} />} onClick={props.onResume}>
              Tiếp tục
            </Button>
          ) : null}
          {(props.running || props.paused) ? (
            <Button variant="danger" leftIcon={<Square size={14} />} onClick={props.onStop}>
              Dừng
            </Button>
          ) : null}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>Chu kỳ phát tín hiệu</span>
        {[5, 15, 30, 60].map((value) => (
          <Button
            key={value}
            size="sm"
            variant={props.speed === value ? "primary" : "secondary"}
            onClick={() => props.onSpeedChange(value as 5 | 15 | 30 | 60)}
          >
            {value}s
          </Button>
        ))}
      </div>
    </div>
  );
}
