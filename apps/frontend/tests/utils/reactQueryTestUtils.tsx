/**
 * Test utilities for React Query components
 * Provides QueryClient wrapper for testing
 */
import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Create a new QueryClient for testing
 * Disables retries and logging for faster tests
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries in tests
        gcTime: 0, // Disable cache in tests
      },
      mutations: {
        retry: false,
      },
    },
  });
}

/**
 * Wrapper component with QueryClientProvider for testing
 */
export function QueryWrapper({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient();
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

/**
 * Build a renderHook `wrapper` bound to a caller-supplied QueryClient, so the
 * test can read the client's cache back after interacting with the hook
 * (QueryWrapper above creates its own internal client, which isn't
 * observable from the outside). Kept in this .tsx file so plain .ts test
 * files can use it without needing JSX support themselves.
 */
export function createQueryWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}
