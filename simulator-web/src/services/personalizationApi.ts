import type { PersonalizationPayload } from "../types/personalization";
import { apiClient } from "./api";

// ---------------------------------------------------------------------------
// personalizationApi — read-only fetcher for the sim web "Personalization
// Status" card.
//
// Endpoint: GET /api/v1/sim/admin/users/{user_id}/personalization
// Backed by api_server proxy that calls the health_system backend
// (FastAPI) so sim web does not need a direct connection.
// ---------------------------------------------------------------------------

export async function fetchUserPersonalization(
  userId: number,
): Promise<PersonalizationPayload> {
  const response = await apiClient.get<PersonalizationPayload>(
    `/api/v1/sim/admin/users/${userId}/personalization`,
  );
  return response.data;
}
