/**
 * Tests for RadioPresets.tsx
 *
 * User Story: "Als User möchte ich Radiosender auf Preset-Tasten speichern"
 *
 * Focus: Functional tests for preset management
 * - Display device information and presets (1-6)
 * - Assign radio station to preset (opens search modal)
 * - Play preset (future: triggers backend API)
 * - Clear preset (removes assignment)
 * - Device switching with DeviceSwiper
 * - Edge cases: no devices, preset lifecycle
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import RadioPresets from "../../src/pages/RadioPresets";

// Mock toast context so tests don't require ToastProvider wrapper
const mockShowToast = vi.fn();
vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShowToast }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

// Mock API module
vi.mock("../../src/api/presets", () => ({
  getDevicePresets: vi.fn(),
  setPreset: vi.fn(),
  clearPreset: vi.fn(),
  syncPresetsFromDevice: vi.fn(),
}));

// Mock device hooks
const mockSetDeviceVolume = vi.fn();
const mockToggleMute = vi.fn();
let mockVolumeState = { volume: 45, muted: false, loading: false, setDeviceVolume: mockSetDeviceVolume, toggleMute: mockToggleMute };
vi.mock("../../src/hooks/useVolume", () => ({
  useVolume: () => mockVolumeState,
}));

vi.mock("../../src/hooks/useNowPlaying", () => ({
  useNowPlaying: () => ({ nowPlaying: null, loading: false, error: null, refresh: vi.fn() }),
}));

import * as presetsApi from "../../src/api/presets";
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
  default: ({ nowPlaying }: { nowPlaying: { title: string } | null }) => (
    <div data-testid="now-playing">{nowPlaying ? nowPlaying.title : "No playback"}</div>
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

vi.mock("../../src/components/PresetButton", () => ({
  default: ({ number, preset, onAssign, onPlay, isCurrentlyPlaying }: { number: number; preset: { station_name: string } | null; onAssign: () => void; onPlay: () => void; isCurrentlyPlaying?: boolean }) => (
    <div data-testid={`preset-${number}`}>
      <span>Preset {number}</span>
      {preset ? (
        <>
          <span data-testid={`preset-${number}-name`}>{preset.station_name}</span>
          <button onClick={onAssign} data-testid={`preset-${number}-change`}>
            Change
          </button>
          <button onClick={onPlay} data-testid={`preset-${number}-play`} disabled={isCurrentlyPlaying}>
            Play
          </button>
        </>
      ) : (
        <button onClick={onAssign} data-testid={`preset-${number}-assign`}>
          Assign
        </button>
      )}
    </div>
  ),
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
          onClick={() =>
            onStationSelect({
              stationuuid: "test-uuid",
              name: "Test Radio",
              country: "Germany",
              url: "http://test.com",
              homepage: "http://test-homepage.com",
              favicon: "http://test-favicon.com/icon.png",
            })
          }
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

describe("RadioPresets Page", () => {
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
    const result = render(<RadioPresets devices={devices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

      for (let i = 1; i <= 6; i++) {
        expect(screen.getByTestId(`preset-${i}`)).toBeInTheDocument();
      }
    });

    it("should show empty state when no devices available", async () => {
      await act(async () => {
        render(<RadioPresets devices={[]} />);
      });

      expect(screen.getByText("No devices found")).toBeInTheDocument();
      expect(screen.queryByTestId("device-swiper")).not.toBeInTheDocument();
    });
  });

  describe("Preset Assignment Flow", () => {
    it("should open radio search modal when clicking assign button", async () => {
      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
      });

      const assignButton = screen.getByTestId("preset-1-assign");
      fireEvent.click(assignButton);

      expect(screen.getByTestId("radio-search-modal")).toBeInTheDocument();
    });

    it("should assign station to preset when selected from search", async () => {
      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
      });

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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

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

  describe("Preset Playback", () => {
    it("should show play button for assigned preset", async () => {
      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
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

      // Click play - should not throw error (TODO: backend API in Phase 3)
      await act(async () => {
        fireEvent.click(screen.getByTestId("preset-3-play"));
      });

      // Verify play button still exists after click
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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-2-name")).toHaveTextContent("Delete Me");
      });

      // Open search → click delete
      fireEvent.click(screen.getByTestId("preset-2-change"));
      fireEvent.click(screen.getByTestId("search-delete-preset"));

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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

      expect(screen.getByTestId("device-swiper")).toBeInTheDocument();
    });

    it("should update displayed device when swiper index changes", async () => {
      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

      expect(screen.getByTestId("volume-slider")).toBeInTheDocument();
      expect(screen.getByTestId("volume-input")).toHaveValue("45");
    });

    it("should call setDeviceVolume when slider changes", async () => {
      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
      });

      const volumeInput = screen.getByTestId("volume-input");
      await act(async () => {
        fireEvent.change(volumeInput, { target: { value: "75" } });
      });

      expect(mockSetDeviceVolume).toHaveBeenCalledWith(75);
    });

    it("should call toggleMute when mute button clicked", async () => {
      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

      // Should display error message
      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toHaveTextContent("Presets konnten nicht geladen werden");
      });
    });

    it("should dismiss error message when clicking close", async () => {
      vi.mocked(presetsApi.getDevicePresets).mockRejectedValue(new Error("Network error"));

      await act(async () => {
        render(<RadioPresets devices={mockDevices} />);
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
        render(<RadioPresets devices={mockDevices} />);
      });

      // Try to assign preset
      fireEvent.click(screen.getByTestId("preset-1-assign"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should display error
      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toHaveTextContent("Preset konnte nicht gespeichert werden");
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
        render(<RadioPresets devices={mockDevices} />);
      });

      await waitFor(() => {
        expect(screen.getByTestId("preset-1-name")).toBeInTheDocument();
      });

      // Click change → select station (saves directly, no confirmation)
      fireEvent.click(screen.getByTestId("preset-1-change"));
      fireEvent.click(screen.getByTestId("select-station"));

      // Should display user-friendly error
      await waitFor(() => {
        expect(screen.getByTestId("error-message")).toHaveTextContent("Preset konnte nicht gespeichert werden");
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
      render(<RadioPresets devices={mockDevices} />);

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

      render(<RadioPresets devices={mockDevices} />);

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
});
