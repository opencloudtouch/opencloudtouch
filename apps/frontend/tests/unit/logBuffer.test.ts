/**
 * Tests for the frontend log buffer utility
 */
import { describe, it, expect, vi } from "vitest";
import {
  getLogEntries,
  getLogEntriesByDomain,
  initLogBuffer,
} from "../../src/utils/logBuffer";

describe("logBuffer", () => {
  it("captures console.warn output with correct timestamp/level/message shape, and getLogEntries returns a fresh copy each call", () => {
    initLogBuffer();

    // Force an entry to actually exist by producing a log via the patched console.
    const uniqueMessage = `test-log-entry-unique-string-${Date.now()}`;
    console.warn(uniqueMessage);

    const entries = getLogEntries();
    const entry = entries.find((e) => e.message === uniqueMessage);

    // Unconditional — no `if` guard. If the entry isn't there, this test must fail.
    expect(entry).toBeDefined();
    expect(entry).toMatchObject({
      level: "WARN",
      message: uniqueMessage,
    });
    // timestamp must be a valid ISO-8601 string (as produced by new Date().toISOString())
    expect(typeof entry!.timestamp).toBe("string");
    expect(new Date(entry!.timestamp).toISOString()).toBe(entry!.timestamp);

    // getLogEntries returns a copy (not the internal array) — folded in from the
    // now-redundant standalone "returns a copy" test.
    expect(getLogEntries()).not.toBe(getLogEntries());
  });

  it("routes a [SSE]-tagged debug message to the events domain", () => {
    initLogBuffer();
    const uniqueMessage = `sse-tagged-${Date.now()}-${Math.random()}`;
    console.debug("[SSE]", uniqueMessage);

    const events = getLogEntriesByDomain("events");
    expect(events.some((e) => e.message.includes(uniqueMessage))).toBe(true);
  });

  it("routes a bracketed-but-unrecognized tag to the app domain", () => {
    initLogBuffer();
    const uniqueMessage = `unrecognized-tag-${Date.now()}-${Math.random()}`;
    console.debug("[SomeUnknownTag]", uniqueMessage);

    const app = getLogEntriesByDomain("app");
    expect(app.some((e) => e.message.includes(uniqueMessage))).toBe(true);
  });

  it("routes a debug message with no bracketed tag at all to the app domain", () => {
    initLogBuffer();
    const uniqueMessage = `no-brackets-here-${Date.now()}-${Math.random()}`;
    console.debug(uniqueMessage);

    const app = getLogEntriesByDomain("app");
    expect(app.some((e) => e.message.includes(uniqueMessage))).toBe(true);
  });

  it("routes a debug message with a non-string first argument to the app domain", () => {
    initLogBuffer();
    const marker = Date.now();
    console.debug(marker, "non-string-first-arg");

    const app = getLogEntriesByDomain("app");
    expect(
      app.some((e) => e.message.includes(String(marker)) && e.message.includes("non-string-first-arg")),
    ).toBe(true);
  });

  it("JSON-stringifies non-string console.log arguments instead of using them raw", () => {
    initLogBuffer();
    const marker = `json-stringify-marker-${Date.now()}`;
    console.log({ marker, nested: { ok: true } });

    const entries = getLogEntries();
    const entry = entries.find((e) => e.message.includes(marker));
    expect(entry).toBeDefined();
    // Proves JSON.stringify ran (not String(obj), which would produce "[object Object]").
    expect(entry!.message).toContain(`"marker":"${marker}"`);
    expect(entry!.message).toContain('"nested":{"ok":true}');
  });

  it("returns entries from both domains merged in chronological order, not buffer-insertion order", () => {
    initLogBuffer();
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-01-01T00:00:00.000Z"));
      const earlierMessage = `chronological-earlier-${Math.random()}`;
      // Pushed into the "events" buffer, which is concatenated AFTER "app" in
      // getLogEntries's `[...buffers.app, ...buffers.events]` — so without a
      // real sort, this earlier-timestamped entry would appear AFTER the
      // later-timestamped app entry below. Only a working sort fixes the order.
      console.debug("[SSE]", earlierMessage);

      vi.setSystemTime(new Date("2026-01-01T00:00:10.000Z"));
      const laterMessage = `chronological-later-${Math.random()}`;
      console.warn(laterMessage);

      const entries = getLogEntries();
      const earlierIndex = entries.findIndex((e) => e.message.includes(earlierMessage));
      const laterIndex = entries.findIndex((e) => e.message.includes(laterMessage));

      expect(earlierIndex).toBeGreaterThanOrEqual(0);
      expect(laterIndex).toBeGreaterThanOrEqual(0);
      expect(earlierIndex).toBeLessThan(laterIndex);
    } finally {
      vi.useRealTimers();
    }
  });

  it("drops the oldest app entry once the 1000-entry ring buffer overflows", () => {
    initLogBuffer();
    for (let i = 0; i < 1001; i++) {
      console.log(`overflow-marker-${i}`);
    }

    const app = getLogEntriesByDomain("app");
    expect(app).toHaveLength(1000);
    expect(app.some((e) => e.message === "overflow-marker-0")).toBe(false);
    expect(app.some((e) => e.message === "overflow-marker-1000")).toBe(true);
  });
});
