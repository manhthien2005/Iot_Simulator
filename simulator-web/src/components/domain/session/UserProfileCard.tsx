import { useState } from "react";
import { AlertTriangle, Heart, Pill } from "lucide-react";
import { Card } from "../../ui/Card";
import { Skeleton } from "../../ui/Skeleton";
import type { UserProfile } from "../../../types/userProfile";

// ---------------------------------------------------------------------------
// UserProfileCard — hero-card layout.
//
// Section 1 (hero)   : avatar + name + age / gender / phone inline.
// Section 2 (metrics): email · DOB · height · weight · blood type in a
//                      responsive pill grid.
// Section 3 (medical): 3-column grid — conditions | medications | allergies.
//
// Rationale for the redesign:
//   • The previous 2-column flat list had no visual hierarchy — every row
//     looked equally important.
//   • Healthcare UIs work best with a clear hero (identity) → summary
//     (vitals) → details (clinical) progression.
//   • Metric pills and a 3-col medical grid use horizontal space properly
//     without the "form" feeling that borders created.
// ---------------------------------------------------------------------------

interface UserProfileCardProps {
  profile: UserProfile | undefined;
  isLoading: boolean;
  error: Error | null;
}

export function UserProfileCard({ profile, isLoading, error }: UserProfileCardProps) {
  if (isLoading) {
    return <Card><ProfileSkeleton /></Card>;
  }

  if (error) {
    return (
      <Card>
        <div style={{ padding: "12px", borderRadius: "var(--radius-md)", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.24)", color: "var(--severity-critical)", fontSize: "13px" }}>
          Không tải được hồ sơ: {error.message}
        </div>
      </Card>
    );
  }

  if (!profile) {
    return (
      <Card>
        <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: "13px" }}>
          Thiết bị này chưa được gán cho người dùng nào.
        </p>
      </Card>
    );
  }

  const age = computeAge(profile.date_of_birth);
  const initials = getInitials(profile.full_name);
  const fallbackBg = AVATAR_COLORS[profile.id % AVATAR_COLORS.length];

  const heroSubtitle = [
    age != null ? `${age} tuổi` : null,
    profile.gender ? translateGender(profile.gender) : null,
    profile.phone ?? null,
  ].filter(Boolean).join("  ·  ");

  return (
    <Card>
      <div style={{ display: "grid", gap: "16px" }}>

        {/* ── Section 1: Hero ─────────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <ProfileAvatar avatarUrl={profile.avatar_url} initials={initials} fallbackBg={fallbackBg} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.01em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {profile.full_name || "Chưa có tên"}
            </div>
            {heroSubtitle ? (
              <div style={{ marginTop: "4px", fontSize: "13px", color: "var(--text-secondary)" }}>
                {heroSubtitle}
              </div>
            ) : null}
          </div>
        </div>

        {/* ── Section 2: Metric pills ──────────────────────────────── */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: "8px",
          }}
        >
          <MetricPill label="Email" value={profile.email} mono />
          <MetricPill label="Ngày sinh" value={formatDate(profile.date_of_birth)} />
          <MetricPill label="Chiều cao" value={profile.height_cm != null ? `${profile.height_cm} cm` : "—"} />
          <MetricPill label="Cân nặng" value={profile.weight_kg != null ? `${profile.weight_kg} kg` : "—"} />
          <MetricPill label="Nhóm máu" value={profile.blood_type ?? "—"} accent={Boolean(profile.blood_type)} />
        </div>

        {/* ── Section 3: Medical 3-col ─────────────────────────────── */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: "8px",
          }}
        >
          <MedicalPill
            icon={<Heart size={12} strokeWidth={2} />}
            label="Bệnh nền"
            items={profile.medical_conditions}
            emptyText="Chưa ghi nhận."
            color="var(--severity-critical)"
            bg="rgba(239,68,68,0.06)"
          />
          <MedicalPill
            icon={<Pill size={12} strokeWidth={2} />}
            label="Đang dùng thuốc"
            items={profile.medications}
            emptyText="Không có."
            color="var(--accent-cyan)"
            bg="rgba(6,182,212,0.06)"
          />
          <MedicalPill
            icon={<AlertTriangle size={12} strokeWidth={2} />}
            label="Dị ứng"
            items={profile.allergies}
            emptyText="Không có."
            color="var(--severity-warning)"
            bg="rgba(245,158,11,0.06)"
          />
        </div>

      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// MetricPill — compact labelled value chip for the summary row.
// ---------------------------------------------------------------------------

function MetricPill({ label, value, mono = false, accent = false }: {
  label: string;
  value: string;
  mono?: boolean;
  accent?: boolean;
}) {
  return (
    <div
      style={{
        padding: "8px 12px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-elevated)",
        display: "grid",
        gap: "3px",
        minWidth: 0,
      }}
    >
      <span style={{ fontSize: "10.5px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)" }}>
        {label}
      </span>
      <span
        style={{
          fontSize: "13px",
          fontWeight: 600,
          color: accent ? "var(--accent-cyan)" : "var(--text-primary)",
          fontFamily: mono ? "var(--font-mono)" : undefined,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MedicalPill — one of the 3 clinical columns.
// Shows a colored header + chip list or muted italic empty-state.
// ---------------------------------------------------------------------------

function MedicalPill({ icon, label, items, emptyText, color, bg }: {
  icon: React.ReactNode;
  label: string;
  items: string[];
  emptyText: string;
  color: string;
  bg: string;
}) {
  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: "var(--radius-md)",
        background: bg,
        border: `1px solid color-mix(in srgb, ${color} 20%, transparent)`,
        display: "grid",
        gap: "6px",
        alignContent: "start",
        minWidth: 0,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "5px", color, fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em" }}>
        {icon}
        {label}
      </div>

      {/* Content */}
      {items.length === 0 ? (
        <span style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
          {emptyText}
        </span>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
          {items.map((item) => (
            <span
              key={item}
              style={{
                padding: "2px 8px",
                borderRadius: "var(--radius-full)",
                background: "rgba(255,255,255,0.06)",
                color: "var(--text-primary)",
                fontSize: "11.5px",
                fontWeight: 500,
              }}
            >
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProfileAvatar — loads Supabase public URL, falls back to initials.
// ---------------------------------------------------------------------------

function ProfileAvatar({ avatarUrl, initials, fallbackBg }: {
  avatarUrl: string | null;
  initials: string;
  fallbackBg: string;
}) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(avatarUrl?.trim()) && !failed;

  return (
    <div
      style={{
        width: "56px",
        height: "56px",
        borderRadius: "50%",
        overflow: "hidden",
        background: fallbackBg,
        display: "grid",
        placeItems: "center",
        fontSize: "20px",
        fontWeight: 700,
        color: "#fff",
        flexShrink: 0,
      }}
    >
      {showImage ? (
        <img
          src={avatarUrl as string}
          alt="Avatar"
          width={56}
          height={56}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => setFailed(true)}
        />
      ) : (
        initials
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function ProfileSkeleton() {
  return (
    <div style={{ display: "grid", gap: "14px" }}>
      <div style={{ display: "flex", gap: "14px", alignItems: "center" }}>
        <Skeleton style={{ width: "56px", height: "56px", borderRadius: "50%" }} />
        <div style={{ display: "grid", gap: "6px", flex: 1 }}>
          <Skeleton style={{ width: "40%", height: "18px" }} />
          <Skeleton style={{ width: "60%", height: "13px" }} />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px,1fr))", gap: "8px" }}>
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} style={{ height: "48px" }} />)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "8px" }}>
        {[0, 1, 2].map((i) => <Skeleton key={i} style={{ height: "64px" }} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pure utilities
// ---------------------------------------------------------------------------

const AVATAR_COLORS = ["#06b6d4", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#3b82f6"];

function getInitials(fullName: string | null): string {
  if (!fullName) return "?";
  const tokens = fullName.trim().split(/\s+/);
  if (tokens.length === 1) return tokens[0].charAt(0).toUpperCase();
  return (tokens[0].charAt(0) + tokens[tokens.length - 1].charAt(0)).toUpperCase();
}

function computeAge(dob: string | null): number | null {
  if (!dob) return null;
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const m = now.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}/${date.getFullYear()}`;
}

function translateGender(value: string | null): string {
  if (!value) return "—";
  const v = value.toLowerCase();
  if (v === "male") return "Nam";
  if (v === "female") return "Nữ";
  if (v === "other") return "Khác";
  return value;
}
