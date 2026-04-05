import { useQuery } from "@tanstack/react-query";
import { fetchDbDevices, fetchDevices } from "../services/deviceApi";
import type { DbDevice } from "../types/device";
import { POLL_INTERVALS } from "../config/defaults";

export function useDevices(refetchInterval = Number(import.meta.env.VITE_POLL_INTERVAL_DEVICES) || POLL_INTERVALS.devices) {
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
export function useDbDevices(refetchInterval = POLL_INTERVALS.dbDevices) {
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
