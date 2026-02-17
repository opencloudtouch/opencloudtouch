import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PresetButton, { type Preset } from "../../src/components/PresetButton";

describe("PresetButton Component", () => {
  const mockOnAssign = vi.fn();
  const mockOnClear = vi.fn();
  const mockOnPlay = vi.fn();

  const mockPreset: Preset = {
    station_name: "BBC Radio 1",
  };

  beforeEach(() => {
    mockOnAssign.mockClear();
    mockOnClear.mockClear();
    mockOnPlay.mockClear();
  });

  describe("Empty Preset", () => {
    it("renders empty state with placeholder text", () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );

      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("Preset zuweisen")).toBeInTheDocument();
    });

    it("renders empty state when preset is undefined", () => {
      render(
        <PresetButton
          number={2}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );

      expect(screen.getByText("2")).toBeInTheDocument();
      expect(screen.getByText("Preset zuweisen")).toBeInTheDocument();
    });

    it("calls onAssign when empty preset is clicked", () => {
      render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );

      const button = screen.getByText("Preset zuweisen").closest("button");
      fireEvent.click(button!);

      expect(mockOnAssign).toHaveBeenCalledTimes(1);
      expect(mockOnPlay).not.toHaveBeenCalled();
      expect(mockOnClear).not.toHaveBeenCalled();
    });

  });

  describe("Assigned Preset", () => {
    it("renders assigned preset with station name", () => {
      render(
        <PresetButton
          number={3}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );

      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("BBC Radio 1")).toBeInTheDocument();
    });

    it("calls onPlay when preset play button is clicked", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );

      const playButton = screen.getByText("BBC Radio 1").closest("button");
      fireEvent.click(playButton!);

      expect(mockOnPlay).toHaveBeenCalledTimes(1);
      expect(mockOnAssign).not.toHaveBeenCalled();
      expect(mockOnClear).not.toHaveBeenCalled();
    });

    it("calls onClear when clear button is clicked", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );

      const clearButton = screen.getByLabelText("Clear preset");
      fireEvent.click(clearButton);

      expect(mockOnClear).toHaveBeenCalledTimes(1);
      expect(mockOnAssign).not.toHaveBeenCalled();
      expect(mockOnPlay).not.toHaveBeenCalled();
    });

  });

  describe("Preset Number Display", () => {
    it("displays correct preset number for different slots", () => {
      const { rerender } = render(
        <PresetButton
          number={1}
          preset={null}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );
      expect(screen.getByText("1")).toBeInTheDocument();

      rerender(
        <PresetButton
          number={6}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onClear={mockOnClear}
          onPlay={mockOnPlay}
        />
      );
      expect(screen.getByText("6")).toBeInTheDocument();
    });

  });

});
