/**
 * Functional Tests for LocalControl Component
 *
 * User Story: "Als User möchte ich meine Musik steuern (Play/Pause/Skip/Volume)"
 *
 * Test Strategy: Behaviour-driven testing focusing on user interactions
 * Coverage: Play/Pause, Skip, Volume, Standby, Source Selection, Error Handling
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
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
  });

  /**
   * TEST 1: Empty State Handling
   * User Story: Als User möchte ich wissen wenn keine Geräte verfügbar sind
   */
  test("should show empty state when no devices available", async () => {
    await act(async () => {
      render(<LocalControl devices={[]} />);
    });

    expect(screen.getByText(/Keine Geräte gefunden/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /play/i })).not.toBeInTheDocument();
  });

  /**
   * TEST 2: Device Display
   * User Story: Als User möchte ich sehen welches Gerät ich steuere
   */
  test("should display current device name and model", async () => {
    await act(async () => {
      render(<LocalControl devices={mockDevices} />);
    });

    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(screen.getByText("SoundTouch 10")).toBeInTheDocument();
  });

  /**
   * TEST 3: Play/Pause Toggle
   * User Story: Als User möchte ich Wiedergabe starten und pausieren
   */
  test("should toggle play/pause when play button clicked", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    // Find by icon text since there's no aria-label
    const playPauseButton = screen.getByText("⏸️").closest("button")!;

    // Initial state: Playing (shows pause icon)
    expect(playPauseButton).toHaveTextContent("⏸️");

    // Click to pause
    await user.click(playPauseButton);
    expect(playPauseButton).toHaveTextContent("▶️");

    // Click to play again
    await user.click(playPauseButton);
    expect(playPauseButton).toHaveTextContent("⏸️");
  });

  /**
   * TEST 4: Volume Control
   * User Story: Als User möchte ich die Lautstärke ändern können
   */
  test("should update volume when slider changed", async () => {
    render(<LocalControl devices={mockDevices} />);

    const volumeSlider = screen.getByRole("slider");
    const volumeDisplay = screen.getByText(/45%/); // Initial volume

    expect(volumeDisplay).toBeInTheDocument();

    // Change volume to 75 using fireEvent (range inputs need onChange simulation)
    fireEvent.change(volumeSlider, { target: { value: "75" } });

    await waitFor(() => {
      expect(screen.getByText(/75%/)).toBeInTheDocument();
    });
  });

  /**
   * TEST 5: Mute Functionality
   * User Story: Als User möchte ich den Ton stumm schalten können
   */
  test("should mute and unmute volume", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const muteButton = screen.getByRole("button", { name: /Stumm/i });

    // Initial: Not muted
    expect(screen.getByText(/45%/)).toBeInTheDocument();
    expect(muteButton).toHaveTextContent("🔊");

    // Click to mute
    await user.click(muteButton);

    await waitFor(() => {
      expect(screen.getByText(/0%/)).toBeInTheDocument(); // Volume shows 0
      expect(screen.getByRole("button", { name: /Ton an/i })).toBeInTheDocument();
    });

    // Click to unmute
    const unmuteButton = screen.getByRole("button", { name: /Ton an/i });
    await user.click(unmuteButton);

    await waitFor(() => {
      expect(screen.getByText(/45%/)).toBeInTheDocument(); // Volume restored
    });
  });

  /**
   * TEST 6: Previous Track
   * User Story: Als User möchte ich zum vorherigen Track springen
   */
  test("previous track button should be disabled until API is implemented", async () => {
    render(<LocalControl devices={mockDevices} />);

    const previousButton = screen.getByText("⏮").closest("button")!;

    // Button is disabled until Phase 3 implementation
    expect(previousButton).toBeDisabled();
    expect(previousButton).toHaveAttribute("title", "Kommt in Phase 3");
  });

  /**
   * TEST 7: Next Track
   * User Story: Als User möchte ich zum nächsten Track springen
   */
  test("next track button should be disabled until API is implemented", async () => {
    render(<LocalControl devices={mockDevices} />);

    const nextButton = screen.getByText("⏭").closest("button")!;

    // Button is disabled until Phase 3 implementation
    expect(nextButton).toBeDisabled();
    expect(nextButton).toHaveAttribute("title", "Kommt in Phase 3");
  });

  /**
   * TEST 8: Standby Mode
   * User Story: Als User möchte ich das Gerät in Standby versetzen
   */
  test("standby button should be disabled until API is implemented", async () => {
    render(<LocalControl devices={mockDevices} />);

    const standbyButton = screen.getByRole("button", { name: /Standby/i });

    // Button is disabled until Phase 3 implementation
    expect(standbyButton).toBeDisabled();
    expect(standbyButton).toHaveAttribute("title", "Kommt in Phase 3");
  });
});

describe("LocalControl - Source Selection", () => {
  /**
   * TEST 9: Source Switching
   * User Story: Als User möchte ich zwischen Quellen wechseln (Radio, Bluetooth, AUX)
   */
  test("should switch between available sources", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    // Initial source: Internet Radio
    const radioTab = screen.getByRole("button", { name: /Radio/i });
    expect(radioTab).toHaveClass("active");

    // Switch to Bluetooth
    const bluetoothTab = screen.getByRole("button", { name: /Bluetooth/i });
    await user.click(bluetoothTab);

    expect(bluetoothTab).toHaveClass("active");
    expect(radioTab).not.toHaveClass("active");

    // Switch to AUX
    const auxTab = screen.getByRole("button", { name: /AUX/i });
    await user.click(auxTab);

    expect(auxTab).toHaveClass("active");
    expect(bluetoothTab).not.toHaveClass("active");
  });

  /**
   * TEST 10: Conditional AirPlay Support
   * User Story: Als User möchte ich AirPlay nur sehen wenn das Gerät es unterstützt
   */
  test("should show AirPlay only when device supports it", async () => {
    let rerender: (ui: React.ReactElement) => void;
    await act(async () => {
      const result = render(<LocalControl devices={[mockDevices[0]!]} />);
      rerender = result.rerender;
    });

    // ST10 (no AirPlay support)
    expect(screen.queryByRole("button", { name: /AirPlay/i })).not.toBeInTheDocument();

    // ST30 (with AirPlay support)
    await act(async () => {
      rerender(<LocalControl devices={[mockDevices[1]!]} />);
    });
    expect(screen.getByRole("button", { name: /AirPlay/i })).toBeInTheDocument();
  });

  /**
   * TEST 11: Disabled Controls for AUX Source
   * User Story: Als User möchte ich wissen dass Play/Pause bei AUX nicht verfügbar ist
   */
  test("should disable playback controls when AUX source selected", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const auxTab = screen.getByRole("button", { name: /AUX/i });
    await user.click(auxTab);

    // Playback buttons should be disabled for AUX
    const playPauseButton = screen.getByText("⏸️").closest("button");
    const previousButton = screen.getByText("⏮").closest("button");
    const nextButton = screen.getByText("⏭").closest("button");

    expect(playPauseButton).toBeDisabled();
    expect(previousButton).toBeDisabled();
    expect(nextButton).toBeDisabled();
  });
});

describe("LocalControl - Multi-Device Handling", () => {
  /**
   * TEST 12: Volume Reset on Device Change
   * User Story: Als User möchte ich dass Lautstärke zurückgesetzt wird beim Gerätewechsel
   */
  test("should reset volume and mute when switching devices", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    // Change volume on first device
    const volumeSlider = screen.getByRole("slider");
    fireEvent.change(volumeSlider, { target: { value: "80" } });

    await waitFor(() => {
      expect(screen.getByText(/80%/)).toBeInTheDocument();
    });

    // Switch to second device using tab selector
    const secondDeviceTab = screen.getByRole("tab", { name: /Schlafzimmer/i });
    await user.click(secondDeviceTab);

    // Volume should reset to 45%
    await waitFor(() => {
      expect(screen.getByText(/45%/)).toBeInTheDocument();
      expect(screen.getByText("Schlafzimmer")).toBeInTheDocument();
    });
  });
});

describe("LocalControl - Edge Cases", () => {
  /**
   * TEST 13: Volume Boundaries
   * User Story: Als User möchte ich Lautstärke von 0-100 einstellen können
   */
  test("should handle volume min and max values", async () => {
    render(<LocalControl devices={mockDevices} />);

    const volumeSlider = screen.getByRole("slider");

    // Test minimum (0)
    fireEvent.change(volumeSlider, { target: { value: "0" } });
    await waitFor(() => {
      expect(screen.getByText(/0%/)).toBeInTheDocument();
    });

    // Test maximum (100)
    fireEvent.change(volumeSlider, { target: { value: "100" } });
    await waitFor(() => {
      expect(screen.getByText(/100%/)).toBeInTheDocument();
    });
  });

  /**
   * TEST 14: Volume Slider Disabled When Muted
   * User Story: Als User sollte der Volume-Slider deaktiviert sein wenn stumm geschaltet
   */
  test("should disable volume slider when muted", async () => {
    const user = userEvent.setup();
    render(<LocalControl devices={mockDevices} />);

    const volumeSlider = screen.getByRole("slider");
    const muteButton = screen.getByRole("button", { name: /Stumm/i });

    // Initially slider is enabled
    expect(volumeSlider).toBeEnabled();

    // Mute
    await user.click(muteButton);

    // Slider should be disabled
    await waitFor(() => {
      expect(volumeSlider).toBeDisabled();
    });
  });

  /**
   * TEST 15: Device Model Fallback
   * User Story: "Unknown Model" wird angezeigt wenn kein Modell bekannt
   */
  test("should display Unknown Model when device model is missing", async () => {
    const deviceWithoutModel = [
      { device_id: "1", name: "Test Device", ip: "192.168.1.10" },
    ];
    render(<LocalControl devices={deviceWithoutModel} />);

    await waitFor(() => {
      expect(screen.getByText("Unknown Model")).toBeInTheDocument();
    });
  });
});
