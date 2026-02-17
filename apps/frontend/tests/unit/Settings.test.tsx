import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Settings from "../../src/pages/Settings";
import { QueryWrapper } from "../utils/reactQueryTestUtils";

// Create typed mock for fetch
let mockFetch: Mock;

const renderWithProviders = (component: React.ReactElement) => {
  return render(<QueryWrapper>{component}</QueryWrapper>);
};

describe("Settings Page", () => {
  beforeEach(() => {
    mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows loading state initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    renderWithProviders(<Settings />);

    expect(screen.getByText("Einstellungen werden geladen...")).toBeInTheDocument();
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
      expect(screen.getByText("Keine manuellen IPs konfiguriert")).toBeInTheDocument();
    });
  });

  it("shows error message when fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    renderWithProviders(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/Fehler beim Laden/i)).toBeInTheDocument();
    });
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
      expect(screen.getByText(/Ungültige IP-Adresse/i)).toBeInTheDocument();
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
      expect(screen.getByText(/Ungültige IP-Adresse/i)).toBeInTheDocument();
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
    const addButton = screen.getByText("+ Hinzufügen");

    fireEvent.change(input, { target: { value: "192.168.1.10" } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/Diese IP-Adresse existiert bereits/i)).toBeInTheDocument();
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
    const addButton = screen.getByText("+ Hinzufügen");

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
      expect(screen.getByText(/IP 192.168.1.30 hinzugefügt/i)).toBeInTheDocument();
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
    const addButton = screen.getByText("+ Hinzufügen");

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
    const addButton = screen.getByText("+ Hinzufügen");

    fireEvent.change(input, { target: { value: "192.168.1.30" } });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/Fehler/i)).toBeInTheDocument();
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

    const deleteButtons = screen.getAllByTitle("IP entfernen");
    fireEvent.click(deleteButtons[0]!);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/settings/manual-ips/192.168.1.10",
        expect.objectContaining({ method: "DELETE" })
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/IP 192.168.1.10 entfernt/i)).toBeInTheDocument();
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

    const deleteButton = screen.getByTitle("IP entfernen");
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(screen.getByText(/Fehler beim Löschen/i)).toBeInTheDocument();
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
      expect(screen.getByText(/Nach dem Hinzufügen oder Entfernen/i)).toBeInTheDocument();
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

    const addButton = screen.getByText("+ Hinzufügen");
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/Bitte geben Sie eine IP-Adresse ein/i)).toBeInTheDocument();
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
});
