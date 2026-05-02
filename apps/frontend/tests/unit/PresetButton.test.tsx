import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PresetButton, { type Preset } from "../../src/components/PresetButton";

describe("PresetButton Component", () => {
  const mockOnAssign = vi.fn();
  const mockOnPlay = vi.fn();

  const mockPreset: Preset = {
    station_name: "BBC Radio 1",
  };

  beforeEach(() => {
    mockOnAssign.mockClear();
    mockOnPlay.mockClear();
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

    it("calls onPlay when play button is clicked", () => {
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

    it("disables play button when currently playing", () => {
      render(
        <PresetButton
          number={1}
          preset={mockPreset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
          isCurrentlyPlaying={true}
        />
      );

      const playButton = screen.getByLabelText("Now playing");
      expect(playButton).toBeDisabled();
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

  // ---------------------------------------------------------------------------
  // BUG-33: CloudBadge false positives for BMX URL presets
  // ---------------------------------------------------------------------------

  describe("BUG-33: BMX URL presets are cloud-independent", () => {
    /**
     * BMX presets have station_url = "https://content.api.bose.io/v1/...?data=BASE64"
     * where BASE64 = btoa(JSON.stringify({ streamUrl: "http://shoutcast.example.com/..." }))
     *
     * Old bug: isCloudDependent() saw "content.api.bose.io" → returned true → orange badge.
     * Fix: decode base64 data param → check actual streamUrl → return false if non-cloud.
     */

    const makeBmxPreset = (streamUrl: string): Preset => {
      const payload = btoa(JSON.stringify({ streamUrl }));
      return {
        station_name: "SHOUTcast Radio via BMX",
        source: "INTERNET_RADIO",
        station_url: `https://content.api.bose.io/v1/audio-content?type=r&data=${payload}`,
      };
    };

    it("shows compatible badge for BMX preset with shoutcast stream URL", () => {
      const preset = makeBmxPreset("http://shoutcast.example.com/stream.mp3");

      render(
        <PresetButton
          number={1}
          preset={preset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      // Compatible badge should be shown (not cloud-dependent)
      expect(
        screen.queryByRole("img", { name: /Compatible after cloud shutdown/i })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("img", { name: /Cloud-dependent/i })
      ).not.toBeInTheDocument();
    });

    it("shows cloud-dependent badge for BMX preset pointing to streaming.bose.com", () => {
      const preset = makeBmxPreset("http://streaming.bose.com/some-stream");

      render(
        <PresetButton
          number={1}
          preset={preset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      expect(
        screen.queryByRole("img", { name: /Cloud-dependent/i })
      ).toBeInTheDocument();
    });

    it("shows cloud-dependent badge when BMX base64 payload cannot be decoded", () => {
      const preset: Preset = {
        station_name: "BMX Broken Payload",
        source: "INTERNET_RADIO",
        station_url: "https://content.api.bose.io/v1/audio-content?type=r&data=NOT_VALID_BASE64!!!",
      };

      render(
        <PresetButton
          number={1}
          preset={preset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      // Safe default: cloud-dependent when we can't determine the real URL
      expect(
        screen.queryByRole("img", { name: /Cloud-dependent/i })
      ).toBeInTheDocument();
    });

    it("TUNEIN source is always cloud-dependent (not affected by BUG-33 fix)", () => {
      const preset: Preset = {
        station_name: "TuneIn Station",
        source: "TUNEIN",
        station_url: "http://shoutcast.example.com/stream.mp3",
      };

      render(
        <PresetButton
          number={1}
          preset={preset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      expect(
        screen.queryByRole("img", { name: /Cloud-dependent/i })
      ).toBeInTheDocument();
    });

    it("LOCAL_INTERNET_RADIO source is always cloud-independent", () => {
      const preset: Preset = {
        station_name: "OCT Local Station",
        source: "LOCAL_INTERNET_RADIO",
        station_url: "http://192.168.1.50/stream/radio.m3u",
      };

      render(
        <PresetButton
          number={1}
          preset={preset}
          onAssign={mockOnAssign}
          onPlay={mockOnPlay}
        />
      );

      expect(
        screen.queryByRole("img", { name: /Compatible after cloud shutdown/i })
      ).toBeInTheDocument();
    });
  });

});
