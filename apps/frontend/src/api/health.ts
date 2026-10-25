/**
 * Health API Client
 * Fetches application version and status from the /health endpoint
 */

export interface HealthResponse {
  status: string;
  version: string;
  /** "official" for signed CI builds, "community" for self-built/local-dev. */
  build: "official" | "community";
  /** Seconds since start; optional, the current /health payload does not send it. */
  uptime?: number;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/health");
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json() as Promise<HealthResponse>;
}
