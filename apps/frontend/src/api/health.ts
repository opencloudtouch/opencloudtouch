/**
 * Health API Client
 * Fetches application version and status from the /health endpoint
 */

export interface HealthResponse {
  status: string;
  version: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/health");
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json() as Promise<HealthResponse>;
}
