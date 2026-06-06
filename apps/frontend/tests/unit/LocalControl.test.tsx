/**
 * Functional Tests for LocalControl Component
 *
 * User Story: "Als User möchte ich meine Musik steuern (Play/Pause/Skip/Volume)"
 *
 * Test Strategy: Behaviour-driven testing focusing on user interactions
 * Coverage: Play/Pause, Skip, Volume, Standby, Source Selection, Error Handling
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import LocalControl from "../../src/pages/LocalControl";

// Mock framer-motion to avoid animation issues in tests
vi.mock("framer-motion", () => ({
  motion: {
    /* eslint-disable @typescript-eslint/no-unused-vars */
    div: ({
      children,
      dragConstraints,
      dragElastic,
      whileTap,
      whileHover,
      initial,
      animate,
      exit,
      transition,
      ...props
    }: Record<string, unknown>) => <div {...props}>{children as React.ReactNode}</div>,
    /* eslint-enable @typescript-eslint/no-unused-vars */
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock hooks
const mockNowPlaying = {
  source: "INTERNET_RADIO",
  state: "PLAY_STATE",
  station_name: "Test Radio",
  artist: "Test Artist",
  track: "Test Track",
  artwork_url: "https://example.com/art.jpg",
};

const mockUseNowPlaying = vi.fn().mockReturnValue({
  nowPlaying: mockNowPlaying,
  loading: false,
  refresh: vi.fn(),
});

const mockSetDeviceVolume = vi.fn();
const mockToggleMute = vi.fn();
const mockUseVolume = vi.fn().mockReturnValue({
  volume: 45,
  muted: false,
  loading: false,
  setDeviceVolume: mockSetDeviceVolume,
  toggleMute: mockToggleMute,
});

vi.mock("../../src/hooks/useNowPlaying", () => ({
  useNowPlaying: (...args: unknown[]) => mockUseNowPlaying(...args),
}));

vi.mock("../../src/hooks/useVolume", () => ({
  useVolume: (...args: unknown[]) => mockUseVolume(...args),
}));

// Mock API
const mockTogglePlayPause = vi.fn().mockResolvedValue(undefined);
const mockNextTrack = vi.fn().mockResolvedValue(undefined);
const mockPrevTrack = vi.fn().mockResolvedValue(undefined);
const mockPower = vi.fn().mockResolvedValue(undefined);

vi.mock("../../src/api/devices", () => ({
  togglePlayPause: (...args: unknown[]) => mockTogglePlayPause(...args),
  nextTrack: (...args: unknown[]) => mockNextTrack(...args),
  prevTrack: (...args: unknown[]) => mockPrevTrack(...args),
  power: (...args: unknown[]) => mockPower(...args),
}));

// Mock useZones (STORY-1013)
vi.mock("../../src/hooks/useZones", () => ({
  useZones: () => ({
    zones: [],
    isLoading: false,
    error: null,
    createZone: vi.fn(),
    dissolveZone: vi.fn(),
    addMembers: vi.fn(),
    removeMembers: vi.fn(),
    changeMaster: vi.fn(),
    refetch: vi.fn(),
  }),
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

vi.mock("../../src/components/SetupBadge", () => ({
  default: () => <span data-testid="setup-badge" />,
}));

vi.mock("../../src/components/DeviceNameEditor", () => ({
  default: ({ name }: { name: string }) => (
    <h2 className="device-name" data-test="device-name">{name}</h2>
  ),
}));

const mockDevices = [
  {
    device_id: "ST10-001",
    name: "Living Room",
    model: "SoundTouch 10",
    ip: "192.168.1.100",
    capabilities: { airplay: false },
  },
  {
    device_id: "ST30-002",
    name: "Schlafzimmer",
    model: "SoundTouch 30",
    ip: "192.168.1.101",
    capabilities: { airplay: true },
  },
];

describe("LocalControl - Core Playback Functionality", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseNowPlaying.mockReturnValue({
      nowPlaying: mockNowPlaying,
      loading: false,
      refresh: vi.fn(),
    });
    mockUseVolume.mockReturnValue({
      volume: 45,
      muted: false,
      loading: false,
      setDeviceVolume: mockSetDeviceVolume,
      toggleMute: mockToggleMute,
    });
  });

  test("should show empty state when no devices available", async () => {
    await act(async () => {
      render(<LocalControl devices={[]} />);
    });

    expect(screen.getByText(/No devices found/i)).toBeInTheDocument();
  });

  test("should display current device name and model", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(screen.getByText("SoundTouch 10")).toBeInTheDocument();
  });

  test("should call useNowPlaying with device ID", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(mockUseNowPlaying).toHaveBeenCalledWith("ST10-001");
  });

  test("should call useVolume with device ID", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(mockUseVolume).toHaveBeenCalledWith("ST10-001");
  });

  test("should call togglePlayPause API when play/pause clicked", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    // Use the playback controls button (not the NowPlaying overlay)
    const playPauseButton = document.querySelector(".playback-button.play-pause") as HTMLButtonElement;
    await user.click(playPauseButton);

    expect(mockTogglePlayPause).toHaveBeenCalledWith("ST10-001");
  });

  test("should call nextTrack API when next clicked", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const nextButton = screen.getByRole("button", { name: /Next Track/i });
    await user.click(nextButton);

    expect(mockNextTrack).toHaveBeenCalledWith("ST10-001");
  });

  test("should call prevTrack API when previous clicked", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const prevButton = screen.getByRole("button", { name: /Previous Track/i });
    await user.click(prevButton);

    expect(mockPrevTrack).toHaveBeenCalledWith("ST10-001");
  });

  test("should show play icon when paused", async () => {
    mockUseNowPlaying.mockReturnValue({
      nowPlaying: { ...mockNowPlaying, state: "PAUSE_STATE" },
      loading: false,
      refresh: vi.fn(),
    });

    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    const playButton = document.querySelector(".playback-button.play-pause") as HTMLButtonElement;
    expect(playButton).toHaveAttribute("aria-label", "Play");
  });

  test("should call power API when power button clicked", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const powerButton = screen.getByRole("button", { name: /Power on\/off/i });
    await user.click(powerButton);

    expect(mockPower).toHaveBeenCalledWith("ST10-001");
  });

  test("should call toggleMute when mute button clicked", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const muteButton = screen.getByRole("button", { name: "Mute" });
    await user.click(muteButton);

    expect(mockToggleMute).toHaveBeenCalled();
  });

  test("should display source selection tabs", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(screen.getByText("Radio")).toBeInTheDocument();
    expect(screen.getByText("Bluetooth")).toBeInTheDocument();
    expect(screen.getByText("AUX")).toBeInTheDocument();
  });

  test("should show NowPlaying component when playing", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(screen.getByText("Test Radio")).toBeInTheDocument();
    expect(screen.getByText("Test Track")).toBeInTheDocument();
  });

  test("should not show NowPlaying when no playback data", async () => {
    mockUseNowPlaying.mockReturnValue({
      nowPlaying: null,
      loading: false,
      refresh: vi.fn(),
    });

    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(screen.queryByText("Test Radio")).not.toBeInTheDocument();
  });
});

describe("LocalControl - Source Selection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseNowPlaying.mockReturnValue({
      nowPlaying: mockNowPlaying,
      loading: false,
      refresh: vi.fn(),
    });
    mockUseVolume.mockReturnValue({
      volume: 45,
      muted: false,
      loading: false,
      setDeviceVolume: mockSetDeviceVolume,
      toggleMute: mockToggleMute,
    });
  });

  test("should switch between available sources", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const bluetoothTab = screen.getByRole("button", { name: /Bluetooth/i });
    await user.click(bluetoothTab);

    expect(bluetoothTab).toHaveClass("active");
  });

  test("should show AirPlay only when device supports it", async () => {
    let rerender: (ui: React.ReactElement) => void;
    await act(async () => {
      const result = render(<LocalControl devices={[mockDevices[0]!]} />);
      rerender = result.rerender;
    });

    expect(screen.queryByRole("button", { name: /AirPlay/i })).not.toBeInTheDocument();

    await act(async () => {
      rerender(<LocalControl devices={[mockDevices[1]!]} />);
    });
    expect(screen.getByRole("button", { name: /AirPlay/i })).toBeInTheDocument();
  });
});

describe("LocalControl - Edge Cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseNowPlaying.mockReturnValue({
      nowPlaying: mockNowPlaying,
      loading: false,
      refresh: vi.fn(),
    });
    mockUseVolume.mockReturnValue({
      volume: 45,
      muted: false,
      loading: false,
      setDeviceVolume: mockSetDeviceVolume,
      toggleMute: mockToggleMute,
    });
  });

  test("should display Unknown Model when device model is missing", async () => {
    const deviceWithoutModel = [
      { device_id: "1", name: "Test Device", ip: "192.168.1.10" },
    ];

    await act(async () => {
      render(<LocalControl devices={deviceWithoutModel} />);
    });

    expect(screen.getByText("Unknown Model")).toBeInTheDocument();
  });

  test("should render VolumeSlider with current volume", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    const slider = screen.getByRole("slider");
    expect(slider).toBeInTheDocument();
  });

  test("should show mute state from useVolume hook", async () => {
    mockUseVolume.mockReturnValue({
      volume: 45,
      muted: true,
      loading: false,
      setDeviceVolume: mockSetDeviceVolume,
      toggleMute: mockToggleMute,
    });

    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(screen.getByRole("button", { name: "Unmute" })).toBeInTheDocument();
  });
});
