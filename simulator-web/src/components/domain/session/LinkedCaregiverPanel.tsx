import type { LinkedCaregiverItem } from "../../../hooks/useCaregivers";

interface LinkedCaregiverPanelProps {
  caregivers: LinkedCaregiverItem[];
  isLoading: boolean;
}

/** ADR-024 Phase 7 S16 — compact list of accepted caregivers with FCM status. */
export function LinkedCaregiverPanel({ caregivers, isLoading }: LinkedCaregiverPanelProps) {
  if (isLoading) {
    return (
      <div style={{ fontSize: "13px", color: "var(--text-muted, #888)", padding: "8px 0" }}>
        Đang tải...
      </div>
    );
  }

  if (caregivers.length === 0) {
    return (
      <div style={{ fontSize: "13px", color: "var(--text-muted, #888)", padding: "8px 0" }}>
        Chưa có người thân được liên kết.
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: "8px" }}>
      {caregivers.map((c) => (
        <div
          key={c.user_id}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            padding: "10px 14px",
            background: "var(--surface-2, #f8f9fa)",
            border: "1px solid var(--border-color, #e0e0e0)",
            borderRadius: "8px",
          }}
        >
          {/* Avatar */}
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              background: "var(--border-color, #ccc)",
              flexShrink: 0,
              overflow: "hidden",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "15px",
              color: "var(--text-secondary, #555)",
            }}
          >
            {c.avatar_url ? (
              <img
                src={c.avatar_url}
                alt={c.full_name ?? c.email}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              (c.full_name ?? c.email).charAt(0).toUpperCase()
            )}
          </div>

          {/* Info */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "var(--text-primary, #222)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {c.full_name ?? c.email}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted, #888)" }}>
              {c.relationship_label ?? c.relationship_type}
            </div>
          </div>

          {/* FCM badge */}
          <div
            title={c.has_active_fcm_token ? "FCM token active" : "No active FCM token"}
            style={{
              fontSize: "11px",
              padding: "2px 8px",
              borderRadius: "4px",
              background: c.has_active_fcm_token
                ? "rgba(0,180,80,0.12)"
                : "rgba(200,50,50,0.10)",
              color: c.has_active_fcm_token ? "#00b450" : "#c83232",
              flexShrink: 0,
            }}
          >
            {c.has_active_fcm_token ? "● FCM" : "○ No FCM"}
          </div>
        </div>
      ))}
    </div>
  );
}
