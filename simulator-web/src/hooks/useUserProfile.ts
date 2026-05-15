import { useQuery } from "@tanstack/react-query";
import { fetchUserProfile } from "../services/userProfileApi";
import type { UserProfile } from "../types/userProfile";

// ---------------------------------------------------------------------------
// useUserProfile — fetch a single user's full profile by id.
//
// Pass `null` when no device is selected (or when the selected device has
// no bound user); the query stays disabled in that case so we don't spam
// the BE with `userId=undefined`-style requests.  Profile data changes
// rarely so we cache for 60s and skip background refetches.
// ---------------------------------------------------------------------------

export function useUserProfile(userId: number | null) {
  return useQuery<UserProfile>({
    queryKey: ["user-profile", userId],
    queryFn: () => fetchUserProfile(userId as number),
    enabled: typeof userId === "number" && userId > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
}
