import { afterEach, beforeAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Mock fetch with base URL for API calls
beforeAll(() => {
  vi.stubGlobal("fetch", vi.fn(() => {
    // Return mock response by default
    return Promise.resolve({
      ok: true,
      status: 200,
      json: async () => ({}),
      text: async () => "",
    });
  }));
});

// Cleanup after each test
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
