import { useQuery } from "@tanstack/react-query";
import { fetchLatestVitals } from "../services/vitalsApi";

export function useVitalsStream(deviceId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["vitals", deviceId],
    queryFn: () => fetchLatestVitals(deviceId),
    refetchInterval: enabled ? Number(import.meta.env.VITE_POLL_INTERVAL_VITALS ?? 1000) : false,
    enabled: Boolean(deviceId) && enabled
  });
}

