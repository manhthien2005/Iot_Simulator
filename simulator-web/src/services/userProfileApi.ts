import type { UserProfile } from "../types/userProfile";
import { apiClient } from "./api";

// ---------------------------------------------------------------------------
// userProfileApi — admin-side user profile fetcher.
//
// The Session page calls this once when the operator picks a device that
// has a `user_id` assigned, so the profile card can render demographics +
// medical info without chaining requests.  Backed by
// GET /api/v1/sim/admin/users/{user_id}/profile (Module: session page redesign).
// ---------------------------------------------------------------------------

export async function fetchUserProfile(userId: number): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>(`/api/v1/sim/admin/users/${userId}/profile`);
  return response.data;
}
