/**
 * Frontend Log Buffer
 * Captures console.log/warn/error for inclusion in bug reports.
 */

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

const MAX_ENTRIES = 100;
const entries: LogEntry[] = [];

let initialized = false;

export function initLogBuffer(): void {
  if (initialized) return;
  initialized = true;

  const origLog = console.log;
  const origWarn = console.warn;
  const origError = console.error;

  const capture = (level: string, orig: (...args: unknown[]) => void) => {
    return (...args: unknown[]) => {
      orig.apply(console, args);
      const message = args.map((a) => (typeof a === "string" ? a : JSON.stringify(a))).join(" ");
      entries.push({
        timestamp: new Date().toISOString(),
        level,
        message: message.slice(0, 500),
      });
      if (entries.length > MAX_ENTRIES) entries.shift();
    };
  };

  console.log = capture("LOG", origLog);
  console.warn = capture("WARN", origWarn);
  console.error = capture("ERROR", origError);
}

export function getLogEntries(): LogEntry[] {
  return [...entries];
}
