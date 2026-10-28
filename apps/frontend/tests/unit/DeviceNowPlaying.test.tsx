/**
 * Tests for DeviceNowPlaying component
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeviceNowPlaying } from "../../src/components/DeviceNowPlaying";
import type { NowPlayingState } from "../../src/api/devices";

function makePlaying(overrides: Partial<NowPlayingState> = {}): NowPlayingState {
  return {
    source: "TUNEIN",
    state: "PLAY_STATE",
    track: "Test Track",
    artist: "Test Artist",
    ...overrides,
  };
}

describe("DeviceNowPlaying", () => {
  // ---- Null / early-return paths ----

  it("renders nothing when nowPlaying is null", () => {
    const { container } = render(<DeviceNowPlaying nowPlaying={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when loading is true", () => {
    const { container } = render(<DeviceNowPlaying nowPlaying={makePlaying()} loading={true} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when state is not PLAY_STATE", () => {
    const { container } = render(
      <DeviceNowPlaying nowPlaying={makePlaying({ state: "STOP_STATE" })} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when neither title nor subtitle available", () => {
    const { container } = render(
      <DeviceNowPlaying
        nowPlaying={makePlaying({
          track: undefined,
          station_name: undefined,
          artist: undefined,
        })}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  // ---- Artwork display ----

  it("shows artwork image when artwork_url is provided", () => {
    render(
      <DeviceNowPlaying
        nowPlaying={makePlaying({ artwork_url: "https://img.example.com/art.jpg" })}
      />
    );
    const img = screen.getByRole("presentation");
    expect(img).toHaveAttribute("src", "https://img.example.com/art.jpg");
    expect(img).toHaveClass("dnp-art");
    expect(img).toHaveAttribute("loading", "lazy");
  });

  it("does not show icon when artwork is present", () => {
    const { container } = render(
      <DeviceNowPlaying
        nowPlaying={makePlaying({
          source: "TUNEIN",
          artwork_url: "https://img.example.com/art.jpg",
        })}
      />
    );
    expect(container.querySelector(".dnp-icon")).toBeNull();
  });

  // ---- Source icon fallbacks (no artwork) ----

  it.each([
    ["a radio icon", "TUNEIN"],
    ["a bluetooth icon", "BLUETOOTH"],
    ["a headphones icon", "AUX"],
  ])("shows %s for %s source without artwork", (_icon, source) => {
    render(<DeviceNowPlaying nowPlaying={makePlaying({ source, artwork_url: undefined })} />);
    expect(document.querySelector(".dnp-icon svg")).not.toBeNull();
  });

  it("shows no icon for unknown source without artwork", () => {
    const { container } = render(
      <DeviceNowPlaying nowPlaying={makePlaying({ source: "SPOTIFY", artwork_url: undefined })} />
    );
    expect(container.querySelector(".dnp-icon")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  // ---- Text display ----

  it("displays track as title", () => {
    render(<DeviceNowPlaying nowPlaying={makePlaying({ track: "My Song" })} />);
    expect(screen.getByText("My Song")).toHaveClass("dnp-title");
  });

  it("displays station_name as title when track is missing", () => {
    render(
      <DeviceNowPlaying nowPlaying={makePlaying({ track: undefined, station_name: "Radio FM" })} />
    );
    expect(screen.getByText("Radio FM")).toHaveClass("dnp-title");
  });

  it("prefers track over station_name", () => {
    render(
      <DeviceNowPlaying nowPlaying={makePlaying({ track: "Song A", station_name: "Station B" })} />
    );
    expect(screen.getByText("Song A")).toBeInTheDocument();
    expect(screen.queryByText("Station B")).toBeNull();
  });

  it("displays artist as subtitle", () => {
    render(<DeviceNowPlaying nowPlaying={makePlaying({ artist: "Cool Band" })} />);
    expect(screen.getByText("Cool Band")).toHaveClass("dnp-artist");
  });

  it("renders without artist when only title available", () => {
    const { container } = render(
      <DeviceNowPlaying nowPlaying={makePlaying({ artist: undefined })} />
    );
    expect(container.querySelector(".dnp-artist")).toBeNull();
    expect(screen.getAllByText("Test Track").length).toBeGreaterThan(0);
  });

  it("renders with only artist when no title available", () => {
    render(
      <DeviceNowPlaying
        nowPlaying={makePlaying({
          track: undefined,
          station_name: undefined,
          artist: "Solo Artist",
        })}
      />
    );
    expect(screen.getByText("Solo Artist")).toBeInTheDocument();
  });
});
