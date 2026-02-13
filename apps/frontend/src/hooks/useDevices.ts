/**
 * React Query hooks for device management
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDevices, syncDevices, getDeviceCapabilities } from "../api/devices";
import type { Device, SyncResult } from "../api/devices";

/**
 * Fetch all devices with automatic caching and refetching
 */
export function useDevices() {
  return useQuery<Device[]>({
    queryKey: ["devices"],
    queryFn: getDevices,
  });
}

/**
 * Sync devices mutation with automatic cache invalidation
 */
export function useSyncDevices() {
  const queryClient = useQueryClient();

  return useMutation<SyncResult, Error, void>({
    mutationFn: syncDevices,
    onSuccess: () => {
      // Invalidate and refetch devices after sync
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}

/**
 * Get device capabilities
 */
export function useDeviceCapabilities(deviceId: string | null) {
  return useQuery({
    queryKey: ["device-capabilities", deviceId],
    queryFn: () => getDeviceCapabilities(deviceId!),
    enabled: !!deviceId, // Only fetch if deviceId is provided
  });
}
