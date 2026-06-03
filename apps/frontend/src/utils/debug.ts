/**
 * Debug logging utility for SSE/WebSocket event tracing.
 *
 * Tied to the backend log level set in Settings → Logging.
 * When DEBUG is selected there, frontend debug logging is also enabled.
 *
 * Manual override in browser console:  `globalThis.__OCT_DEBUG__ = true`
 */

declare global {
  // eslint-disable-next-line no-var
  var __OCT_DEBUG__: boolean;
}

// Initialize from localStorage so it persists across page reloads
if (globalThis.window !== undefined) {
  globalThis.__OCT_DEBUG__ = localStorage.getItem("oct_debug") === "true";

  // Watch for changes so `globalThis.__OCT_DEBUG__ = true` also persists
  let _debugValue = globalThis.__OCT_DEBUG__;
  Object.defineProperty(globalThis, "__OCT_DEBUG__", {
    get: () => _debugValue,
    set: (v: boolean) => {
      _debugValue = !!v;
      localStorage.setItem("oct_debug", String(_debugValue));
    },
    configurable: true,
  });
}

/**
 * Sync frontend debug flag from backend log level.
 * Called by Settings when user changes log level.
 */
export function syncDebugFromBackendLevel(level: string): void {
  if (globalThis.window !== undefined) {
    globalThis.__OCT_DEBUG__ = level === "DEBUG";
  }
}

/**
 * Initialize debug state from backend on app startup.
 */
export async function initDebugFromBackend(): Promise<void> {
  try {
    const res = await fetch("/api/logs/level");
    if (res.ok) {
      const data = (await res.json()) as { level: string };
      syncDebugFromBackendLevel(data.level);
    }
  } catch {
    // Silently fail — debug stays off
  }
}

/**
 * Log a debug message if debug is enabled.
 * Usage: `octDebug("useNowPlaying", "incoming event", data)`
 */
export function octDebug(tag: string, message: string, ...args: unknown[]): void {
  if (globalThis.window !== undefined && globalThis.__OCT_DEBUG__) {
    console.debug(`[${tag}]`, message, ...args);
  }
}
