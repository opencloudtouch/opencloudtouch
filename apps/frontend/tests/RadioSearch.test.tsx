import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import RadioSearch from "../src/components/RadioSearch";

describe("RadioSearch Component", () => {
  const mockOnStationSelect = vi.fn();
  const mockOnClose = vi.fn();
  const mockStations = [
    { uuid: "mock-bbc-1", name: "BBC Radio 1", country: "United Kingdom" },
    { uuid: "mock-npr-1", name: "NPR (National Public Radio)", country: "United States" },
    { uuid: "mock-france-inter", name: "France Inter", country: "France" },
  ];

  beforeEach(() => {
    mockOnStationSelect.mockClear();
    mockOnClose.mockClear();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        // Handle relative URLs by adding a base
        const urlString = String(input);
        const url = urlString.startsWith("http")
          ? new URL(urlString)
          : new URL(urlString, "http://localhost");
        const query = url.searchParams.get("q") || "";

        if (query === "ERROR_503") {
          return {
            ok: false,
            status: 503,
            json: async () => ({ detail: "Service unavailable" }),
          } as Response;
        }

        const filtered = mockStations.filter((station) =>
          station.name.toLowerCase().includes(query.toLowerCase())
        );

        return {
          ok: true,
          status: 200,
          json: async () => ({ stations: filtered }),
        } as Response;
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <RadioSearch isOpen={false} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders search modal when open", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );
    expect(screen.getByPlaceholderText("Sender suchen...")).toBeInTheDocument();
    expect(screen.getByText("✕")).toBeInTheDocument();
  });

  it("calls onClose when close button clicked", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const closeButton = screen.getByText("✕");
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when overlay clicked", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const overlay = screen.getByRole("button", { name: "✕" }).closest(".radio-search-overlay");
    fireEvent.click(overlay);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it("does not close when modal content clicked", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const modal = document.querySelector(".radio-search-modal");
    fireEvent.click(modal);

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("shows loading state during search", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    expect(screen.getByText("Suche...")).toBeInTheDocument();
  });

  it("displays search results", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    await waitFor(
      () => {
        expect(screen.getByText("BBC Radio 1")).toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });

  it("filters results based on search query", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "NPR" } });

    await waitFor(
      () => {
        expect(screen.getByText("NPR (National Public Radio)")).toBeInTheDocument();
        expect(screen.queryByText("BBC Radio 1")).not.toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });

  it("shows empty state when no results found", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });

    await waitFor(
      () => {
        expect(screen.getByText("Keine Sender gefunden")).toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });

  it("clears results when search query is empty", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "" } });

    expect(screen.queryByText("Suche...")).not.toBeInTheDocument();
    expect(screen.queryByText("Keine Sender gefunden")).not.toBeInTheDocument();
  });

  it("calls onStationSelect when station clicked", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    await waitFor(
      () => {
        const stationButton = screen.getByText("BBC Radio 1");
        fireEvent.click(stationButton);
      },
      { timeout: 500 }
    );

    expect(mockOnStationSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        stationuuid: "mock-bbc-1",
        name: "BBC Radio 1",
        country: "United Kingdom",
      })
    );
  });

  it("clears search and closes modal after station selection", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    await waitFor(
      () => {
        const stationButton = screen.getByText("BBC Radio 1");
        fireEvent.click(stationButton);
      },
      { timeout: 500 }
    );

    expect(mockOnClose).toHaveBeenCalled();
  });

  it("autofocuses search input when opened", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    expect(searchInput).toHaveFocus();
  });

  it("is case-insensitive when searching", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("Sender suchen...");
    fireEvent.change(searchInput, { target: { value: "FRANCE" } });

    await waitFor(
      () => {
        expect(screen.getByText("France Inter")).toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });
});
