import { useQuery } from "@tanstack/react-query";
import { fetchDbDevices, fetchDevices } from "../services/deviceApi";
import type { DbDevice } from "../types/device";

export function useDevices(refetchInterval = Number(import.meta.env.VITE_POLL_INTERVAL_DEVICES ?? 5000)) {
  return useQuery({
    queryKey: ["devices"],
    queryFn: fetchDevices,
    refetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
}

/**
 * Hook lấy toàn bộ DB devices, enriched với is_sim_running.
 * Polling mỗi 5s để badge "Đang Sim" cập nhật realtime khi bật/tắt sim.
 */
export function useDbDevices(refetchInterval = 5_000) {
  return useQuery<DbDevice[]>({
    queryKey: ["db-devices"],
    queryFn: fetchDbDevices,
    refetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
}
