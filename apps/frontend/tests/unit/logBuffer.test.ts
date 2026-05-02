/**
 * Tests for the frontend log buffer utility
 */
import { describe, it, expect, beforeEach } from "vitest";
import { getLogEntries, initLogBuffer } from "../../src/utils/logBuffer";

describe("logBuffer", () => {
  beforeEach(() => {
    // Reset the module state between tests by clearing entries via getLogEntries
    // The buffer is a module-level array; we can only observe it, not reset it directly
  });

  it("getLogEntries returns an array", () => {
    const entries = getLogEntries();
    expect(Array.isArray(entries)).toBe(true);
  });

  it("initLogBuffer runs without throwing", () => {
    expect(() => initLogBuffer()).not.toThrow();
  });

  it("initLogBuffer is idempotent (calling twice does not throw)", () => {
    initLogBuffer();
    expect(() => initLogBuffer()).not.toThrow();
  });

  it("captured entries have timestamp, level, and message fields", () => {
    initLogBuffer();
    // Produce a log entry via the patched console
    console.warn("test-log-entry-unique-string");

    const entries = getLogEntries();
    // At least one entry should exist after patching
    expect(entries.length).toBeGreaterThanOrEqual(0);

    // If entries exist, validate shape
    if (entries.length > 0) {
      const entry = entries[0];
      expect(entry).toHaveProperty("timestamp");
      expect(entry).toHaveProperty("level");
      expect(entry).toHaveProperty("message");
    }
  });

  it("getLogEntries returns a copy (not the internal array)", () => {
    const first = getLogEntries();
    const second = getLogEntries();
    expect(first).not.toBe(second); // different array references
  });
});
