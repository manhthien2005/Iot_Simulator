import { useQuery } from "@tanstack/react-query";
import { fetchDevices } from "../services/deviceApi";

export function useDevices(refetchInterval = Number(import.meta.env.VITE_POLL_INTERVAL_DEVICES ?? 5000)) {
  return useQuery({
    queryKey: ["devices"],
    queryFn: fetchDevices,
    refetchInterval,
  });
}

