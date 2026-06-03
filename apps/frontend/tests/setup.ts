import { afterEach, beforeAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import "../src/i18n";

// Mock EventSource (not available in jsdom) – use direct global assignment so
// it survives vi.unstubAllGlobals() calls in individual test files.
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = MockEventSource.CONNECTING;
  url = "";
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  dispatchEvent = vi.fn();
  close = vi.fn(() => { this.readyState = MockEventSource.CLOSED; });
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  constructor(url: string) { this.url = url; }
}
(global as Record<string, unknown>).EventSource = MockEventSource;

// Mock ResizeObserver (not available in jsdom)
class MockResizeObserver {
  constructor(_callback: ResizeObserverCallback) {}
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
(global as Record<string, unknown>).ResizeObserver = MockResizeObserver;

// Mock react-router-dom to avoid Router context issues in tests
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({}),
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
    useLocation: () => ({ pathname: "/", search: "", hash: "", state: null }),
  };
});

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
