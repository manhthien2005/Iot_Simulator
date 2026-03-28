import { apiClient } from "./api";
import type { DashboardSummary } from "../types/dashboard";

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const response = await apiClient.get<DashboardSummary>("/api/sim/dashboard/summary");
  return response.data;
}

