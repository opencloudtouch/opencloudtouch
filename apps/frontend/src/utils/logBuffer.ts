/**
 * Frontend Log Buffer — Multi-Ring-Buffer by domain.
 *
 * Separates logs into domain-specific ring buffers so high-volume
 * debug events (SSE, NowPlaying) don't overwrite valuable wizard
 * or error logs.
 *
 * Domains:
 *   "app"    — general console.log/warn/error (wizard, UI, lifecycle)
 *   "events" — SSE/WebSocket debug events (NowPlaying, Volume, Zones)
 *
 * Each buffer holds up to 10_000 entries (~2KB each = ~20MB worst case).
 */

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

type Domain = "app" | "events";

const BUFFER_LIMITS: Record<Domain, number> = {
  app: 1000,
  events: 10_000,
};

/** Tags from octDebug that route to "events" buffer */
const EVENT_TAGS = new Set(["SSE", "NowPlaying", "Volume", "Zones"]);

const buffers: Record<Domain, LogEntry[]> = {
  app: [],
  events: [],
};

function pushEntry(domain: Domain, entry: LogEntry): void {
  const buf = buffers[domain];
  buf.push(entry);
  if (buf.length > BUFFER_LIMITS[domain]) buf.shift();
}

function formatMessage(args: unknown[]): string {
  return args
    .map((a) => (typeof a === "string" ? a : JSON.stringify(a)))
    .join(" ")
    .slice(0, 500);
}

/** Classify a debug message by its tag prefix → domain */
function classifyDebug(args: unknown[]): Domain {
  const first = args[0];
  if (typeof first === "string") {
    // octDebug produces `[Tag]` as first arg
    const match = /^\[(\w+)]$/.exec(first);
    if (match?.[1] && EVENT_TAGS.has(match[1])) return "events";
  }
  return "app";
}

let initialized = false;

export function initLogBuffer(): void {
  if (initialized) return;
  initialized = true;

  const origLog = console.log;
  const origWarn = console.warn;
  const origError = console.error;
  const origDebug = console.debug;

  const captureApp = (level: string, orig: (...args: unknown[]) => void) => {
    return (...args: unknown[]) => {
      orig.apply(console, args);
      pushEntry("app", {
        timestamp: new Date().toISOString(),
        level,
        message: formatMessage(args),
      });
    };
  };

  console.log = captureApp("LOG", origLog);
  console.warn = captureApp("WARN", origWarn);
  console.error = captureApp("ERROR", origError);

  // Debug: route to domain based on tag
  console.debug = (...args: unknown[]) => {
    origDebug.apply(console, args);
    const domain = classifyDebug(args);
    pushEntry(domain, {
      timestamp: new Date().toISOString(),
      level: "DEBUG",
      message: formatMessage(args),
    });
  };
}

/** Get all log entries merged and sorted by timestamp. */
export function getLogEntries(): LogEntry[] {
  return [...buffers.app, ...buffers.events].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

/** Get entries from a specific domain buffer. */
export function getLogEntriesByDomain(domain: Domain): LogEntry[] {
  return [...buffers[domain]];
}

/** Get all buffers keyed by domain (for structured export). */
export function getLogBuffers(): Record<Domain, LogEntry[]> {
  return {
    app: [...buffers.app],
    events: [...buffers.events],
  };
}
