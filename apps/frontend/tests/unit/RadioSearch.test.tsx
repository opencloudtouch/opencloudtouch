import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import RadioSearch from "../../src/components/RadioSearch";

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
        const urlString = String(input);
        const url = urlString.startsWith("http")
          ? new URL(urlString)
          : new URL(urlString, "http://localhost");

        // Station detail endpoint
        if (url.pathname.match(/\/api\/radio\/station\//)) {
          const uuid = url.pathname.split("/").pop();
          const station = mockStations.find((s) => s.uuid === uuid);
          if (!station) {
            return { ok: false, status: 404, json: async () => ({}) } as Response;
          }
          return {
            ok: true,
            status: 200,
            json: async () => ({
              uuid: station.uuid,
              name: station.name,
              country: station.country,
              url: "https://example.com/stream.mp3",
              codec: "MP3",
              bitrate: 128,
              tags: ["pop"],
              homepage: "https://example.com",
              favicon: "https://example.com/logo.png",
              provider: "radiobrowser",
            }),
          } as Response;
        }

        // Search endpoint
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
    expect(screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026")).toBeInTheDocument();
    expect(screen.getByText("\u2715")).toBeInTheDocument();
  });

  it("renders search type chips", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Country")).toBeInTheDocument();
    expect(screen.getByText("Genre")).toBeInTheDocument();
  });

  it("changes placeholder when search type changes", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );
    fireEvent.click(screen.getByText("Country"));
    expect(screen.getByPlaceholderText("e.g. Germany, Austria\u2026")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Genre"));
    expect(screen.getByPlaceholderText("e.g. Rock, Jazz, pop\u2026")).toBeInTheDocument();
  });

  it("sends correct search_type to API", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );
    fireEvent.click(screen.getByText("Country"));
    const searchInput = screen.getByPlaceholderText("e.g. Germany, Austria\u2026");
    fireEvent.change(searchInput, { target: { value: "Germany" } });
    await waitFor(() => {
      const fetchCalls = (fetch as ReturnType<typeof vi.fn>).mock.calls;
      const lastCall = fetchCalls[fetchCalls.length - 1];
      expect(String(lastCall[0])).toContain("search_type=country");
    }, { timeout: 700 });
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

    const overlay = screen.getByRole("button", { name: "Close search" }).closest(".radio-search-overlay")!;
    fireEvent.click(overlay);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it("does not close when modal content clicked", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const modal = document.querySelector(".radio-search-modal")!;
    fireEvent.click(modal);

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("shows loading state during search", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    expect(screen.getByText("Searching...")).toBeInTheDocument();
  });

  it("displays search results", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    await waitFor(
      () => {
        expect(screen.getByText("BBC Radio 1")).toBeInTheDocument();
      },
      { timeout: 700 }
    );
  });

  it("filters results based on search query", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "NPR" } });

    await waitFor(
      () => {
        expect(screen.getByText("NPR (National Public Radio)")).toBeInTheDocument();
        expect(screen.queryByText("BBC Radio 1")).not.toBeInTheDocument();
      },
      { timeout: 700 }
    );
  });

  it("shows empty state when no results found", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });

    await waitFor(
      () => {
        expect(screen.getByText("No stations found")).toBeInTheDocument();
      },
      { timeout: 700 }
    );
  });

  it("clears results when search query is empty", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "" } });

    expect(screen.queryByText("Searching...")).not.toBeInTheDocument();
    expect(screen.queryByText("No stations found")).not.toBeInTheDocument();
  });

  it("opens station detail when station clicked", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    await waitFor(
      () => {
        const stationButton = screen.getByText("BBC Radio 1");
        fireEvent.click(stationButton);
      },
      { timeout: 700 }
    );

    // Should show detail view (station name from fetch)
    await waitFor(() => {
      expect(screen.getByText("Save as preset")).toBeInTheDocument();
    });
  });

  it("hides search results when detail view is open", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "BBC" } });

    await waitFor(
      () => {
        const stationButton = screen.getByText("BBC Radio 1");
        fireEvent.click(stationButton);
      },
      { timeout: 700 }
    );

    // Search input should be hidden, detail view visible
    expect(screen.queryByPlaceholderText("e.g. SWR3, BBC Radio\u2026")).not.toBeInTheDocument();
  });

  it("autofocuses search input when opened", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    expect(searchInput).toHaveFocus();
  });

  it("is case-insensitive when searching", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "FRANCE" } });

    await waitFor(
      () => {
        expect(screen.getByText("France Inter")).toBeInTheDocument();
      },
      { timeout: 700 }
    );
  });

  it("displays error message on API failure", async () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "ERROR_503" } });

    await waitFor(
      () => {
        expect(screen.getByText("Station search failed. Please try again.")).toBeInTheDocument();
      },
      { timeout: 700 }
    );
  });

  it("handles network errors gracefully", async () => {
    // Override fetch to throw network error
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network error"))
    );

    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "test" } });

    await waitFor(
      () => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      },
      { timeout: 700 }
    );
  });

  it("does not search for single character queries", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
    );

    const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
    fireEvent.change(searchInput, { target: { value: "a" } });

    // Wait longer than debounce to confirm no fetch was made
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("calls onClose when Escape key is pressed on overlay", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />,
    );

    const overlay = document.querySelector(".radio-search-overlay")!;
    fireEvent.keyDown(overlay, { key: "Escape" });

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("does not close on non-Escape key on overlay", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />,
    );

    const overlay = document.querySelector(".radio-search-overlay")!;
    fireEvent.keyDown(overlay, { key: "Tab" });

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("overlay has role=none for a11y", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />,
    );

    const overlay = document.querySelector(".radio-search-overlay")!;
    expect(overlay).toHaveAttribute("role", "none");
  });

  it("modal uses div[role=dialog] element (not native dialog) for correct centering", () => {
    render(
      <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />,
    );

    // Must be a div with role="dialog", NOT a native <dialog> element
    // (native <dialog open> has browser-default styles that prevent flex centering)
    const modal = document.querySelector("div.radio-search-modal")!;
    expect(modal).toBeInTheDocument();
    expect(modal).toHaveAttribute("role", "dialog");
    expect(modal).toHaveAttribute("aria-modal", "true");

    const nativeDialog = document.querySelector("dialog.radio-search-modal");
    expect(nativeDialog).not.toBeInTheDocument();
  });

  describe("Feature Toggle (HAS_TUNEIN_SUPPORT)", () => {
    it("should hide provider row when HAS_TUNEIN_SUPPORT is false (only 1 provider)", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_TUNEIN_SUPPORT: false }));
      const { default: RadioSearchGated } = await import("../../src/components/RadioSearch");

      const { container } = render(
        <RadioSearchGated isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      // Search type row exists, but provider row should be hidden (only 1 provider)
      const chipRows = container.querySelectorAll(".search-type-row");
      // Only the search-type row (name/country/tag) should be visible
      expect(chipRows.length).toBe(1);

      // No TuneIn text in DOM
      expect(container.textContent).not.toContain("TuneIn");

      vi.doUnmock("../../src/config/capabilities");
    });

    it("should show provider row with TuneIn chip when HAS_TUNEIN_SUPPORT is true", () => {
      const { container } = render(
        <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      const chipRows = container.querySelectorAll(".search-type-row");
      expect(chipRows.length).toBe(2);

      expect(container.textContent).toContain("TuneIn");
      expect(container.textContent).toContain("RadioBrowser");
    });
  });

  describe("Pagination / Load More", () => {
    const makePage = (count: number, startIndex: number, hasMore: boolean) => {
      const stations = Array.from({ length: count }, (_, i) => ({
        uuid: `station-${startIndex + i}`,
        name: `Station ${startIndex + i}`,
        country: "Testland",
      }));
      return { stations, has_more: hasMore };
    };

    const searchAndWait = async (value: string) => {
      const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
      fireEvent.change(searchInput, { target: { value } });
      await waitFor(
        () => {
          expect(screen.getByText("Station 0")).toBeInTheDocument();
        },
        { timeout: 700 }
      );
    };

    it("shows Load More button when has_more is true", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => ({
          ok: true,
          status: 200,
          json: async () => makePage(10, 0, true),
        } as Response))
      );

      render(
        <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      await searchAndWait("test");

      const loadMoreBtn = document.querySelector(".load-more-btn");
      expect(loadMoreBtn).toBeInTheDocument();
      expect(loadMoreBtn).toHaveTextContent("Load more");
    });

    it("loads more results when Load More is clicked", async () => {
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const urlString = String(input);
        const url = new URL(urlString, "http://localhost");
        const offsetParam = parseInt(url.searchParams.get("offset") || "0", 10);

        if (offsetParam === 0) {
          return {
            ok: true,
            status: 200,
            json: async () => makePage(10, 0, true),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => makePage(10, 10, false),
        } as Response;
      });
      vi.stubGlobal("fetch", fetchMock);

      render(
        <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      await searchAndWait("test");

      const loadMoreBtn = document.querySelector(".load-more-btn")!;
      fireEvent.click(loadMoreBtn);

      await waitFor(() => {
        expect(screen.getByText("Station 10")).toBeInTheDocument();
      });

      // Verify second fetch used offset=10
      const secondCall = fetchMock.mock.calls.find((call) => {
        const u = new URL(String(call[0]), "http://localhost");
        return u.searchParams.get("offset") === "10";
      });
      expect(secondCall).toBeDefined();

      // All 20 results visible
      expect(screen.getByText("Station 0")).toBeInTheDocument();
      expect(screen.getByText("Station 19")).toBeInTheDocument();

      // Load More hidden after has_more=false
      expect(document.querySelector(".load-more-btn")).not.toBeInTheDocument();
    });

    it("hides Load More button when has_more is false", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => ({
          ok: true,
          status: 200,
          json: async () => makePage(5, 0, false),
        } as Response))
      );

      render(
        <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
      fireEvent.change(searchInput, { target: { value: "test" } });

      await waitFor(
        () => {
          expect(screen.getByText("Station 0")).toBeInTheDocument();
        },
        { timeout: 700 }
      );

      expect(document.querySelector(".load-more-btn")).not.toBeInTheDocument();
    });

    it("shows max reached message when results >= 200", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => ({
          ok: true,
          status: 200,
          json: async () => makePage(200, 0, true),
        } as Response))
      );

      render(
        <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      const searchInput = screen.getByPlaceholderText("e.g. SWR3, BBC Radio\u2026");
      fireEvent.change(searchInput, { target: { value: "test" } });

      await waitFor(
        () => {
          expect(screen.getByText("Station 0")).toBeInTheDocument();
        },
        { timeout: 700 }
      );

      const maxReached = document.querySelector(".max-reached");
      expect(maxReached).toBeInTheDocument();
      // Load More should NOT appear even though has_more=true (MAX_RESULTS reached)
      expect(document.querySelector(".load-more-btn")).not.toBeInTheDocument();
    });

    it("handles load more API error", async () => {
      let callCount = 0;
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => {
          callCount++;
          if (callCount === 1) {
            return {
              ok: true,
              status: 200,
              json: async () => makePage(10, 0, true),
            } as Response;
          }
          return {
            ok: false,
            status: 500,
            json: async () => ({ detail: "Internal server error" }),
          } as Response;
        })
      );

      render(
        <RadioSearch isOpen={true} onStationSelect={mockOnStationSelect} onClose={mockOnClose} />
      );

      await searchAndWait("test");

      const loadMoreBtn = document.querySelector(".load-more-btn")!;
      fireEvent.click(loadMoreBtn);

      await waitFor(() => {
        expect(document.querySelector(".search-error")).toBeInTheDocument();
      });
    });
  });
});
