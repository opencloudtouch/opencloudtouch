/**
 * React Query hooks for settings management
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getManualIPs, setManualIPs, deleteManualIP } from "../api/settings";

/**
 * Fetch manual IP configuration
 */
export function useManualIPs() {
  return useQuery<string[]>({
    queryKey: ["manual-ips"],
    queryFn: getManualIPs,
  });
}

/**
 * Set manual IPs (replaces all) - for bulk operations
 * Use addManualIP helper function for adding single IPs
 */
export function useSetManualIPs() {
  const queryClient = useQueryClient();

  return useMutation<string[], Error, string[]>({
    mutationFn: setManualIPs,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["manual-ips"] });
    },
  });
}

/**
 * Add single manual IP (helper using setManualIPs under the hood)
 */
export function useAddManualIP() {
  const queryClient = useQueryClient();

  return useMutation<string[], Error, string>({
    mutationFn: async (ip: string) => {
      // Get current IPs
      const currentIPs = queryClient.getQueryData<string[]>(["manual-ips"]) || [];
      // Add new IP if not already present
      if (!currentIPs.includes(ip)) {
        const newIPs = [...currentIPs, ip];
        return await setManualIPs(newIPs);
      }
      return currentIPs;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["manual-ips"] });
    },
  });
}

/**
 * Delete manual IP mutation with automatic cache invalidation
 */
export function useDeleteManualIP() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteManualIP,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["manual-ips"] });
    },
  });
}
