/**
 * TDD tests for the Scan Button feature in the Settings page.
 *
 * Feature requirements:
 * - Scan button always visible in the Automatic Search card
 * - Button disabled while discovery is running
 * - On completion: toast with count of NEW devices (not pre-existing ones)
 * - Singular vs. plural phrasing in toast message
 */
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
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
describe("Settings — Scan Button visibility", () => {
  it.each([
    { scenario: "IP list is empty", ips: [] as string[], devices: [] },
    { scenario: "IPs are configured", ips: ["192.168.1.10"], devices: [] },
    {
      scenario: "IPs match already-known devices",
      ips: ["192.168.1.10"],
      devices: [{ device_id: "AAA", ip: "192.168.1.10" }],
    },
    {
      scenario: "all configured IPs match known device IPs",
      ips: ["192.168.1.10", "192.168.1.20"],
      devices: [
        { device_id: "A", ip: "192.168.1.10" },
        { device_id: "B", ip: "192.168.1.20" },
      ],
    },
  ])("shows scan button even when $scenario", async ({ ips, devices }) => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips }) });

    renderSettings(devices);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /scan now/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Manual Discover Button visibility — REMOVED
// The manual discover button was replaced by direct probe on "+ Add".
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Trigger
// ---------------------------------------------------------------------------
describe("Settings — Scan Button trigger", () => {
  it("calls startDiscovery when button is clicked", async () => {
    mockFetch.mockImplementation(async (url: string) => ({
      ok: true,
      json: async () => (String(url).endsWith("/api/devices") ? { devices: [] } : { ips: [] }),
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /scan now/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /scan now/i }));

    await waitFor(() => expect(mockStartDiscovery).toHaveBeenCalledTimes(1));
  });

  it("reads the database again before a second scan", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");

    const databaseSnapshots = [
      { devices: [] },
      { devices: [{ device_id: "NEW1", name: "Kitchen" }] },
    ];
    let reads = 0;

    mockFetch.mockImplementation(async (url: string) => ({
      ok: true,
      json: async () => {
        if (String(url).endsWith("/api/devices")) {
          return databaseSnapshots[reads++];
        }
        return { ips: [] };
      },
    }));

    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState(),
      startDiscovery: mockStartDiscovery,
    });

    renderSettings();

    const button = await screen.findByRole("button", { name: /scan now/i });

    fireEvent.click(button);
    await waitFor(() => expect(mockStartDiscovery).toHaveBeenCalledTimes(1));

    fireEvent.click(button);
    await waitFor(() => expect(mockStartDiscovery).toHaveBeenCalledTimes(2));

    expect(reads).toBe(2);
  });

  it("does not list a device as new on the second scan", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");

    let dbDevices: { device_id: string; name: string }[] = [];
    mockFetch.mockImplementation(async (url: string) => ({
      ok: true,
      json: async () =>
        String(url).endsWith("/api/devices") ? { devices: dbDevices } : { ips: [] },
    }));

    const discoveryResult = {
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [{ device_id: "NEW1", name: "Kitchen" }],
      }),
      startDiscovery: mockStartDiscovery,
    };

    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState(),
      startDiscovery: mockStartDiscovery,
    });

    const qc = buildQueryClient();
    const { rerender } = render(
      <Wrapper qc={qc}>
        <Settings />
      </Wrapper>
    );

    const button = await screen.findByRole("button", { name: /scan now/i });

    fireEvent.click(button);
    await waitFor(() => expect(mockStartDiscovery).toHaveBeenCalledTimes(1));

    (useDiscoveryStream as Mock).mockReturnValue(discoveryResult);
    rerender(
      <Wrapper qc={qc}>
        <Settings />
      </Wrapper>
    );

    expect(await screen.findByText("Kitchen")).toBeInTheDocument();

    dbDevices = [{ device_id: "NEW1", name: "Kitchen" }];

    fireEvent.click(button);
    await waitFor(() => expect(mockStartDiscovery).toHaveBeenCalledTimes(2));

    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState(),
      startDiscovery: mockStartDiscovery,
    });
    rerender(
      <Wrapper qc={qc}>
        <Settings />
      </Wrapper>
    );

    (useDiscoveryStream as Mock).mockReturnValue(discoveryResult);
    rerender(
      <Wrapper qc={qc}>
        <Settings />
      </Wrapper>
    );

    await waitFor(() => {
      expect(screen.getByText(/0 new devices found/i, {
        selector: '[data-test="toast-message"]',
      })).toBeInTheDocument();
      expect(screen.queryByText("Kitchen")).not.toBeInTheDocument();
    });
  });

  it("prevents double clicks while preparing discovery", async () => {
    let resolveDevices!: (value: unknown) => void;
    const pendingDevices = new Promise<unknown>((resolve) => {
      resolveDevices = resolve;
    });
    let deviceRequests = 0;

    mockFetch.mockImplementation(async (url: string) => {
      if (String(url).endsWith("/api/devices")) {
        deviceRequests++;
        return pendingDevices;
      }
      return { ok: true, json: async () => ({ ips: [] }) };
    });

    renderSettings();
    const button = await screen.findByRole("button", { name: /scan now/i });

    fireEvent.click(button);
    fireEvent.click(button);

    expect(deviceRequests).toBe(1);
    expect(button).toBeDisabled();
    expect(mockStartDiscovery).not.toHaveBeenCalled();

    resolveDevices({ ok: true, json: async () => ({ devices: [] }) });

    await waitFor(() => {
      expect(mockStartDiscovery).toHaveBeenCalledTimes(1);
    });
  });

  it("does not start discovery if the page unmounts during the pre-scan read", async () => {
    let resolveDevices!: (value: unknown) => void;
    const pendingDevices = new Promise<unknown>((resolve) => {
      resolveDevices = resolve;
    });

    mockFetch.mockImplementation(async (url: string) => {
      if (String(url).endsWith("/api/devices")) return pendingDevices;
      return { ok: true, json: async () => ({ ips: [] }) };
    });

    const { unmount } = renderSettings();
    const button = await screen.findByRole("button", { name: /scan now/i });
    fireEvent.click(button);
    await waitFor(() => expect(button).toBeDisabled());

    unmount();
    await act(async () => {
      resolveDevices({ ok: true, json: async () => ({ devices: [] }) });
      await pendingDevices;
    });
    expect(mockStartDiscovery).not.toHaveBeenCalled();
  });

  it("button is disabled while discovery is running", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: true }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: [] }) });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /scan now/i })).toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Page reload during discovery
// ---------------------------------------------------------------------------
describe("Settings — Scan Button on page reload", () => {
  it("button becomes enabled once discovery completes after page reload", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");

    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: true }),
      startDiscovery: mockStartDiscovery,
    });

    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ips: [] }) });

    const qc = buildQueryClient();
    const { rerender } = render(<Wrapper qc={qc}><Settings /></Wrapper>);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /scan now/i })).toBeDisabled();
    });

    // Discovery finishes — update mock and force re-render with same QueryClient
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({ isDiscovering: false }),
      startDiscovery: mockStartDiscovery,
    });
    rerender(<Wrapper qc={qc}><Settings /></Wrapper>);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /scan now/i })).not.toBeDisabled();
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

  it("lists only newly synced devices, excluding previously known devices", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [
          { device_id: "OLD", name: "Already Known", ip: "192.168.1.10" },
          { device_id: "NEW", name: "Living Room", ip: "192.168.1.11" },
        ],
      }),
      startDiscovery: mockStartDiscovery,
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: [] }) });
    renderSettings([{ device_id: "OLD", ip: "192.168.1.10" }]);
    const list = await screen.findByRole("list");
    expect(list).toHaveTextContent("Living Room");
    expect(list).not.toHaveTextContent("Already Known");
  });

  it("shows no results list when all discovered devices are known", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [{ device_id: "OLD", name: "Known", ip: "192.168.1.10" }],
      }),
      startDiscovery: mockStartDiscovery,
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: [] }) });
    renderSettings([{ device_id: "OLD", ip: "192.168.1.10" }]);
    await screen.findByText(/0 new devices found/i);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("deduplicates repeated synced events by device ID", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: [
          { device_id: "NEW", name: "Kitchen" },
          { device_id: "NEW", name: "Kitchen" },
        ],
      }),
      startDiscovery: mockStartDiscovery,
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: [] }) });
    renderSettings();
    expect(await screen.findAllByText("Kitchen")).toHaveLength(1);
  });

  it.each([
    {
      scenario: "discovery is still idle (not completed)",
      setup: () => {},
    },
    {
      scenario: "discovery errored (no completed flag)",
      setup: async () => {
        const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
        (useDiscoveryStream as Mock).mockReturnValue({
          ...makeDiscoveryState({ completed: false, error: "Connection lost" }),
          startDiscovery: mockStartDiscovery,
        });
      },
    },
  ])("does NOT show completion toast when $scenario", async ({ setup }) => {
    await setup();
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ips: [] }) });

    renderSettings([]);

    await waitFor(() => {
      const button = screen.getByRole("button", { name: /scan now/i });
      expect(button).toBeInTheDocument();
      // Also covers the plain idle-render case: button starts out enabled.
      expect(button).not.toBeDisabled();
    });

    expect(screen.queryByText(/new devices found/i)).toBeNull();
    expect(screen.queryByText(/new device found/i)).toBeNull();
  });
});

describe("Settings — discovery review regressions", () => {
  it("aborts the scan if the pre-scan device fetch fails", async () => {
    mockFetch.mockImplementation(async (url: string) => {
      if (String(url).endsWith("/api/devices")) {
        throw new Error("Failed to fetch devices");
      }
      return { ok: true, json: async () => ({ ips: [] }) };
    });

    renderSettings();
    const button = await screen.findByRole("button", { name: /scan now/i });
    fireEvent.click(button);

    await waitFor(() => expect(button).not.toBeDisabled());
    expect(mockStartDiscovery).not.toHaveBeenCalled();
    expect(
      await screen.findByText(
        /Could not connect to the server\. Please check your network connection\./i
      )
    ).toBeInTheDocument();
  });

  it("keeps the expand button mounted and supports collapsing", async () => {
    const { useDiscoveryStream } = await import("../../src/hooks/useDiscoveryStream");
    (useDiscoveryStream as Mock).mockReturnValue({
      ...makeDiscoveryState({
        completed: true,
        devicesFound: Array.from({ length: 7 }, (_, i) => ({
          device_id: `NEW${i}`,
          name: `Device ${i}`,
        })),
      }),
      startDiscovery: mockStartDiscovery,
    });
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderSettings();
    const expand = await screen.findByRole("button", { name: /more/i });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    expect(screen.getAllByRole("listitem")).toHaveLength(5);

    fireEvent.click(expand);
    expect(expand).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("listitem")).toHaveLength(7);

    fireEvent.click(expand);
    expect(expand).toHaveAttribute("aria-expanded", "false");
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });
});
