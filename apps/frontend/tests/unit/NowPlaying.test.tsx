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
      render(<NowPlaying nowPlaying={null} />);

      expect(screen.getByText("No playback")).toBeInTheDocument();
    });

    it("should show empty state when nowPlaying is undefined", () => {
      render(<NowPlaying />);

      expect(screen.getByText("No playback")).toBeInTheDocument();
    });

    it("should apply empty CSS class in empty state", () => {
      const { container } = render(<NowPlaying nowPlaying={null} />);

      const nowPlayingDiv = container.querySelector(".now-playing");
      expect(nowPlayingDiv).toHaveClass("empty");
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

    it("should show music placeholder when no album art", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-art-placeholder svg")).toBeInTheDocument();
    });
  });

  describe("Play/Pause Overlay", () => {
    it("should show Pause button overlay when playing and onPlayPause provided", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(
        <NowPlaying nowPlaying={nowPlaying} onPlayPause={vi.fn()} />
      );

      expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
      expect(container.querySelector(".np-play-overlay")).toBeInTheDocument();
    });

    it("should show Play button overlay when paused and onPlayPause provided", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PAUSE_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} onPlayPause={vi.fn()} />);

      expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
    });

    it("should call onPlayPause when overlay clicked", () => {
      const mockPlayPause = vi.fn();
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} onPlayPause={mockPlayPause} />);

      fireEvent.click(screen.getByRole("button", { name: "Pause" }));
      expect(mockPlayPause).toHaveBeenCalledTimes(1);
    });

    it("should not show overlay when onPlayPause not provided", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-play-overlay")).not.toBeInTheDocument();
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

  describe("Complete Data Scenarios", () => {
    it("should handle all fields with complete data", () => {
      const nowPlaying = {
        art_url: "https://example.com/art.jpg",
        station: "Classic Rock FM",
        track: "Bohemian Rhapsody",
        artist: "Queen",
        play_status: "PLAY_STATE",
      };

      const { container } = render(
        <NowPlaying nowPlaying={nowPlaying} onPlayPause={vi.fn()} />
      );

      expect(screen.getByText("Classic Rock FM")).toBeInTheDocument();
      expect(screen.getByText("Bohemian Rhapsody")).toBeInTheDocument();
      expect(screen.getByText("Queen")).toBeInTheDocument();

      const img = container.querySelector(".np-art img");
      expect(img).toHaveAttribute("src", "https://example.com/art.jpg");

      expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    });

    it("should handle minimal data with only track", () => {
      const nowPlaying = {
        track: "Unknown Artist Song",
        play_status: "PAUSE_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} onPlayPause={vi.fn()} />);

      expect(screen.getByText("No station")).toBeInTheDocument();
      expect(screen.getByText("Unknown Artist Song")).toBeInTheDocument();
      expect(container.querySelector(".np-art-placeholder svg")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
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

      expect(container.querySelector(".np-source-badge.bluetooth")).toBeInTheDocument();
    });

    it("should show Radio badge when source is INTERNET_RADIO", () => {
      const nowPlaying = {
        station: "Radio FM",
        source: "INTERNET_RADIO",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source-badge.radio")).toBeInTheDocument();
    });

    it("should show Radio badge when source is TUNEIN", () => {
      const nowPlaying = {
        station: "TuneIn Station",
        source: "TUNEIN",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source-badge.radio")).toBeInTheDocument();
    });

    it("should not show badge when no source provided", () => {
      const nowPlaying = {
        station: "Some Station",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source-badge")).not.toBeInTheDocument();
    });

    it("should render badge SVG at 16px size", () => {
      const nowPlaying = {
        station: "My Phone",
        source: "BLUETOOTH",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);
      const svg = container.querySelector(".np-source-badge svg");

      expect(svg).toHaveAttribute("width", "16");
      expect(svg).toHaveAttribute("height", "16");
    });
  });

  describe("Bluetooth Source Display", () => {
    it('should show "No device connected" for BLUETOOTH source without station', () => {
      const nowPlaying = {
        source: "BLUETOOTH",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("No device connected")).toBeInTheDocument();
    });

    it("should show device name for BLUETOOTH source with station", () => {
      const nowPlaying = {
        station: "iPhone von Max",
        source: "BLUETOOTH",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("iPhone von Max")).toBeInTheDocument();
    });

    it('should show "No station" for non-BLUETOOTH source without station', () => {
      const nowPlaying = {
        source: "INTERNET_RADIO",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("No station")).toBeInTheDocument();
    });
  });

  describe("Feature Toggle (HAS_EXT_RESOLVER)", () => {
    it("should not show badge for TUNEIN source when HAS_EXT_RESOLVER is false", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_EXT_RESOLVER: false }));
      const { default: NowPlayingGated } = await import("../../src/components/NowPlaying");

      const nowPlaying = {
        station: "TuneIn Station",
        source: "TUNEIN",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlayingGated nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source-badge")).not.toBeInTheDocument();

      vi.doUnmock("../../src/config/capabilities");
    });

    it("should show Radio badge for TUNEIN source when HAS_EXT_RESOLVER is true", () => {
      const nowPlaying = {
        station: "TuneIn Station",
        source: "TUNEIN",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source-badge.radio")).toBeInTheDocument();
    });

    it("should always show Radio badge for INTERNET_RADIO regardless of flag", async () => {
      vi.resetModules();
      vi.doMock("../../src/config/capabilities", () => ({ HAS_EXT_RESOLVER: false }));
      const { default: NowPlayingGated } = await import("../../src/components/NowPlaying");

      const nowPlaying = {
        station: "Radio FM",
        source: "INTERNET_RADIO",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlayingGated nowPlaying={nowPlaying} />);

      expect(container.querySelector(".np-source-badge.radio")).toBeInTheDocument();

      vi.doUnmock("../../src/config/capabilities");
    });
  });
});
