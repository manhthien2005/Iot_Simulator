import { useQuery } from "@tanstack/react-query";
import { fetchUserPersonalization } from "../services/personalizationApi";
import type { PersonalizationPayload } from "../types/personalization";

// ---------------------------------------------------------------------------
// usePersonalization — fetch the personalization payload for a user.
//
// Disabled when no userId or userId <= 0. 30s stale time matches the
// rate at which baselines evolve (cron runs once a day; demo trigger
// changes the picture immediately so a 30s window is generous).
// ---------------------------------------------------------------------------

export function usePersonalization(userId: number | null) {
  return useQuery<PersonalizationPayload>({
    queryKey: ["personalization", userId],
    queryFn: () => fetchUserPersonalization(userId as number),
    enabled: typeof userId === "number" && userId > 0,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: 1,
  });
}
