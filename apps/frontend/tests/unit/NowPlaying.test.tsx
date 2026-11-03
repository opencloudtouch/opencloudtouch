/**
 * Tests for NowPlaying.tsx
 *
 * User Story: "Als User möchte ich sehen was gerade abgespielt wird"
 *
 * Focus: Functional tests for now playing display
 * - Show track, artist, station info
 * - Show album art or placeholder
 * - Play/Pause overlay on album art
 * - Handle missing data gracefully
 * - Empty state when nothing playing
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import NowPlaying from "../../src/components/NowPlaying";

describe("NowPlaying Component", () => {
  describe("Empty State", () => {
    it("should show empty state when nowPlaying is null", () => {
      const { container } = render(<NowPlaying nowPlaying={null} />);

      expect(screen.getByText("No playback")).toBeInTheDocument();

      const nowPlayingDiv = container.querySelector(".np");
      expect(nowPlayingDiv).toHaveClass("np--empty");
    });

    it("should show empty state when nowPlaying is undefined", () => {
      render(<NowPlaying />);

      expect(screen.getByText("No playback")).toBeInTheDocument();
    });
  });

  describe("Now Playing Display", () => {
    it("should display station, track, and artist when all provided", () => {
      const nowPlaying = {
        station: "Radio Paradise",
        track: "Imagine",
        artist: "John Lennon",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Radio Paradise")).toBeInTheDocument();
      expect(screen.getByText("Imagine")).toBeInTheDocument();
      expect(screen.getByText("John Lennon")).toBeInTheDocument();
    });

    it("should display album art when art_url provided", () => {
      const nowPlaying = {
        art_url: "https://example.com/art.jpg",
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      const img = container.querySelector(".np-art img");
      expect(img).toHaveAttribute("src", "https://example.com/art.jpg");
    });

    it("should show default artwork when no album art", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      const img = container.querySelector(".np-art img");
      expect(img).toBeInTheDocument();
      expect(img?.getAttribute("src")).toMatch(/\/images\/default-artwork-[1-3]\.jpg/);
    });

    it("should fall back to default artwork on image load error", () => {
      const nowPlaying = {
        station: "Test Station",
        art_url: "https://broken-url.example.com/nope",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      const img = container.querySelector(".np-art img") as HTMLImageElement;
      expect(img).toBeInTheDocument();
      expect(img.src).toContain("broken-url.example.com");

      // Simulate image load error
      fireEvent.error(img);

      expect(img.getAttribute("src")).toMatch(/\/images\/default-artwork-[1-3]\.jpg/);
    });
  });

  describe("Header with the source switch", () => {
    const action = <div data-testid="switch">switch</div>;

    it("shows the switch in the header and no play overlay on the cover", () => {
      const nowPlaying = { station: "SWR3", track: "Track", play_status: "PLAY_STATE", source: "INTERNET_RADIO" };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} headerAction={action} />);

      expect(screen.getByTestId("switch")).toBeInTheDocument();
      expect(container.querySelector(".np-header")).toHaveClass("si-head");
      expect(screen.queryByRole("button", { name: "Pause" })).not.toBeInTheDocument();
    });

    it("hides the source badge for sources the switch shows as pressed", () => {
      const nowPlaying = { station: "SWR3", play_status: "PLAY_STATE", source: "INTERNET_RADIO" };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} headerAction={action} />);

      expect(container.querySelector(".np-source")).not.toBeInTheDocument();
    });

    it("keeps the source badge for sources that cannot be chosen (Spotify)", () => {
      const nowPlaying = { track: "Track", play_status: "PLAY_STATE", source: "SPOTIFY" };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} headerAction={action} />);

      expect(container.querySelector(".np-source")).toBeInTheDocument();
    });

    it("replaces the header text while a switch is running", () => {
      const nowPlaying = { station: "SWR3", play_status: "PLAY_STATE", source: "INTERNET_RADIO" };

      render(<NowPlaying nowPlaying={nowPlaying} headerLabel="Switching to AUX…" headerAction={action} />);

      expect(screen.getByText("Switching to AUX…")).toBeInTheDocument();
      expect(screen.queryByText("SWR3")).not.toBeInTheDocument();
    });

    it("shows the switch even without playback data", () => {
      render(<NowPlaying nowPlaying={null} headerAction={action} />);

      expect(screen.getByTestId("switch")).toBeInTheDocument();
    });

    it("shows an icon tile instead of a stock picture for AUX and Bluetooth without cover", () => {
      const { container, rerender } = render(
        <NowPlaying nowPlaying={{ play_status: "PLAY_STATE", source: "AUX" }} />
      );
      expect(container.querySelector(".np-art--none")).toBeInTheDocument();
      expect(container.querySelector("img")).not.toBeInTheDocument();

      rerender(<NowPlaying nowPlaying={{ track: "T", play_status: "PLAY_STATE", source: "BLUETOOTH" }} />);
      expect(container.querySelector(".np-art--none")).toBeInTheDocument();

      rerender(
        <NowPlaying
          nowPlaying={{ track: "T", art_url: "http://x/y.jpg", play_status: "PLAY_STATE", source: "BLUETOOTH" }}
        />
      );
      expect(container.querySelector(".np-art--none")).not.toBeInTheDocument();
      expect(container.querySelector("img")).toBeInTheDocument();
    });
  });

  describe("Missing Data Handling", () => {
    it('should show "No station" when station not provided', () => {
      const nowPlaying = {
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("No station")).toBeInTheDocument();
    });

    it("should not show track element when track not provided", () => {
      const nowPlaying = {
        station: "Test Station",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-track")).not.toBeInTheDocument();
    });

    it("should not display artist element when artist not provided", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      const artistElement = container.querySelector(".np-artist");
      expect(artistElement).not.toBeInTheDocument();
    });

    it("should display artist when provided", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        artist: "Test Artist",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Test Artist")).toBeInTheDocument();
    });
  });

  describe("Source Badge", () => {
    it("should show Bluetooth badge when source is BLUETOOTH", () => {
      const nowPlaying = {
        station: "My Phone",
        source: "BLUETOOTH",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.bluetooth")).toBeInTheDocument();
    });

    it("should show Radio badge when source is INTERNET_RADIO", () => {
      const nowPlaying = {
        station: "Radio FM",
        source: "INTERNET_RADIO",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.radio")).toBeInTheDocument();
    });

    it("should show Radio badge when source is TUNEIN", () => {
      const nowPlaying = {
        station: "TuneIn Station",
        source: "TUNEIN",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.radio")).toBeInTheDocument();
    });

    it("should not show badge when no source provided", () => {
      const nowPlaying = {
        station: "Some Station",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source")).not.toBeInTheDocument();
    });

    it("should show AUX badge for AUX source", () => {
      const nowPlaying = {
        source: "AUX",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.aux")).toBeInTheDocument();
    });

    it("should show AirPlay badge for AIRPLAY source", () => {
      const nowPlaying = {
        source: "AIRPLAY",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.airplay")).toBeInTheDocument();
    });

    it("should show TV badge for TV source", () => {
      const nowPlaying = {
        source: "TV",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.tv")).toBeInTheDocument();
    });

    it("should show streaming badge for SPOTIFY source", () => {
      const nowPlaying = {
        source: "SPOTIFY",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.streaming")).toBeInTheDocument();
    });
  });

  describe("Bluetooth Source Display", () => {
    it('should show "Bluetooth" for BLUETOOTH source without station', () => {
      const nowPlaying = {
        source: "BLUETOOTH",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Bluetooth")).toBeInTheDocument();
    });

    it("should show source and device name for BLUETOOTH source with station", () => {
      const nowPlaying = {
        station: "iPhone von Max",
        source: "BLUETOOTH",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Bluetooth · iPhone von Max")).toBeInTheDocument();
    });

    it('should show "No station" for non-BLUETOOTH source without station', () => {
      const nowPlaying = {
        source: "INTERNET_RADIO",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("No station")).toBeInTheDocument();
    });

    it('should show "AUX" for AUX source', () => {
      const nowPlaying = {
        source: "AUX",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("AUX")).toBeInTheDocument();
    });

    it('should show "AirPlay" for AIRPLAY source', () => {
      const nowPlaying = {
        source: "AIRPLAY",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("AirPlay")).toBeInTheDocument();
    });

    it('should show "DLNA" for DLNA source', () => {
      const nowPlaying = {
        source: "DLNA",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("DLNA")).toBeInTheDocument();
    });

    it('should show "TV / HDMI" for TV source', () => {
      const nowPlaying = {
        source: "TV",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("TV / HDMI")).toBeInTheDocument();
    });
  });

  describe("Feature Toggle (HAS_TUNEIN_SUPPORT)", () => {
    it("should not show badge for TUNEIN source when HAS_TUNEIN_SUPPORT is false", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_TUNEIN_SUPPORT: false }));
      const { default: NowPlayingGated } = await import("../../src/components/NowPlaying");

      const nowPlaying = {
        station: "TuneIn Station",
        source: "TUNEIN",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlayingGated nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source")).not.toBeInTheDocument();

      vi.doUnmock("../../src/config/capabilities");
    });

    it("should always show Radio badge for INTERNET_RADIO regardless of flag", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_TUNEIN_SUPPORT: false }));
      const { default: NowPlayingGated } = await import("../../src/components/NowPlaying");

      const nowPlaying = {
        station: "Radio FM",
        source: "INTERNET_RADIO",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlayingGated nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source.radio")).toBeInTheDocument();

      vi.doUnmock("../../src/config/capabilities");
    });
  });
});
