import { useQuery } from "@tanstack/react-query";
import { fetchDashboardSummary } from "../services/dashboardApi";
import { POLL_INTERVALS } from "../config/defaults";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: fetchDashboardSummary,
    refetchInterval: POLL_INTERVALS.dashboard,
    refetchIntervalInBackground: false,
    retry: false,
  });
}
