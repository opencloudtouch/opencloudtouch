import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PresetButton, { type Preset } from "../../src/components/PresetButton";

describe("PresetButton Component", () => {
  const mockOnAssign = vi.fn();
  const mockOnPlay = vi.fn();
  const mockOnPause = vi.fn();

  const mockPreset: Preset = {
    station_name: "BBC Radio 1",
  };

  beforeEach(() => {
    mockOnAssign.mockClear();
    mockOnPlay.mockClear();
    mockOnPause.mockClear();
  });

  describe("Empty Preset", () => {
    it("renders empty state with placeholder text", () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("Assign preset")).toBeInTheDocument();
    });

    it("renders empty state when preset is undefined", () => {
      render(
        <PresetButton
          number={2}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("Assign preset")).toBeInTheDocument();
    });

    it("calls onAssign when empty preset is clicked", () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      const button = screen.getByText("Assign preset").closest("button");
      fireEvent.click(button!);

      expect(mockOnAssign).toHaveBeenCalledTimes(1);
      expect(mockOnPlay).not.toHaveBeenCalled();
    });

  });

  describe("Assigned Preset", () => {
    it("renders assigned preset with station name", () => {
      render(
        <PresetButton
          number={3}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("BBC Radio 1")).toBeInTheDocument();
    });

    it("calls onAssign when preset info area is clicked", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      const infoButton = screen.getByText("BBC Radio 1").closest("button");
      fireEvent.click(infoButton!);

      expect(mockOnAssign).toHaveBeenCalledTimes(1);
      expect(mockOnPlay).not.toHaveBeenCalled();
    });

    it("calls onPlay when play button is clicked (not onAssign)", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      const playButton = screen.getByLabelText(/Play preset/i);
      fireEvent.click(playButton);

      expect(mockOnPlay).toHaveBeenCalledTimes(1);
      expect(mockOnAssign).not.toHaveBeenCalled();
    });

    it("shows station avatar when no favicon", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      // BBC Radio 1 → initials "BR"
      expect(screen.getByText("BR")).toBeInTheDocument();
    });

    it("shows playing state when currently playing", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          isCurrentlyPlaying={true}
        />
      );

      const pauseButton = screen.getByLabelText("Pause");
      expect(pauseButton).toBeInTheDocument();
      expect(pauseButton).toHaveClass("playing");
    });

  });

  describe("Preset Number Display", () => {
    it("displays correct preset number for different slots", () => {
      const { rerender } = render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );
      expect(screen.getByText("1")).toBeInTheDocument();

      rerender(
        <PresetButton
          number={6}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );
      expect(screen.getByText("6")).toBeInTheDocument();
    });

  });

  describe("Play/Pause Toggle", () => {
    it("calls onPause when pause button is clicked while playing", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          onPause={mockOnPause}
          isCurrentlyPlaying={true}
        />
      );

      const pauseButton = screen.getByLabelText("Pause");
      fireEvent.click(pauseButton);

      expect(mockOnPause).toHaveBeenCalledTimes(1);
      expect(mockOnPlay).not.toHaveBeenCalled();
    });

    it("calls onPlay when play button is clicked while not playing", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          onPause={mockOnPause}
          isCurrentlyPlaying={false}
        />
      );

      const playButton = screen.getByLabelText(/Play preset/i);
      fireEvent.click(playButton);

      expect(mockOnPlay).toHaveBeenCalledTimes(1);
      expect(mockOnPause).not.toHaveBeenCalled();
    });

    it("does not crash when onPause is not provided and playing", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          isCurrentlyPlaying={true}
        />
      );

      const pauseButton = screen.getByLabelText("Pause");
      fireEvent.click(pauseButton);
      // Should not throw — onPause is optional
      expect(mockOnPlay).not.toHaveBeenCalled();
    });
  });

  describe("Favicon Error Handling", () => {
    it("hides favicon and shows avatar fallback on image error", () => {
      const presetWithFavicon: Preset = {
        station_name: "Test Station",
        station_favicon: "https://example.com/broken.png",
      };

      render(
        <PresetButton
          number={1}
          preset={presetWithFavicon}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      const img = document.querySelector(".preset-favicon") as HTMLImageElement;
      fireEvent.error(img);

      expect((img as HTMLImageElement).style.display).toBe("none");
    });
  });

  describe("Disabled State", () => {
    it("renders disabled preset with station name", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          disabled={true}
        />
      );

      expect(screen.getByText("BBC Radio 1")).toBeInTheDocument();
      const container = screen.getByTestId("preset-1");
      expect(container).toHaveClass("preset-disabled");
    });

    it("renders disabled preset with fallback text when no station name", () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          disabled={true}
        />
      );

      const container = screen.getByTestId("preset-1");
      expect(container).toHaveClass("preset-disabled");
    });
  });

});
