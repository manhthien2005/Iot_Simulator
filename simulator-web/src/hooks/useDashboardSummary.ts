import { useQuery } from "@tanstack/react-query";
import { fetchDashboardSummary } from "../services/dashboardApi";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: fetchDashboardSummary,
    refetchInterval: 5000,
  });
}

