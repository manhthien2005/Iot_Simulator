import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/api";

export interface LinkedCaregiverItem {
  user_id: number;
  full_name: string | null;
  email: string;
  avatar_url: string | null;
  relationship_type: string;
  relationship_label: string | null;
  has_active_fcm_token: boolean;
}

export interface LinkedCaregiversResponse {
  patient_id: number;
  caregivers: LinkedCaregiverItem[];
}

async function fetchCaregivers(userId: number): Promise<LinkedCaregiversResponse> {
  const { data } = await apiClient.get<LinkedCaregiversResponse>(
    `/api/v1/sim/admin/users/${userId}/caregivers`
  );
  return data;
}

/** ADR-024 Phase 7 S16 — fetch accepted caregivers for a patient user. */
export function useCaregivers(userId: number | null) {
  return useQuery<LinkedCaregiversResponse>({
    queryKey: ["caregivers", userId],
    queryFn: () => fetchCaregivers(userId!),
    enabled: userId != null,
    staleTime: 30_000,
  });
}
