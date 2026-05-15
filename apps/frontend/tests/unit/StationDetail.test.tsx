import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import StationDetail from "../../src/components/StationDetail";

const mockStation = {
  uuid: "abc-123",
  name: "SWR3",
  url: "https://swr3.example.com/stream.mp3",
  homepage: "https://www.swr3.de",
  favicon: "https://swr3.example.com/logo.png",
  tags: ["pop", "rock", "news"],
  country: "Germany",
  codec: "MP3",
  bitrate: 128,
  provider: "radiobrowser",
};

describe("StationDetail Component", () => {
  const mockOnBack = vi.fn();
  const mockOnSelect = vi.fn();

  beforeEach(() => {
    mockOnBack.mockClear();
    mockOnSelect.mockClear();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const urlStr = String(input);
        if (urlStr.includes("not-found-uuid")) {
          return { ok: false, status: 404 } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => mockStation,
        } as Response;
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows loading state initially", () => {
    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("displays station details after loading", async () => {
    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("SWR3")).toBeInTheDocument();
    });

    expect(screen.getByText("Germany")).toBeInTheDocument();
    expect(screen.getByText("MP3")).toBeInTheDocument();
    expect(screen.getByText("128 kbps")).toBeInTheDocument();
    expect(screen.getByText("pop")).toBeInTheDocument();
    expect(screen.getByText("rock")).toBeInTheDocument();
    expect(screen.getByText("news")).toBeInTheDocument();
  });

  it("renders favicon image", async () => {
    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("SWR3")).toBeInTheDocument();
    });

    const img = document.querySelector(".sd-favicon") as HTMLImageElement;
    expect(img).not.toBeNull();
    expect(img.src).toBe("https://swr3.example.com/logo.png");
  });

  it("renders homepage link with target _blank", async () => {
    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("SWR3")).toBeInTheDocument();
    });

    const link = screen.getByText("www.swr3.de") as HTMLAnchorElement;
    expect(link.href).toBe("https://www.swr3.de/");
    expect(link.target).toBe("_blank");
    expect(link.rel).toContain("noopener");
  });

  it("calls onBack when back button clicked", async () => {
    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("SWR3")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("← Back"));
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  it("calls onSelect with station data when preset button clicked", async () => {
    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("SWR3")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Save as preset"));
    expect(mockOnSelect).toHaveBeenCalledWith(mockStation);
  });

  it("shows error when station not found", async () => {
    render(
      <StationDetail stationUuid="not-found-uuid" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load. Please try again.")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("← Back"));
    expect(mockOnBack).toHaveBeenCalledTimes(1);
  });

  it("shows error on network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

    render(
      <StationDetail stationUuid="abc-123" onBack={mockOnBack} onSelect={mockOnSelect} />
    );

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
