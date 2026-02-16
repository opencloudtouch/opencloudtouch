/**
 * Tests for NowPlaying.tsx
 *
 * User Story: "Als User möchte ich sehen was gerade abgespielt wird"
 *
 * Focus: Functional tests for now playing display
 * - Show track, artist, station info
 * - Show album art or placeholder
 * - Show play/pause status
 * - Handle missing data gracefully
 * - Empty state when nothing playing
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import NowPlaying from "../../src/components/NowPlaying";

describe("NowPlaying Component", () => {
  describe("Empty State", () => {
    it("should show empty state when nowPlaying is null", () => {
      render(<NowPlaying nowPlaying={null} />);

      expect(screen.getByText("Kein Titel")).toBeInTheDocument();
    });

    it("should show empty state when nowPlaying is undefined", () => {
      render(<NowPlaying />);

      expect(screen.getByText("Kein Titel")).toBeInTheDocument();
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

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("🎵")).toBeInTheDocument();
    });
  });

  describe("Play Status Icons", () => {
    it("should show play icon (▶) when playing", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("▶")).toBeInTheDocument();
    });

    it("should show pause icon (⏸) when paused", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PAUSE_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("⏸")).toBeInTheDocument();
    });

    it("should apply playing CSS class when status is PLAY_STATE", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      const statusIcon = container.querySelector(".status-icon");
      expect(statusIcon).toHaveClass("playing");
    });

    it("should not apply playing CSS class when paused", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PAUSE_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      const statusIcon = container.querySelector(".status-icon");
      expect(statusIcon).not.toHaveClass("playing");
    });
  });

  describe("Missing Data Handling", () => {
    it('should show "Unknown Station" when station not provided', () => {
      const nowPlaying = {
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Unknown Station")).toBeInTheDocument();
    });

    it('should show "Unknown Track" when track not provided', () => {
      const nowPlaying = {
        station: "Test Station",
        play_status: "PLAY_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Unknown Track")).toBeInTheDocument();
    });

    it("should not display artist element when artist not provided", () => {
      const nowPlaying = {
        station: "Test Station",
        track: "Test Track",
        play_status: "PLAY_STATE",
      };

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      // Artist div should not exist when artist is not provided
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

      const { container } = render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Classic Rock FM")).toBeInTheDocument();
      expect(screen.getByText("Bohemian Rhapsody")).toBeInTheDocument();
      expect(screen.getByText("Queen")).toBeInTheDocument();

      const img = container.querySelector(".np-art img");
      expect(img).toHaveAttribute("src", "https://example.com/art.jpg");

      expect(screen.getByText("▶")).toBeInTheDocument();
    });

    it("should handle minimal data with only track", () => {
      const nowPlaying = {
        track: "Unknown Artist Song",
        play_status: "PAUSE_STATE",
      };

      render(<NowPlaying nowPlaying={nowPlaying} />);

      expect(screen.getByText("Unknown Station")).toBeInTheDocument();
      expect(screen.getByText("Unknown Artist Song")).toBeInTheDocument();
      expect(screen.getByText("🎵")).toBeInTheDocument();
      expect(screen.getByText("⏸")).toBeInTheDocument();
    });
  });
});
