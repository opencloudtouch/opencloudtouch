/**
 * Tests for device persistence across page navigations.
 *
 * Verifies that swiping to a different device updates the URL parameter
 * so Navigation can propagate it across pages.
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import React from "react";

// Track setSearchParams calls
const mockSetSearchParams = vi.fn();
const mockSearchParams = new URLSearchParams();

// Override the global mock from setup.ts
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({}),
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
    useLocation: () => ({ pathname: "/", search: "", hash: "", state: null }),
  };
});

// Capture onIndexChange from DeviceSwiper
let _capturedOnIndexChange: ((index: number) => void) | null = null;

vi.mock("../../src/components/DeviceSwiper", () => ({
  default: ({
    children,
    onIndexChange,
  }: {
    children: React.ReactNode;
    onIndexChange: (index: number) => void;
  }) => {
    _capturedOnIndexChange = onIndexChange;
    return (
      <div data-testid="device-swiper">
        <button data-testid="swipe-to-0" onClick={() => onIndexChange(0)}>
          Device 1
        </button>
        <button data-testid="swipe-to-1" onClick={() => onIndexChange(1)}>
          Device 2
        </button>
        <div>{children}</div>
      </div>
    );
  },
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...(props as Record<string, string>)}>{children as React.ReactNode}</div>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../../src/components/NowPlaying", () => ({
  default: () => <div data-testid="now-playing" />,
}));
vi.mock("../../src/components/PresetButton", () => ({
  default: () => <div data-testid="preset-button" />,
}));
vi.mock("../../src/components/SetupBadge", () => ({
  default: () => <span data-testid="setup-badge" />,
}));
vi.mock("../../src/components/DeviceOfflineBanner", () => ({
  default: () => null,
}));
vi.mock("../../src/components/DeviceNameEditor", () => ({
  default: ({ name }: { name: string }) => (
    <h2 data-testid="device-name">{name}</h2>
  ),
}));
vi.mock("../../src/components/RadioSearch", () => ({
  default: () => null,
}));
vi.mock("../../src/components/VolumeSlider", () => ({
  default: () => <div data-testid="volume-slider" />,
}));
vi.mock("../../src/components/ConfirmDialog", () => ({
  default: () => null,
}));
vi.mock("../../src/components/LoadingSkeleton", () => ({
  PresetSkeleton: () => <div data-testid="skeleton" />,
}));

vi.mock("../../src/api/devices", () => ({
  playPreset: vi.fn(),
  togglePlayPause: vi.fn(),
  power: vi.fn(),
  deleteDeviceById: vi.fn(),
}));
vi.mock("../../src/api/offlineDeviceStore", () => ({
  isDeviceOffline: () => false,
}));
vi.mock("../../src/hooks/usePresets", () => ({
  usePresets: () => ({
    presets: [],
    loading: false,
    syncing: false,
    error: null,
    clearError: vi.fn(),
    syncPresets: vi.fn(),
    assignStation: vi.fn(),
    removePreset: vi.fn(),
  }),
}));
vi.mock("../../src/hooks/useVolume", () => ({
  useVolume: () => ({
    volume: 50,
    muted: false,
    loading: false,
    setDeviceVolume: vi.fn(),
    toggleMute: vi.fn(),
  }),
}));
vi.mock("../../src/hooks/useNowPlaying", () => ({
  useNowPlaying: () => ({
    nowPlaying: null,
    loading: false,
    refresh: vi.fn(),
  }),
}));
vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: vi.fn() }),
}));

import RadioPresets from "../../src/pages/RadioPresets";

const mockDevices = [
  {
    device_id: "AABBCC111111",
    name: "Wohnzimmer",
    model: "SoundTouch 30",
    ip: "192.168.1.100",
  },
  {
    device_id: "DDEEFF222222",
    name: "Küche",
    model: "SoundTouch 10",
    ip: "192.168.1.101",
  },
];

describe("Device persistence via URL parameter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _capturedOnIndexChange = null;
  });

  test("swiping to second device updates URL with ?device= parameter", async () => {
    render(<RadioPresets devices={mockDevices} />);

    // Swipe to second device
    await act(async () => {
      fireEvent.click(screen.getByTestId("swipe-to-1"));
    });

    expect(mockSetSearchParams).toHaveBeenCalledWith(
      { device: "DDEEFF222222" },
      { replace: true }
    );
  });

  test("swiping back to first device updates URL parameter", async () => {
    render(<RadioPresets devices={mockDevices} />);

    // First swipe to device 2
    await act(async () => {
      fireEvent.click(screen.getByTestId("swipe-to-1"));
    });

    mockSetSearchParams.mockClear();

    // Then back to device 1
    await act(async () => {
      fireEvent.click(screen.getByTestId("swipe-to-0"));
    });

    expect(mockSetSearchParams).toHaveBeenCalledWith(
      { device: "AABBCC111111" },
      { replace: true }
    );
  });

  test("URL parameter is set with replace:true to avoid history pollution", async () => {
    render(<RadioPresets devices={mockDevices} />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("swipe-to-1"));
    });

    // Second argument must be { replace: true }
    const callArgs = mockSetSearchParams.mock.calls[0];
    expect(callArgs[1]).toEqual({ replace: true });
  });
});
