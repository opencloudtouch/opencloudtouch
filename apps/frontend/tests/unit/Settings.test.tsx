import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Settings from "../../src/pages/Settings";
import { QueryWrapper } from "../utils/reactQueryTestUtils";
import { ToastProvider } from "../../src/contexts/ToastContext";

// Mock AboutSection to avoid extra fetch calls (health + devices) in Settings tests
vi.mock("../../src/components/AboutSection", () => ({
  default: () => null,
}));

// Create typed mock for fetch
let mockFetch: Mock;

const renderWithProviders = (component: React.ReactElement) => {
  return render(<QueryWrapper><ToastProvider>{component}</ToastProvider></QueryWrapper>);
};

describe("Settings Page", () => {
  beforeEach(() => {
    mockFetch = vi.fn();
    // Wrap fetch so /api/logs/level is always handled transparently
    // without consuming sequential mockResolvedValueOnce entries.
    vi.stubGlobal("fetch", (...args: unknown[]) => {
      const url = args[0] as string;
      if (url === "/api/logs/level") {
        const options = args[1] as RequestInit | undefined;
        if (options?.method === "PUT") {
          const body = JSON.parse(options.body as string);
          return Promise.resolve({ ok: true, json: async () => ({ level: body.level }) });
        }
        return Promise.resolve({ ok: true, json: async () => ({ level: "INFO" }) });
      }
      return mockFetch(...args);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows loading state initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    renderWithProviders(<Settings />);

    expect(screen.getByText("Loading settings...")).toBeInTheDocument();
  });

  it("fetches manual IPs on mount", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/settings/manual-ips");
    });
  });

  it("displays IP input form (no IP list)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });
    // IP list is no longer displayed — only the input form
    expect(screen.queryByText("192.168.1.20")).not.toBeInTheDocument();
  });

  it("shows IP input when no IPs configured", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });
    expect(screen.getByText("+ Add")).toBeInTheDocument();
  });

  it("shows error message with retry button when fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/Error loading/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });

  it("validates IP format before adding", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const form = input.closest("form")!;

    // Invalid IP: too many octets
    fireEvent.change(input, { target: { value: "192.168.1.1.1" } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/Invalid IP address/i)).toBeInTheDocument();
    });

    // mockFetch should not be called for invalid IP
    expect(mockFetch).toHaveBeenCalledTimes(1); // Only initial fetch
  });

  it("validates IP octet range", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const form = input.closest("form")!;

    // Invalid IP: octet > 255
    fireEvent.change(input, { target: { value: "192.168.1.300" } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/Invalid IP address/i)).toBeInTheDocument();
    });
  });

  it("probes device on add (calls POST /api/devices/probe)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const addButton = screen.getByText("+ Add");

    fireEvent.change(input, { target: { value: "192.168.1.10" } });

    // Mock probe response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ device_id: "ABC", ip: "192.168.1.10", name: "Living Room", model: "ST20" }),
    });
    // Re-fetch manual-ips after probe invalidation
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10"] }),
    });

    fireEvent.click(addButton);

    await waitFor(() => {
      const probeCall = mockFetch.mock.calls.find((call: unknown[]) => call[0] === "/api/devices/probe");
      expect(probeCall).toBeDefined();
      const body = JSON.parse((probeCall![1] as RequestInit).body as string);
      expect(body).toEqual({ ip: "192.168.1.10" });
    });
  });

  it("adds valid IP successfully", async () => {
    // Initial fetch - empty list
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const addButton = screen.getByText("+ Add");

    fireEvent.change(input, { target: { value: "192.168.1.30" } });

    // Mock probe response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ device_id: "XYZ", ip: "192.168.1.30", name: "Kitchen", model: "ST10" }),
    });

    // Re-fetch after mutation (React Query invalidation)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.30"] }),
    });

    fireEvent.click(addButton);

    await waitFor(() => {
      const probeCall = mockFetch.mock.calls.find((call: unknown[]) => call[0] === "/api/devices/probe");
      expect(probeCall).toBeDefined();
    });
  });

  it("clears input after successful add", async () => {
    // Initial fetch - empty list
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    // POST request
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.30"] }),
    });

    // Re-fetch after mutation (React Query invalidation)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.30"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10") as HTMLInputElement;
    const addButton = screen.getByText("+ Add");

    fireEvent.change(input, { target: { value: "192.168.1.30" } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(input.value).toBe("");
    });
  });

  it("shows error when add fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    // Probe fails (device not reachable)
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Device not reachable at 192.168.1.30" }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const addButton = screen.getByText("+ Add");

    fireEvent.change(input, { target: { value: "192.168.1.30" } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/No device found/i)).toBeInTheDocument();
    });
  });

  it("renders unified device discovery section with two method cards", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("Find Devices")).toBeInTheDocument();
    });

    expect(screen.getByText("Automatic Search")).toBeInTheDocument();
    expect(screen.getByText("Manual IP Address")).toBeInTheDocument();
  });

  it("rejects empty IP input", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const addButton = screen.getByText("+ Add");
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/Please enter an IP address/i)).toBeInTheDocument();
    });
  });

  it("trims whitespace from IP input", async () => {
    // Initial fetch - empty list
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const form = input.closest("form")!;

    // Mock probe response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ device_id: "XYZ", ip: "192.168.1.30", name: "Kitchen", model: "ST10" }),
    });

    // Re-fetch after mutation
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.30"] }),
    });

    fireEvent.change(input, { target: { value: "  192.168.1.30  " } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/probe",
        expect.objectContaining({
          body: JSON.stringify({ ip: "192.168.1.30" }), // Trimmed
        })
      );
    });
  });

  it("downloads logs via POST /api/logs/backend when Download Logs button is clicked", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    // Wait for settings to load
    await waitFor(() => {
      expect(screen.getByPlaceholderText("192.168.1.10")).toBeInTheDocument();
    });

    // Find the Download Logs button in the Logging section
    const allButtons = screen.getAllByRole("button");
    const downloadButton = allButtons.find(btn => btn.textContent?.includes("Download") || btn.textContent?.includes("downloadLogs"));
    expect(downloadButton).toBeDefined();

    // Mock the POST response for log download
    const mockBlob = new Blob(["log content"], { type: "text/plain" });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      blob: async () => mockBlob,
      headers: new Headers({
        "Content-Disposition": 'attachment; filename="oct-backend-20250101.log"',
      }),
    });

    // Mock URL.createObjectURL
    const mockUrl = "blob:http://localhost/test";
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue(mockUrl),
      revokeObjectURL: vi.fn(),
    });

    const mockAnchor = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
    vi.spyOn(document, "createElement").mockReturnValue(mockAnchor as unknown as HTMLElement);
    vi.spyOn(document.body, "appendChild").mockImplementation((node) => node);

    fireEvent.click(downloadButton!);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/logs/backend",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("shows scan button in automatic search card", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan Now" })).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Scan Now" })).not.toBeDisabled();
  });

  it("shows manual IP fallback description", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/automatic search doesn.*t find anything/i)).toBeInTheDocument();
    });
  });
});
