/**
 * React Query hook for application health / version
 */
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../api/health";
import type { HealthResponse } from "../api/health";

const HEALTH_STALE_TIME = 5 * 60 * 1000;

export function useHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ["health"],
    queryFn: getHealth,
    staleTime: HEALTH_STALE_TIME,
    refetchOnWindowFocus: false,
  });
}
