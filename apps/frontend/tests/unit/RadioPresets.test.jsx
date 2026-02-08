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

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RadioPresets from '../../src/pages/RadioPresets';

// Mock child components
vi.mock('../../src/components/DeviceSwiper', () => ({
  default: ({ children, devices, currentIndex, onIndexChange }) => (
    <div data-testid="device-swiper">
      <button onClick={() => onIndexChange(0)}>Device 1</button>
      <button onClick={() => onIndexChange(1)}>Device 2</button>
      <div data-testid="swiper-content">{children}</div>
    </div>
  ),
}));

vi.mock('../../src/components/NowPlaying', () => ({
  default: ({ nowPlaying }) => (
    <div data-testid="now-playing">
      {nowPlaying ? nowPlaying.title : 'No playback'}
    </div>
  ),
}));

vi.mock('../../src/components/VolumeSlider', () => ({
  default: ({ volume, onVolumeChange, muted, onMuteToggle }) => (
    <div data-testid="volume-slider">
      <input
        type="range"
        value={volume}
        onChange={(e) => onVolumeChange(Number(e.target.value))}
        data-testid="volume-input"
      />
      <button onClick={onMuteToggle} data-testid="mute-button">
        {muted ? 'Unmute' : 'Mute'}
      </button>
    </div>
  ),
}));

vi.mock('../../src/components/PresetButton', () => ({
  default: ({ number, preset, onAssign, onClear, onPlay }) => (
    <div data-testid={`preset-${number}`}>
      <span>Preset {number}</span>
      {preset ? (
        <>
          <span data-testid={`preset-${number}-name`}>{preset.station_name}</span>
          <button onClick={onPlay} data-testid={`preset-${number}-play`}>Play</button>
          <button onClick={onClear} data-testid={`preset-${number}-clear`}>Clear</button>
        </>
      ) : (
        <button onClick={onAssign} data-testid={`preset-${number}-assign`}>Assign</button>
      )}
    </div>
  ),
}));

vi.mock('../../src/components/RadioSearch', () => ({
  default: ({ isOpen, onClose, onStationSelect }) => {
    if (!isOpen) return null;
    return (
      <div data-testid="radio-search-modal">
        <button onClick={onClose} data-testid="search-close">Close</button>
        <button
          onClick={() => onStationSelect({ name: 'Test Radio', url: 'http://test.com' })}
          data-testid="select-station"
        >
          Select Test Radio
        </button>
      </div>
    );
  },
}));

describe('RadioPresets Page', () => {
  const mockDevices = [
    {
      device_id: 'AABBCC123456',
      name: 'Living Room',
      model: 'SoundTouch 30',
      ip: '192.168.1.101',
    },
    {
      device_id: 'DDEEFF789012',
      name: 'Küche',
      model: 'SoundTouch 10',
      ip: '192.168.1.102',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Device Display', () => {
    it('should display current device information', () => {
      render(<RadioPresets devices={mockDevices} />);

      // Component uses data-test, not data-testid, so use text queries
      expect(screen.getByText('Living Room')).toBeInTheDocument();
      expect(screen.getByText('SoundTouch 30')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.101')).toBeInTheDocument();
    });

    it('should show all 6 preset buttons', () => {
      render(<RadioPresets devices={mockDevices} />);

      for (let i = 1; i <= 6; i++) {
        expect(screen.getByTestId(`preset-${i}`)).toBeInTheDocument();
      }
    });

    it('should show empty state when no devices available', () => {
      render(<RadioPresets devices={[]} />);

      expect(screen.getByText('Keine Geräte gefunden')).toBeInTheDocument();
      expect(screen.queryByTestId('device-swiper')).not.toBeInTheDocument();
    });
  });

  describe('Preset Assignment Flow', () => {
    it('should open radio search modal when clicking assign button', () => {
      render(<RadioPresets devices={mockDevices} />);

      const assignButton = screen.getByTestId('preset-1-assign');
      fireEvent.click(assignButton);

      expect(screen.getByTestId('radio-search-modal')).toBeInTheDocument();
    });

    it('should assign station to preset when selected from search', async () => {
      render(<RadioPresets devices={mockDevices} />);

      // Open search for preset 1
      const assignButton = screen.getByTestId('preset-1-assign');
      fireEvent.click(assignButton);

      // Select station
      const selectButton = screen.getByTestId('select-station');
      fireEvent.click(selectButton);

      // Verify preset is assigned
      await waitFor(() => {
        expect(screen.getByTestId('preset-1-name')).toHaveTextContent('Test Radio');
      });

      // Note: Modal remains open (component behavior - user must close manually)
    });

    it('should close search modal when clicking close button', () => {
      render(<RadioPresets devices={mockDevices} />);

      // Open search
      fireEvent.click(screen.getByTestId('preset-2-assign'));
      expect(screen.getByTestId('radio-search-modal')).toBeInTheDocument();

      // Close search
      fireEvent.click(screen.getByTestId('search-close'));
      expect(screen.queryByTestId('radio-search-modal')).not.toBeInTheDocument();
    });

    it('should allow assigning different stations to different presets', async () => {
      render(<RadioPresets devices={mockDevices} />);

      // Assign to preset 1
      fireEvent.click(screen.getByTestId('preset-1-assign'));
      fireEvent.click(screen.getByTestId('select-station'));

      await waitFor(() => {
        expect(screen.getByTestId('preset-1-name')).toHaveTextContent('Test Radio');
      });

      // Assign to preset 2
      fireEvent.click(screen.getByTestId('preset-2-assign'));
      fireEvent.click(screen.getByTestId('select-station'));

      await waitFor(() => {
        expect(screen.getByTestId('preset-2-name')).toHaveTextContent('Test Radio');
      });

      // Both presets should be assigned
      expect(screen.getByTestId('preset-1-name')).toBeInTheDocument();
      expect(screen.getByTestId('preset-2-name')).toBeInTheDocument();
    });
  });

  describe('Preset Playback', () => {
    it('should show play button for assigned preset', async () => {
      render(<RadioPresets devices={mockDevices} />);

      // Assign preset first
      fireEvent.click(screen.getByTestId('preset-3-assign'));
      fireEvent.click(screen.getByTestId('select-station'));

      await waitFor(() => {
        expect(screen.getByTestId('preset-3-play')).toBeInTheDocument();
      });

      // Click play - should not throw error (TODO: backend API in Phase 3)
      fireEvent.click(screen.getByTestId('preset-3-play'));

      // Verify play button still exists after click
      expect(screen.getByTestId('preset-3-play')).toBeInTheDocument();
    });
  });

  describe('Preset Clearing', () => {
    it('should clear assigned preset when clicking clear button', async () => {
      render(<RadioPresets devices={mockDevices} />);

      // Assign preset
      fireEvent.click(screen.getByTestId('preset-4-assign'));
      fireEvent.click(screen.getByTestId('select-station'));

      await waitFor(() => {
        expect(screen.getByTestId('preset-4-name')).toBeInTheDocument();
      });

      // Clear preset
      fireEvent.click(screen.getByTestId('preset-4-clear'));

      // Should show assign button again
      await waitFor(() => {
        expect(screen.getByTestId('preset-4-assign')).toBeInTheDocument();
        expect(screen.queryByTestId('preset-4-name')).not.toBeInTheDocument();
      });
    });

    it('should maintain other presets when clearing one', async () => {
      render(<RadioPresets devices={mockDevices} />);

      // Assign two presets
      fireEvent.click(screen.getByTestId('preset-1-assign'));
      fireEvent.click(screen.getByTestId('select-station'));
      await waitFor(() => expect(screen.getByTestId('preset-1-name')).toBeInTheDocument());

      fireEvent.click(screen.getByTestId('preset-2-assign'));
      fireEvent.click(screen.getByTestId('select-station'));
      await waitFor(() => expect(screen.getByTestId('preset-2-name')).toBeInTheDocument());

      // Clear preset 1
      fireEvent.click(screen.getByTestId('preset-1-clear'));

      // Preset 1 should be cleared, preset 2 should remain
      await waitFor(() => {
        expect(screen.getByTestId('preset-1-assign')).toBeInTheDocument();
        expect(screen.getByTestId('preset-2-name')).toBeInTheDocument();
      });
    });
  });

  describe('Device Switching', () => {
    it('should render DeviceSwiper component', () => {
      render(<RadioPresets devices={mockDevices} />);

      expect(screen.getByTestId('device-swiper')).toBeInTheDocument();
    });

    it('should update displayed device when swiper index changes', () => {
      render(<RadioPresets devices={mockDevices} />);

      // Initially shows first device
      expect(screen.getByText('Living Room')).toBeInTheDocument();

      // Switch to second device
      fireEvent.click(screen.getByText('Device 2'));

      // Should show second device
      expect(screen.getByText('Küche')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.102')).toBeInTheDocument();
    });
  });

  describe('Volume Control', () => {
    it('should render volume slider', () => {
      render(<RadioPresets devices={mockDevices} />);

      expect(screen.getByTestId('volume-slider')).toBeInTheDocument();
      expect(screen.getByTestId('volume-input')).toHaveValue('45');
    });

    it('should update volume when slider changes', () => {
      render(<RadioPresets devices={mockDevices} />);

      const volumeInput = screen.getByTestId('volume-input');
      fireEvent.change(volumeInput, { target: { value: '75' } });

      expect(volumeInput).toHaveValue('75');
    });

    it('should toggle mute state', () => {
      render(<RadioPresets devices={mockDevices} />);

      const muteButton = screen.getByTestId('mute-button');

      // Initially not muted
      expect(muteButton).toHaveTextContent('Mute');

      // Toggle mute
      fireEvent.click(muteButton);
      expect(muteButton).toHaveTextContent('Unmute');

      // Toggle back
      fireEvent.click(muteButton);
      expect(muteButton).toHaveTextContent('Mute');
    });
  });
});
