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

  it("displays fetched IPs", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
      expect(screen.getByText("192.168.1.20")).toBeInTheDocument();
    });
  });

  it("shows empty state when no IPs configured", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("No manual IPs configured")).toBeInTheDocument();
    });
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

  it("prevents adding duplicate IPs", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("192.168.1.10");
    const addButton = screen.getByText("+ Add");

    fireEvent.change(input, { target: { value: "192.168.1.10" } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/This IP address already exists/i)).toBeInTheDocument();
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

    // Mock POST request for adding IP (sets all IPs)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.30"] }),
    });

    // Re-fetch after mutation (React Query invalidation)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.30"] }),
    });

    fireEvent.click(addButton);

    await waitFor(() => {
      const postCall = mockFetch.mock.calls.find((call: unknown[]) => (call[1] as RequestInit)?.method === "POST");
      expect(postCall).toBeDefined();
      expect(postCall![0]).toBe("/api/settings/manual-ips");
      const body = JSON.parse((postCall![1] as RequestInit).body as string);
      expect(body).toEqual({ ips: ["192.168.1.30"] });
    });

    await waitFor(() => {
      expect(screen.getByText(/IP 192.168.1.30 added/i)).toBeInTheDocument();
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

    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Server error" }),
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
      expect(screen.getByText(/Error/i)).toBeInTheDocument();
    });
  });

  it("deletes IP successfully", async () => {
    // Initial fetch of IPs
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10", "192.168.1.20"] }),
    });

    // DELETE request
    mockFetch.mockResolvedValueOnce({
      ok: true,
    });

    // Re-fetch after delete (React Query invalidation)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.20"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Remove IP");
    fireEvent.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/settings/manual-ips/192.168.1.10",
        expect.objectContaining({ method: "DELETE" })
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/IP 192.168.1.10 removed/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByText("192.168.1.10")).not.toBeInTheDocument();
      expect(screen.getByText("192.168.1.20")).toBeInTheDocument();
    });
  });

  it("shows error when delete fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10"] }),
    });

    mockFetch.mockResolvedValueOnce({
      ok: false,
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
    });

    const deleteButton = screen.getByTitle("Remove IP");
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(screen.getByText(/unexpected error/i)).toBeInTheDocument();
    });

    // IP should still be in list
    expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
  });

  it("shows info box", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/Click.*Discover Devices/i)).toBeInTheDocument();
    });
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

    // POST new manual IPs (with trimmed IP)
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

    const input = screen.getByPlaceholderText("192.168.1.10");
    const form = input.closest("form")!;

    fireEvent.change(input, { target: { value: "  192.168.1.30  " } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/settings/manual-ips",
        expect.objectContaining({
          body: JSON.stringify({ ips: ["192.168.1.30"] }), // Trimmed
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

  it("renders the network discovery section", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("Network Discovery")).toBeInTheDocument();
    });

    expect(screen.getByText(/Scan your local network/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scan Network" })).toBeInTheDocument();
  });

  it("shows scan button as disabled while discovering", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: ["192.168.1.10"] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
    });

    const scanButton = screen.getByRole("button", { name: "Scan Network" });
    expect(scanButton).not.toBeDisabled();
  });

  it("shows network discovery hint text", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ips: [] }),
    });

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/Uses SSDP to find devices/)).toBeInTheDocument();
    });
  });
});
