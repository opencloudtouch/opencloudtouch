/**
 * TDD tests for the Discover Button feature in the Settings page.
 * Written BEFORE implementation (RED phase).
 *
 * Feature requirements:
 * - Discover button visible only when manualIPs.length >= 1
 * - Button disabled while discovery is running
 * - On completion: toast with count of NEW devices (not pre-existing ones)
 * - Singular vs. plural phrasing in toast message
 */
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import Settings from "../../src/pages/Settings";
import { ToastProvider } from "../../src/contexts/ToastContext";
import type { DiscoveryState } from "../../src/hooks/useDiscoveryStream";

// ---------------------------------------------------------------------------
// Module-level mock — isolated to this file
// ---------------------------------------------------------------------------
vi.mock("../../src/hooks/useDiscoveryStream", () => ({
  useDiscoveryStream: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function makeDiscoveryState(overrides: Partial<DiscoveryState> = {}): DiscoveryState {
  return {
    isDiscovering: false,
    devicesFound: [],
    completed: false,
    error: null,
    stats: { discovered: 0, synced: 0, failed: 0 },
    ...overrides,
  };
}

function buildQueryClient(initialDevices: { device_id: string; ip: string }[] = []) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  if (initialDevices.length > 0) {
    qc.setQueryData(["devices"], initialDevices);
  }
  return qc;
}

function Wrapper({ qc, children }: { qc: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

function renderSettings(
  initialDevices: { device_id: string; ip: string }[] = [],
  qc?: QueryClient
) {
  const client = qc ?? buildQueryClient(initialDevices);
  return render(
    <Wrapper qc={client}>
      <Settings />
    </Wrapper>
  );
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------
let mockFetch: Mock;
let mockStartDiscovery: Mock;

beforeEach(async () => {
  mockFetch = vi.fn();
  vi.stubGlobal("fetch", mockFetch);
  mockStartDiscovery = vi.fn();

  const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
  (useDiscoveryStream as Mock).mockReturnValue({
    ...makeDiscoveryState(),
    startDiscovery: mockStartDiscovery,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  vi.resetAllMocks();
});

// ---------------------------------------------------------------------------
// Visibility
// ---------------------------------------------------------------------------
describe("Settings — Discover Button visibility", () => {
  it("does NOT show discover button when IP list is empty", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: [] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("No manual IPs configured")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /gerät(e)? such|discover/i })).toBeNull();
  });

  it("shows discover button when at least 1 IP is configured", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });
  });

  it("shows discover button for multiple IPs", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20", "192.168.1.30"] }),
    });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });
  });

  it("shows discover button even if those IPs match already-known devices", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings([{ device_id: "AAA", ip: "192.168.1.10" }]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Trigger
// ---------------------------------------------------------------------------
describe("Settings — Discover Button trigger", () => {
  it("calls startDiscovery when button is clicked", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /gerät(e)? such|discover/i }));

    expect(mockStartDiscovery).toHaveBeenCalledTimes(1);
  });

  it("button is enabled when discovery is idle and IPs are present", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).not.toBeDisabled();
    });
  });

  it("button is disabled while discovery is running", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: true }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Page reload during discovery
// ---------------------------------------------------------------------------
describe("Settings — Discover Button on page reload", () => {
  it("button is disabled on mount if discovery already running (page reload)", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: true }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeDisabled();
    });
  });

  it("button becomes enabled once discovery completes after page reload", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");

    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: true }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    const qc = buildQueryClient();
    const { rerender } = render(<Wrapper qc={qc}><Settings /></Wrapper>);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeDisabled();
    });

    // Discovery finishes — update mock and force re-render with same QueryClient
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: false }),
      startDiscovery: mockStartDiscovery,
    });
    rerender(<Wrapper qc={qc}><Settings /></Wrapper>);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).not.toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Completion toast — new device counting
// ---------------------------------------------------------------------------
describe("Settings — Discover Button completion toast", () => {
  it("shows '0 new devices found' when all discovered devices were already known", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [{ device_id: "AAA", ip: "192.168.1.10", name: "TV", model: "ST300", firmware: "1.0" }],
      }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings([{ device_id: "AAA", ip: "192.168.1.10" }]);

    await waitFor(() => {
      expect(screen.getByText(/0 new devices found/i)).toBeInTheDocument();
    });
  });

  it("shows '3 new devices found' when 3 new devices discovered, no pre-existing", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [
          { device_id: "NEW1", ip: "192.168.1.11", name: "A", model: "ST10", firmware: "1.0" },
          { device_id: "NEW2", ip: "192.168.1.12", name: "B", model: "ST10", firmware: "1.0" },
          { device_id: "NEW3", ip: "192.168.1.13", name: "C", model: "ST10", firmware: "1.0" },
        ],
      }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.11", "192.168.1.12", "192.168.1.13"] }),
    });

    renderSettings([]);

    await waitFor(() => {
      expect(screen.getByText(/3 new devices found/i)).toBeInTheDocument();
    });
  });

  it("counts only NEW devices in mix of known and unknown (expects '2 new devices')", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [
          { device_id: "KNOWN1", ip: "192.168.1.10", name: "Alt", model: "ST10", firmware: "1.0" },
          { device_id: "NEW1", ip: "192.168.1.20", name: "Neu1", model: "ST10", firmware: "1.0" },
          { device_id: "NEW2", ip: "192.168.1.30", name: "Neu2", model: "ST10", firmware: "1.0" },
        ],
      }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20", "192.168.1.30"] }),
    });

    renderSettings([{ device_id: "KNOWN1", ip: "192.168.1.10" }]);

    await waitFor(() => {
      expect(screen.getByText(/2 new devices found/i)).toBeInTheDocument();
    });
  });

  it("shows singular '1 new device found' for exactly 1 new device", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [
          { device_id: "KNOWN1", ip: "192.168.1.10", name: "Alt", model: "ST10", firmware: "1.0" },
          { device_id: "NEW1", ip: "192.168.1.20", name: "Neu", model: "ST10", firmware: "1.0" },
        ],
      }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    renderSettings([{ device_id: "KNOWN1", ip: "192.168.1.10" }]);

    await waitFor(() => {
      expect(screen.getByText(/1 new device found/i)).toBeInTheDocument();
    });
  });

  it("does NOT show completion toast when discovery is still idle (not completed)", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings([]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });

    expect(screen.queryByText(/new devices found/i)).toBeNull();
    expect(screen.queryByText(/new device found/i)).toBeNull();
  });

  it("does NOT show completion toast when discovery errored (no completed flag)", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ completed: false, error: "Connection lost" }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: ["192.168.1.10"] }) });

    renderSettings([]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });

    expect(screen.queryByText(/new devices found/i)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Edge cases — existing devices in cache
// ---------------------------------------------------------------------------
describe("Settings — Discover Button with existing devices", () => {
  it("shows '0 new devices found' when all discovered match pre-existing in DB", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [
          { device_id: "A", ip: "192.168.1.10", name: "A", model: "ST10", firmware: "1.0" },
          { device_id: "B", ip: "192.168.1.20", name: "B", model: "ST10", firmware: "1.0" },
        ],
      }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    renderSettings([
      { device_id: "A", ip: "192.168.1.10" },
      { device_id: "B", ip: "192.168.1.20" },
    ]);

    await waitFor(() => {
      expect(screen.getByText(/0 new devices found/i)).toBeInTheDocument();
    });
  });

  it("button is visible even if all configured IPs match known device IPs", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    renderSettings([
      { device_id: "A", ip: "192.168.1.10" },
      { device_id: "B", ip: "192.168.1.20" },
    ]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /gerät(e)? such|discover/i })).toBeInTheDocument();
    });
  });
});
