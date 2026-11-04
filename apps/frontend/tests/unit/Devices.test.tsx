/**
 * Tests for Devices.tsx (the device card with now playing, source switch, keys, volume and presets)
 *
 * User Story: "Als User möchte ich Radiosender auf Preset-Tasten speichern"
 *
 * Focus: Functional tests for preset management
 * - Display device information and presets (1-6)
 * - Assign radio station to preset (opens search modal)
 * - Play preset (triggers backend API)
 * - Clear preset (removes assignment)
 * - Device switching with DeviceSwiper
 * - Edge cases: no devices, preset lifecycle
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import Devices from "../../src/pages/Devices";
import { deleteDeviceById } from "../../src/api/devices";
import { markDeviceOffline, _resetOfflineStore } from "../../src/api/offlineDeviceStore";

// Mock toast context so tests don't require ToastProvider wrapper
const mockShowToast = vi.fn();
const mockHideToast = vi.fn();
vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShowToast, hide: mockHideToast }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

// Mock API module
vi.mock("../../src/api/presets", () => ({
  getDevicePresets: vi.fn(),
  setPreset: vi.fn(),
  clearPreset: vi.fn(),
  syncPresetsFromDevice: vi.fn(),
}));

// Preserve the real device API methods and spy on the existing playPreset call.
vi.mock("../../src/api/devices", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/devices")>();
  return {
    ...actual,
    playPreset: vi.fn().mockResolvedValue(undefined),
    deleteDeviceById: vi.fn().mockResolvedValue(undefined),
    selectSource: vi.fn().mockResolvedValue(undefined),
    togglePlayPause: vi.fn().mockResolvedValue(undefined),
    nextTrack: vi.fn().mockResolvedValue(undefined),
    prevTrack: vi.fn().mockResolvedValue(undefined),
  };
});

// Mock device hooks
const mockSetDeviceVolume = vi.fn();
const mockToggleMute = vi.fn();
let mockVolumeState = { volume: 45, muted: false, loading: false, setDeviceVolume: mockSetDeviceVolume, toggleMute: mockToggleMute };
vi.mock("../../src/hooks/useVolume", () => ({
  useVolume: () => mockVolumeState,
}));

const mockRefreshNowPlaying = vi.fn();
let mockNowPlayingState: Record<string, unknown> | null = null;
vi.mock("../../src/hooks/useNowPlaying", () => ({
  useNowPlaying: () => ({
    nowPlaying: mockNowPlayingState,
    loading: false,
    error: null,
    refresh: mockRefreshNowPlaying,
  }),
}));

import * as presetsApi from "../../src/api/presets";
import * as devicesApi from "../../src/api/devices";
import type { PresetResponse } from "../../src/api/presets";
import type { ReactNode } from "react";

// Mock child components
vi.mock("../../src/components/DeviceSwiper", () => ({
  default: ({ children, onIndexChange }: { children: ReactNode; onIndexChange: (index: number) => void }) => (
    <div data-testid="device-swiper">
      <button onClick={() => onIndexChange(0)}>Device 1</button>
      <button onClick={() => onIndexChange(1)}>Device 2</button>
      <div data-testid="swiper-content">{children}</div>
    </div>
  ),
}));

vi.mock("../../src/components/NowPlaying", () => ({
  default: ({
    nowPlaying,
    headerLabel,
    headerAction,
  }: {
    nowPlaying: { title: string } | null;
    headerLabel?: string;
    headerAction?: ReactNode;
  }) => (
    <div data-testid="now-playing">
      <span data-testid="np-label">{headerLabel}</span>
      {headerAction}
      {nowPlaying ? nowPlaying.title : "No playback"}
    </div>
  ),
}));

vi.mock("../../src/components/DeviceNameEditor", () => ({
  default: ({ name }: { name: string }) => (
    <h2 className="device-name" data-test="device-name">{name}</h2>
  ),
}));

vi.mock("../../src/components/VolumeSlider", () => ({
  default: ({ volume, onVolumeChange, muted, onMuteToggle }: { volume: number; onVolumeChange: (v: number) => void; muted: boolean; onMuteToggle: () => void }) => (
    <div data-testid="volume-slider">
      <input
        type="range"
        value={volume}
        onChange={(e) => onVolumeChange(Number(e.target.value))}
        data-testid="volume-input"
      />
      <button onClick={onMuteToggle} data-testid="mute-button">
        {muted ? "Unmute" : "Mute"}
      </button>
    </div>
  ),
}));

vi.mock("../../src/components/PresetRow", () => ({
  default: ({ number, preset, state, onToggle, onChange }: { number: number; preset: { station_name: string } | null; state: string; onToggle: () => void; onChange: () => void }) => (
    <div data-testid={`preset-${number}`}>
      <span>Preset {number}</span>
      {preset ? (
        <>
          <span data-testid={`preset-${number}-name`}>{preset.station_name}</span>
          <button onClick={onChange} data-testid={`preset-${number}-change`}>
            Change
          </button>
          <button onClick={onToggle} data-testid={`preset-${number}-play`} data-state={state}>
            Play
          </button>
        </>
      ) : (
        <button onClick={onChange} data-testid={`preset-${number}-assign`}>
          Assign
        </button>
      )}
    </div>
  ),
}));

let mockZones: unknown[] = [];
vi.mock("../../src/hooks/useZones", () => ({
  useZones: () => ({ zones: mockZones, isLoading: false, error: null }),
}));

vi.mock("../../src/components/RadioSearch", () => ({
  default: ({ isOpen, onClose, onStationSelect, onDelete, hasExistingPreset }: { isOpen: boolean; onClose: () => void; onStationSelect: (station: { stationuuid: string; name: string; country: string; url: string; homepage: string; favicon: string }) => void; onDelete?: () => void; hasExistingPreset?: boolean }) => {
    if (!isOpen) return null;
    return (
      <div data-testid="radio-search-modal">
        <button onClick={onClose} data-testid="search-close">
          Close
        </button>
        <button
          onClick={async () => {
            try {
              await onStationSelect({
                stationuuid: "test-uuid",
                name: "Test Radio",
                country: "Germany",
                url: "http://test.com",
                homepage: "http://test-homepage.com",
                favicon: "http://test-favicon.com/icon.png",
              });
            } catch {
              // RadioSearch handles assignment errors in its own error dialog.
            }
          }}
          data-testid="select-station"
        >
          Select Test Radio
        </button>
        {hasExistingPreset && onDelete && (
          <button onClick={onDelete} data-testid="search-delete-preset">
            Delete Preset
          </button>
        )}
      </div>
    );
  },
}));

vi.mock("../../src/components/SetupBadge", () => ({
  default: () => <span data-testid="setup-badge" />,
}));

describe("Devices Page", () => {
  const mockDevices = [
    {
      device_id: "AABBCC123456",
      name: "Living Room",
      model: "SoundTouch 30",
      ip: "192.168.1.101",
    },
    {
      device_id: "DDEEFF789012",
      name: "Küche",
      model: "SoundTouch 10",
      ip: "192.168.1.102",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockNowPlayingState = null;
    mockZones = [];
    window.localStorage.clear();

    // Reset volume hook mock state
    mockVolumeState = { volume: 45, muted: false, loading: false, setDeviceVolume: mockSetDeviceVolume, toggleMute: mockToggleMute };

    // Setup default API mocks
    vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([]);
    vi.mocked(presetsApi.setPreset).mockResolvedValue({
      id: 1,
      device_id: "AABBCC123456",
      preset_number: 1,
      station_uuid: "test-uuid",
      station_name: "Test Radio",
      station_url: "http://test.com",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    });
    vi.mocked(presetsApi.clearPreset).mockResolvedValue({ message: "Preset cleared" });
    vi.mocked(presetsApi.syncPresetsFromDevice).mockResolvedValue({ message: "Synced" });
  });

  // Helper function to render and wait for initial load to complete
  const renderAndWaitForLoad = async (devices = mockDevices) => {
    const result = render(<Devices devices={devices} />);
    // Wait for any pending state updates from useEffect
    await act(async () => {
      await vi
        .waitFor(
          () => {
            expect(presetsApi.getDevicePresets).toHaveBeenCalled();
          },
          { timeout: 100 }
        )
        .catch(() => {
          // May not be called if no devices
        });
    });
    return result;
  };

  describe("Device Display", () => {
    it("should display current device information", async () => {
      await renderAndWaitForLoad();

      // Component uses data-test, not data-testid, so use text queries
      expect(screen.getByText("Living Room")).toBeInTheDocument();
      expect(screen.getByText("SoundTouch 30")).toBeInTheDocument();
      expect(screen.getByText("192.168.1.101")).toBeInTheDocument();
    });

    it("should show all 6 preset buttons", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      for (let i = 1; i <= 6; i++) {
        expect(screen.getByTestId(`preset-${i}`)).toBeInTheDocument();
      }
    });

    it("should show empty state when no devices available", async () => {
      await act(async () => {
        render(<Devices devices={[]} />);
      });

      expect(screen.getByText("No devices found")).toBeInTheDocument();
      expect(screen.queryByTestId("device-swiper")).not.toBeInTheDocument();
    });
  });

  describe("Preset Assignment Flow", () => {
    it("should open radio search modal when clicking assign button", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      const assignButton = screen.getByTestId("preset-1-assign");
      fireEvent.click(assignButton);

      expect(screen.getByTestId("radio-search-modal")).toBeInTheDocument();
    });

    it("should assign station to preset when selected from search", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Allow the initial empty-DB auto-sync to finish before assigning.
      await waitFor(() => {
        expect(presetsApi.getDevicePresets).toHaveBeenCalledTimes(2);
      });
      await act(async () => {});

      // Open search for preset 1
      const assignButton = screen.getByTestId("preset-1-assign");
      fireEvent.click(assignButton);

      // Select station
      const selectButton = screen.getByTestId("select-station");
      fireEvent.click(selectButton);

      // Verify preset is assigned
      await waitFor(() => {
        expect(screen.getByTestId("preset-1-name")).toHaveTextContent("Test Radio");
      });

      // Note: Modal remains open (component behavior - user must close manually)
    });

    it("should close search modal when clicking close button", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Open search
      fireEvent.click(screen.getByTestId("preset-2-assign"));
      expect(screen.getByTestId("radio-search-modal")).toBeInTheDocument();

      // Close search
      fireEvent.click(screen.getByTestId("search-close"));
      expect(screen.queryByTestId("radio-search-modal")).not.toBeInTheDocument();
    });

    it("should allow assigning different stations to different presets", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Allow the initial empty-DB auto-sync to finish before assigning.
      await waitFor(() => {
        expect(presetsApi.getDevicePresets).toHaveBeenCalledTimes(2);
      });
      await act(async () => {});

      // Assign to preset 1
      fireEvent.click(screen.getByTestId("preset-1-assign"));
      fireEvent.click(screen.getByTestId("select-station"));

      await waitFor(() => {
        expect(screen.getByTestId("preset-1-name")).toHaveTextContent("Test Radio");
      });

      // Assign to preset 2
      fireEvent.click(screen.getByTestId("preset-2-assign"));
      fireEvent.click(screen.getByTestId("select-station"));

      await waitFor(() => {
        expect(screen.getByTestId("preset-2-name")).toHaveTextContent("Test Radio");
      });

      // Both presets should be assigned
      expect(screen.getByTestId("preset-1-name")).toBeInTheDocument();
      expect(screen.getByTestId("preset-2-name")).toBeInTheDocument();
    });
  });

  describe("Power Button", () => {
    it("refreshes now-playing state after toggling power (#416)", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await act(async () => {
        fireEvent.click(screen.getByLabelText("Power on/off"));
      });

      // The device's own SSE push can be delayed or missed entirely, so the
      // power button must force a fresh fetch itself instead of only
      // trusting the push channel -- otherwise the UI is stuck showing the
      // pre-toggle state until something else (e.g. a tab switch) happens
      // to remount the hook.
      await waitFor(() => {
        expect(mockRefreshNowPlaying).toHaveBeenCalled();
      });
    });
  });

  describe("Preset Playback", () => {
    it("should show play button for assigned preset", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Assign preset first
      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-3-assign"));
      });
      await act(async () => {
        fireEvent.click(screen.getByTestId("select-station"));
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-3-play")).toBeInTheDocument();
      });

      // Click play and verify it calls the already-shipped backend API.
      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-3-play"));
      });

      await waitFor(() => {
        expect(devicesApi.playPreset).toHaveBeenCalledWith("AABBCC123456", 3);
      });
      expect(screen.getByTestId("preset-3-play")).toBeInTheDocument();
    });
  });

  describe("Preset Overwrite Flow", () => {
    it("should directly overwrite an occupied preset without confirmation", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 4,
          station_uuid: "uuid-4",
          station_name: "Old Radio",
          station_url: "http://old.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ]);

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-4-name")).toBeInTheDocument();
      });

      // Click change on occupied preset → select new station
      fireEvent.click(screen.getByTestId("preset-4-change"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should call setPreset API directly without confirmation dialog
      await waitFor(() => {
        expect(presetsApi.setPreset).toHaveBeenCalledWith(
          expect.objectContaining({
            device_id: "AABBCC123456",
            preset_number: 4,
            station_name: "Test Radio",
          })
        );
      });
    });
  });

  describe("Preset Deletion", () => {
    it("should show delete button in search modal for occupied preset", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 3,
          station_uuid: "uuid-3",
          station_name: "Old Station",
          station_url: "http://old.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ]);

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-3-name")).toBeInTheDocument();
      });

      // Open search for occupied preset
      fireEvent.click(screen.getByTestId("preset-3-change"));

      // Delete button should be visible
      expect(screen.getByTestId("search-delete-preset")).toBeInTheDocument();
    });

    it("should delete preset when delete button is clicked", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 2,
          station_uuid: "uuid-2",
          station_name: "Delete Me",
          station_url: "http://delete.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ]);

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-2-name")).toHaveTextContent("Delete Me");
      });

      // Open search → click delete → confirm in dialog
      fireEvent.click(screen.getByTestId("preset-2-change"));
      fireEvent.click(screen.getByTestId("search-delete-preset"));

      await waitFor(() => {
        expect(screen.getByTestId("confirm-dialog-confirm")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByTestId("confirm-dialog-confirm"));

      await waitFor(() => {
        expect(presetsApi.clearPreset).toHaveBeenCalledWith("AABBCC123456", 2);
      });

      // Modal should close and preset should be gone
      await waitFor(() => {
        expect(screen.queryByTestId("radio-search-modal")).not.toBeInTheDocument();
      });
    });

    it("should not show delete button for empty preset", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Open search for empty preset
      fireEvent.click(screen.getByTestId("preset-1-assign"));

      // Delete button should NOT be visible
      expect(screen.queryByTestId("search-delete-preset")).not.toBeInTheDocument();
    });
  });

  describe("Device Switching", () => {
    it("should render DeviceSwiper component", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      expect(screen.getByTestId("device-swiper")).toBeInTheDocument();
    });

    it("should update displayed device when swiper index changes", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Initially shows first device
      expect(screen.getByText("Living Room")).toBeInTheDocument();

      // Switch to second device
      await act(async () => {
        fireEvent.click(screen.getByText("Device 2"));
      });

      // Should show second device
      expect(screen.getByText("Küche")).toBeInTheDocument();
      expect(screen.getByText("192.168.1.102")).toBeInTheDocument();
    });
  });

  describe("Volume Control", () => {
    it("should render volume slider", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      expect(screen.getByTestId("volume-slider")).toBeInTheDocument();
      expect(screen.getByTestId("volume-input")).toHaveValue("45");
    });

    it("should call setDeviceVolume when slider changes", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      const volumeInput = screen.getByTestId("volume-input");
      await act(async () => {
        fireEvent.change(volumeInput, { target: { value: "75" } });
      });

      expect(mockSetDeviceVolume).toHaveBeenCalledWith(75);
    });

    it("should call toggleMute when mute button clicked", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      const muteButton = screen.getByTestId("mute-button");

      // Initially not muted
      expect(muteButton).toHaveTextContent("Mute");

      // Toggle mute
      await act(async () => {
        fireEvent.click(muteButton);
      });
      expect(mockToggleMute).toHaveBeenCalledTimes(1);
    });
  });

  describe("API Integration", () => {
    it("should load presets from API on mount", async () => {
      const mockPresets = [
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 1,
          station_uuid: "uuid-1",
          station_name: "Radio One",
          station_url: "http://radio1.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
        {
          id: 2,
          device_id: "AABBCC123456",
          preset_number: 3,
          station_uuid: "uuid-3",
          station_name: "Radio Three",
          station_url: "http://radio3.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ];

      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(mockPresets);

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Should call API with device_id
      await waitFor(() => {
        expect(presetsApi.getDevicePresets).toHaveBeenCalledWith("AABBCC123456");
      });

      // Should display loaded presets
      await waitFor(() => {
        expect(screen.getByTestId("preset-1-name")).toHaveTextContent("Radio One");
        expect(screen.getByTestId("preset-3-name")).toHaveTextContent("Radio Three");
      });
    });

    it("should call setPreset API when assigning station", async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Open search and select station
      fireEvent.click(screen.getByTestId("preset-2-assign"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should call API with correct parameters
      await waitFor(() => {
        expect(presetsApi.setPreset).toHaveBeenCalledWith({
          device_id: "AABBCC123456",
          preset_number: 2,
          station_uuid: "test-uuid",
          station_name: "Test Radio",
          station_url: "http://test.com",
          station_homepage: "http://test-homepage.com",
          station_favicon: "http://test-favicon.com/icon.png",
        });
      });
    });

    it("should call setPreset API directly when overwriting existing preset", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 4,
          station_uuid: "uuid-4",
          station_name: "Radio Four",
          station_url: "http://radio4.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ]);

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-4-name")).toBeInTheDocument();
      });

      // Click change → select station → should save directly
      fireEvent.click(screen.getByTestId("preset-4-change"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should call setPreset API directly without confirmation
      await waitFor(() => {
        expect(presetsApi.setPreset).toHaveBeenCalledWith(
          expect.objectContaining({
            device_id: "AABBCC123456",
            preset_number: 4,
          })
        );
      });
    });

    it("should reload presets when device changes", async () => {
      const device1Presets = [
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 1,
          station_uuid: "uuid-1",
          station_name: "Device 1 Radio",
          station_url: "http://radio1.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ];

      const device2Presets = [
        {
          id: 2,
          device_id: "DDEEFF789012",
          preset_number: 2,
          station_uuid: "uuid-2",
          station_name: "Device 2 Radio",
          station_url: "http://radio2.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ];

      vi.mocked(presetsApi.getDevicePresets)
        .mockResolvedValueOnce(device1Presets)
        .mockResolvedValueOnce(device2Presets);

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Wait for device 1 presets to load
      await waitFor(() => {
        expect(screen.getByTestId("preset-1-name")).toHaveTextContent("Device 1 Radio");
      });

      // Switch to device 2
      fireEvent.click(screen.getByText("Device 2"));

      // Should load device 2 presets
      await waitFor(() => {
        expect(presetsApi.getDevicePresets).toHaveBeenCalledWith("DDEEFF789012");
        expect(screen.getByTestId("preset-2-name")).toHaveTextContent("Device 2 Radio");
      });

      // Device 1 preset should be gone
      expect(screen.queryByText("Device 1 Radio")).not.toBeInTheDocument();
    });
  });

  describe("Error Handling", () => {
    // Suppress console.error for error handling tests (expected behavior)
    const originalConsoleError = console.error;
    beforeEach(() => {
      console.error = vi.fn();
    });
    afterEach(() => {
      console.error = originalConsoleError;
    });

    it("should display error when loading presets fails", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockRejectedValue(new Error("Network error"));

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Should display error message
      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toHaveTextContent("Presets could not be loaded. Please try again.");
      });
    });

    it("should dismiss error message when clicking close", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockRejectedValue(new Error("Network error"));

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toBeInTheDocument();
      });

      // Click close button
      const closeButton = screen.getByTestId("error-message").querySelector("button");
      fireEvent.click(closeButton!);

      // Error should be gone
      await waitFor(() => {
        expect(screen.queryByTestId("error-message")).not.toBeInTheDocument();
      });
    });

    it("should display error when setting preset fails", async () => {
      vi.mocked(presetsApi.setPreset).mockRejectedValue(new Error("Failed to save preset"));

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      // Try to assign preset
      fireEvent.click(screen.getByTestId("preset-1-assign"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should display error
      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toHaveTextContent("Preset could not be saved. Please try again.");
      });
    });

    it("should display error when saving preset fails during overwrite", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([
        {
          id: 1,
          device_id: "AABBCC123456",
          preset_number: 1,
          station_uuid: "uuid-1",
          station_name: "Test Radio",
          station_url: "http://test.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ]);

      vi.mocked(presetsApi.setPreset).mockRejectedValue(new Error("Failed to save preset"));

      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-1-name")).toBeInTheDocument();
      });

      // Click change → select station (saves directly, no confirmation)
      fireEvent.click(screen.getByTestId("preset-1-change"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should display user-friendly error
      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toHaveTextContent("Preset could not be saved. Please try again.");
      });
    });
  });

  describe("Loading States", () => {
    it("should show loading indicator while loading presets", async () => {
      let resolvePresets: (value: PresetResponse[]) => void;
      const presetsPromise = new Promise<PresetResponse[]>((resolve) => {
        resolvePresets = resolve;
      });

      vi.mocked(presetsApi.getDevicePresets).mockReturnValue(presetsPromise);

      // Use fake timers to advance past the 500ms debounce
      vi.useFakeTimers();
      render(<Devices devices={mockDevices} />);

      // Advance past the 500ms debounce
      await act(async () => {
        vi.advanceTimersByTime(600);
      });
      vi.useRealTimers();

      // Should now be loading (loadPresets fired and set loading=true)
      await waitFor(() => {
        expect(screen.getByTestId("loading-indicator")).toBeInTheDocument();
      });

      // Resolve presets
      resolvePresets!([]);

      // Loading should disappear
      await waitFor(() => {
        expect(screen.queryByTestId("loading-indicator")).not.toBeInTheDocument();
      });
    });

    it("should show loading indicator while saving preset", async () => {
      let resolveSetPreset: (value: PresetResponse) => void;
      const setPresetPromise = new Promise<PresetResponse>((resolve) => {
        resolveSetPreset = resolve;
      });

      vi.mocked(presetsApi.setPreset).mockReturnValue(setPresetPromise);

      render(<Devices devices={mockDevices} />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.queryByTestId("loading-indicator")).not.toBeInTheDocument();
      });

      // Start assigning preset
      fireEvent.click(screen.getByTestId("preset-1-assign"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should show loading
      await waitFor(() => {
        expect(screen.getByTestId("loading-indicator")).toBeInTheDocument();
      });

      // Resolve save
      resolveSetPreset!({
        id: 1,
        device_id: "AABBCC123456",
        preset_number: 1,
        station_uuid: "test-uuid",
        station_name: "Test Radio",
        station_url: "http://test.com",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      });

      // Loading should disappear
      await waitFor(() => {
        expect(screen.queryByTestId("loading-indicator")).not.toBeInTheDocument();
      });
    });
  });
  describe("Remove online device", () => {
    it("offers the quiet remove button and the dialog says the device is reachable", async () => {
      const onRemoveDevice = vi.fn();
      await act(async () => {
        render(<Devices devices={mockDevices} onRemoveDevice={onRemoveDevice} />);
      });

      const button = screen.getByRole("button", { name: /remove device/i });
      expect(button).toHaveClass("btn-ghost");
      fireEvent.click(button);

      const dialog = await screen.findByRole("alertdialog");
      expect(dialog).toHaveTextContent("Living Room");
      expect(dialog).toHaveTextContent(/is reachable/i);

      fireEvent.click(await screen.findByTestId("confirm-dialog-confirm"));
      await waitFor(() => {
        expect(deleteDeviceById).toHaveBeenCalledWith(mockDevices[0]!.device_id);
        expect(onRemoveDevice).toHaveBeenCalledWith(mockDevices[0]!.device_id);
      });
    });
  });

  describe("Remove offline device", () => {
    afterEach(() => {
      _resetOfflineStore();
    });

    const openRemoveDialog = async () => {
      markDeviceOffline(mockDevices[0]!.device_id);
      const onRemoveDevice = vi.fn();
      await act(async () => {
        render(<Devices devices={mockDevices} onRemoveDevice={onRemoveDevice} />);
      });
      fireEvent.click(screen.getByRole("button", { name: /remove device|delete device/i }));
      return onRemoveDevice;
    };

    it("asks for confirmation naming the device before removing it", async () => {
      await openRemoveDialog();

      const dialog = await screen.findByRole("alertdialog");
      expect(dialog).toHaveTextContent("Living Room");
      expect(deleteDeviceById).not.toHaveBeenCalled();
    });

    it("does not remove the device when the user cancels", async () => {
      const onRemoveDevice = await openRemoveDialog();

      fireEvent.click(await screen.findByTestId("confirm-dialog-cancel"));

      expect(deleteDeviceById).not.toHaveBeenCalled();
      expect(onRemoveDevice).not.toHaveBeenCalled();
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });

    it("removes the device after the user confirms", async () => {
      const onRemoveDevice = await openRemoveDialog();

      fireEvent.click(await screen.findByTestId("confirm-dialog-confirm"));

      await waitFor(() => {
        expect(deleteDeviceById).toHaveBeenCalledWith(mockDevices[0]!.device_id);
        expect(onRemoveDevice).toHaveBeenCalledWith(mockDevices[0]!.device_id);
      });
    });
  });

  describe("Source switch, keys and preset toggle", () => {
    const presetRows = [
      { id: 1, device_id: "AABBCC123456", preset_number: 1, station_uuid: "u1", station_name: "SWR3", station_url: "http://a", created_at: "2024-01-01T00:00:00Z", updated_at: "2024-01-01T00:00:00Z" },
      { id: 2, device_id: "AABBCC123456", preset_number: 2, station_uuid: "u2", station_name: "NDR 2", station_url: "http://b", created_at: "2024-01-01T00:00:00Z", updated_at: "2024-01-01T00:00:00Z" },
    ];
    const playing = (source: string, extra: Record<string, unknown> = {}) => ({
      source,
      state: "PLAY_STATE",
      ...extra,
    });
    const renderDevices = async () => {
      await act(async () => {
        render(<Devices devices={mockDevices} />);
      });
    };

    it("shows three source buttons and presses the one the device plays", async () => {
      mockNowPlayingState = playing("BLUETOOTH", { station_name: "iPhone" });
      await renderDevices();

      expect(screen.getByRole("button", { name: "Bluetooth" })).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByRole("button", { name: "Presets" })).toHaveAttribute("aria-pressed", "false");
    });

    it("switches to AUX through the backend and refreshes now playing", async () => {
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      await renderDevices();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "AUX" }));
      });

      await waitFor(() => {
        expect(devicesApi.selectSource).toHaveBeenCalledWith("AABBCC123456", "AUX");
      });
      expect(mockRefreshNowPlaying).toHaveBeenCalled();
    });

    it("shows the header text Switching... while the switch runs", async () => {
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      let finish: () => void = () => {};
      vi.mocked(devicesApi.selectSource).mockImplementationOnce(
        () => new Promise<void>((resolve) => { finish = resolve; })
      );
      await renderDevices();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Bluetooth" }));
      });
      expect(screen.getByTestId("np-label")).toHaveTextContent("Switching to Bluetooth…");
      expect(screen.getByRole("button", { name: "Bluetooth" })).toHaveAttribute("aria-busy", "true");

      await act(async () => {
        finish();
      });
      expect(screen.getByTestId("np-label")).toHaveTextContent("");
    });

    it("marks the key and shows a persistent toast with retry when the switch fails", async () => {
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      vi.mocked(devicesApi.selectSource).mockRejectedValueOnce(new Error("offline"));
      await renderDevices();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "AUX" }));
      });

      const marked = await screen.findByRole("button", { name: "AUX, not reachable. Try again" });
      expect(marked).toHaveClass("si-bb--fail");
      expect(screen.getByRole("button", { name: "Presets" })).toHaveAttribute("aria-pressed", "true");
      expect(mockShowToast).toHaveBeenCalledWith(
        "AUX not reachable",
        "error",
        expect.objectContaining({ persistent: true })
      );

      // tapping the marked key tries again; success clears the marker and the toast
      await act(async () => {
        fireEvent.click(marked);
      });
      expect(devicesApi.selectSource).toHaveBeenCalledTimes(2);
      await waitFor(() => expect(mockHideToast).toHaveBeenCalled());
      expect(screen.queryByRole("button", { name: /not reachable/ })).not.toBeInTheDocument();
    });

    it("retries from the toast action", async () => {
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      vi.mocked(devicesApi.selectSource).mockRejectedValueOnce(new Error("offline"));
      await renderDevices();
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "AUX" }));
      });
      await screen.findByRole("button", { name: "AUX, not reachable. Try again" });

      const options = mockShowToast.mock.calls.at(-1)?.[2] as {
        action: { onClick: () => void };
      };
      await act(async () => {
        options.action.onClick();
      });
      expect(devicesApi.selectSource).toHaveBeenCalledTimes(2);
    });

    it("Presets plays the preset this device played last", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      window.localStorage.setItem("oct.lastPreset.AABBCC123456", "2");
      mockNowPlayingState = playing("BLUETOOTH", { station_name: "iPhone" });
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-2-name")).toBeInTheDocument());

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Presets" }));
      });

      await waitFor(() => {
        expect(devicesApi.playPreset).toHaveBeenCalledWith("AABBCC123456", 2);
      });
    });

    it("Presets falls back to the first saved preset when none was played yet", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue([presetRows[1]!]);
      mockNowPlayingState = playing("AUX");
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-2-name")).toBeInTheDocument());

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Presets" }));
      });

      await waitFor(() => {
        expect(devicesApi.playPreset).toHaveBeenCalledWith("AABBCC123456", 2);
      });
    });

    it("Presets tells the user when no preset is saved and starts nothing", async () => {
      mockNowPlayingState = playing("BLUETOOTH", { station_name: "iPhone" });
      await renderDevices();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Presets" }));
      });

      expect(mockShowToast).toHaveBeenCalledWith(
        "No preset is saved yet. Assign a station to a preset first.",
        "warning"
      );
      expect(devicesApi.playPreset).not.toHaveBeenCalled();
    });

    it("remembers a preset that is playing as the last one", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "NDR 2" });
      await renderDevices();

      await waitFor(() => {
        expect(window.localStorage.getItem("oct.lastPreset.AABBCC123456")).toBe("2");
      });
    });

    it("a preset row toggles: start, pause, resume", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-1-play")).toBeInTheDocument());

      // idle: starts the preset
      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-1-play"));
      });
      expect(devicesApi.playPreset).toHaveBeenCalledWith("AABBCC123456", 1);
      expect(devicesApi.togglePlayPause).not.toHaveBeenCalled();
    });

    it("pauses a running preset with the play/pause key instead of restarting it", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-1-play")).toHaveAttribute("data-state", "playing"));

      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-1-play"));
      });

      expect(devicesApi.togglePlayPause).toHaveBeenCalledWith("AABBCC123456");
      expect(devicesApi.playPreset).not.toHaveBeenCalled();
    });

    it("resumes a paused preset", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      mockNowPlayingState = { source: "INTERNET_RADIO", state: "PAUSE_STATE", station_name: "SWR3" };
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-1-play")).toHaveAttribute("data-state", "paused"));

      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-1-play"));
      });

      expect(devicesApi.togglePlayPause).toHaveBeenCalledTimes(1);
      expect(devicesApi.playPreset).not.toHaveBeenCalled();
    });

    it("marks a preset as failed when the start fails and announces it", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      vi.mocked(devicesApi.playPreset).mockRejectedValueOnce(new Error("nope"));
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-1-play")).toBeInTheDocument());

      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-1-play"));
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-1-play")).toHaveAttribute("data-state", "failed");
      });
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Preset 1 (SWR3) could not be started. Tap it to try again."
      );
    });

    it("shows previous and next for Bluetooth and sends the keys", async () => {
      mockNowPlayingState = playing("BLUETOOTH", { station_name: "iPhone" });
      await renderDevices();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Next track" }));
      });
      expect(devicesApi.nextTrack).toHaveBeenCalledWith("AABBCC123456");

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Previous track" }));
      });
      expect(devicesApi.prevTrack).toHaveBeenCalledWith("AABBCC123456");
    });

    it("shows no previous/next for radio, and a note instead of keys for AUX", async () => {
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      const { unmount } = render(<Devices devices={mockDevices} />);
      expect(screen.queryByRole("button", { name: "Next track" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
      unmount();

      mockNowPlayingState = playing("AUX");
      render(<Devices devices={mockDevices} />);
      expect(
        screen.getByText("Playback is controlled on the connected device.")
      ).toBeInTheDocument();
    });

    it("locks source and keys in standby", async () => {
      mockNowPlayingState = { source: "STANDBY", state: "STOP_STATE" };
      await renderDevices();

      expect(screen.getByText("Device on standby. Switch it on to listen.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Play" })).toBeDisabled();
      expect(screen.getByRole("button", { name: "AUX" })).toHaveAttribute("aria-disabled", "true");
      expect(document.querySelector("[inert]")).not.toBeNull();
    });

    it("keeps the presets editable in standby (assigning a station only touches the database)", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockResolvedValue(presetRows);
      mockNowPlayingState = { source: "STANDBY", state: "STOP_STATE" };
      await renderDevices();
      await waitFor(() => expect(screen.getByTestId("preset-1-change")).toBeInTheDocument());

      expect(screen.getByTestId("preset-1-change").closest("[inert]")).toBeNull();
      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-3-assign"));
      });
      expect(screen.getByTestId("radio-search-modal")).toBeInTheDocument();
    });

    it("a zone member cannot change the source and says why", async () => {
      mockZones = [
        {
          master_id: "MASTER",
          members: [
            { device_id: "MASTER", role: "master", name: "Wohnzimmer" },
            { device_id: "AABBCC123456", role: "slave" },
          ],
        },
      ];
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      await renderDevices();

      const aux = screen.getByRole("button", { name: "AUX" });
      expect(aux).toHaveAttribute("aria-disabled", "true");
      expect(aux).toHaveAttribute("aria-describedby", "dv-slave-hint");
      expect(document.getElementById("dv-slave-hint")).toHaveTextContent(
        "The source is set by master Wohnzimmer."
      );
      expect(screen.getByRole("button", { name: "Pause" })).toBeDisabled();
    });

    it("drops the result of a switch that finishes after the user moved to another device", async () => {
      mockNowPlayingState = playing("INTERNET_RADIO", { station_name: "SWR3" });
      let fail: (err: Error) => void = () => {};
      vi.mocked(devicesApi.selectSource).mockImplementationOnce(
        () => new Promise<void>((_, reject) => { fail = reject; })
      );
      await renderDevices();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "AUX" }));
      });
      await act(async () => {
        fireEvent.click(screen.getByText("Device 2"));
      });
      await act(async () => {
        fail(new Error("late failure"));
      });

      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("shows no player, presets or volume for an offline device", async () => {
      markDeviceOffline("AABBCC123456");
      await renderDevices();

      expect(screen.queryByTestId("now-playing")).not.toBeInTheDocument();
      expect(screen.queryByTestId("preset-list")).not.toBeInTheDocument();
      expect(screen.queryByTestId("volume-slider")).not.toBeInTheDocument();
    });
  });
});
