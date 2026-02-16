/**
 * Tests for VolumeSlider.tsx
 *
 * User Story: "Als User möchte ich die Lautstärke präzise steuern"
 *
 * Focus: Functional tests for volume control
 * - Volume adjustment (0-100)
 * - Mute/Unmute toggle
 * - Dynamic icon based on volume level
 * - Disabled state when muted
 * - Accessibility (aria-labels)
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import VolumeSlider from "../../src/components/VolumeSlider";

describe("VolumeSlider Component", () => {
  describe("Volume Display & Controls", () => {
    it("should display current volume value", () => {
      render(
        <VolumeSlider volume={45} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByText("45%")).toBeInTheDocument();
    });

    it("should update volume when slider changes", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider
          volume={50}
          onVolumeChange={mockOnVolumeChange}
          muted={false}
          onMuteToggle={vi.fn()}
        />
      );

      const slider = screen.getByRole("slider", { name: "Volume" });
      fireEvent.change(slider, { target: { value: "75" } });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(75);
    });

    it("should have correct slider range (0-100)", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      const slider = screen.getByRole("slider");
      expect(slider).toHaveAttribute("min", "0");
      expect(slider).toHaveAttribute("max", "100");
      expect(slider).toHaveAttribute("value", "50");
    });
  });

  describe("Mute Functionality", () => {
    it("should toggle mute when button clicked", () => {
      const mockOnMuteToggle = vi.fn();
      render(
        <VolumeSlider
          volume={50}
          onVolumeChange={vi.fn()}
          muted={false}
          onMuteToggle={mockOnMuteToggle}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: "Mute" }));

      expect(mockOnMuteToggle).toHaveBeenCalledTimes(1);
    });

    it("should disable slider when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );

      const slider = screen.getByRole("slider");
      expect(slider).toBeDisabled();
    });

    it("should show unmute label when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByRole("button", { name: "Unmute" })).toBeInTheDocument();
    });

    it("should show mute label when not muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByRole("button", { name: "Mute" })).toBeInTheDocument();
    });

    it("should apply muted CSS class when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );

      const muteButton = screen.getByRole("button", { name: "Unmute" });
      expect(muteButton).toHaveClass("muted");
    });
  });

  describe("Dynamic Icon Display", () => {
    it("should show mute icon (🔇) when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByText("🔇")).toBeInTheDocument();
    });

    it("should show high volume icon (🔊) when volume > 50", () => {
      render(
        <VolumeSlider volume={75} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByText("🔊")).toBeInTheDocument();
    });

    it("should show medium volume icon (🔉) when 0 < volume <= 50", () => {
      render(
        <VolumeSlider volume={30} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByText("🔉")).toBeInTheDocument();
    });

    it("should show low volume icon (🔈) when volume = 0", () => {
      render(
        <VolumeSlider volume={0} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByText("🔈")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle volume at boundary (exactly 50)", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      // volume === 50 should show medium icon (not high)
      expect(screen.getByText("🔉")).toBeInTheDocument();
    });

    it("should handle volume at maximum (100)", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider
          volume={100}
          onVolumeChange={mockOnVolumeChange}
          muted={false}
          onMuteToggle={vi.fn()}
        />
      );

      expect(screen.getByText("100%")).toBeInTheDocument();
      expect(screen.getByText("🔊")).toBeInTheDocument();
    });

    it("should parse string values to integers", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider
          volume={50}
          onVolumeChange={mockOnVolumeChange}
          muted={false}
          onMuteToggle={vi.fn()}
        />
      );

      const slider = screen.getByRole("slider");
      fireEvent.change(slider, { target: { value: "88" } });

      // parseInt should convert "88" to 88
      expect(mockOnVolumeChange).toHaveBeenCalledWith(88);
    });
  });

  describe("Accessibility", () => {
    it("should have aria-label on slider", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByRole("slider", { name: "Volume" })).toBeInTheDocument();
    });

    it("should have dynamic aria-label on mute button", () => {
      const { rerender } = render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByRole("button", { name: "Mute" })).toBeInTheDocument();

      rerender(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );

      expect(screen.getByRole("button", { name: "Unmute" })).toBeInTheDocument();
    });
  });
});
