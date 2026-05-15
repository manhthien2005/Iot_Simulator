// ---------------------------------------------------------------------------
// UserProfile — shape returned by GET /api/sim/admin/users/{user_id}/profile.
//
// Mirrors the `AdminUserProfileResponse` Pydantic model in
// `api_server/schemas.py`.  Used by the Session page profile card to render
// demographics, medical info, and emergency contacts for the selected
// device's bound user.
// ---------------------------------------------------------------------------

export interface EmergencyContact {
  id: number;
  name: string;
  phone: string;
  relationship: string | null;
  priority: number;
}

export interface UserProfile {
  // Identity
  id: number;
  email: string;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;

  // Demographics
  date_of_birth: string | null; // ISO date "YYYY-MM-DD"
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;

  // Medical
  blood_type: string | null;
  medical_conditions: string[];
  medications: string[];
  allergies: string[];

  // Emergency contacts
  emergency_contacts: EmergencyContact[];
}
