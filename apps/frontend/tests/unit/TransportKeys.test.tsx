import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TransportKeys from "../../src/components/TransportKeys";

const base = {
  playing: false,
  showSkip: true,
  noControl: false,
  disabled: false,
  busyKey: null,
  onKey: vi.fn(),
};

describe("TransportKeys", () => {
  it("shows previous, play and next for sources with tracks", () => {
    const onKey = vi.fn();
    render(<TransportKeys {...base} onKey={onKey} />);

    fireEvent.click(screen.getByRole("button", { name: "Previous track" }));
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    fireEvent.click(screen.getByRole("button", { name: "Next track" }));
    expect(onKey.mock.calls.map((c) => c[0])).toEqual(["PREV_TRACK", "PLAY_PAUSE", "NEXT_TRACK"]);
  });

  it("shows only play/pause for radio and offers pause while playing", () => {
    render(<TransportKeys {...base} showSkip={false} playing />);

    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Previous track" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next track" })).not.toBeInTheDocument();
  });

  it("shows a note instead of keys for AUX", () => {
    render(<TransportKeys {...base} noControl />);

    expect(screen.getByText("Playback is controlled on the connected device.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("disables all keys when locked and marks the busy key", () => {
    const { rerender } = render(<TransportKeys {...base} disabled />);
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();

    rerender(<TransportKeys {...base} busyKey="NEXT_TRACK" />);
    expect(screen.getByRole("button", { name: "Next track" })).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Play" })).toBeDisabled();
  });

  it("disables skip with a hint for a single track", () => {
    const onKey = vi.fn();
    render(<TransportKeys {...base} skipDisabled onKey={onKey} />);
    const next = screen.getByRole("button", { name: "Next track" });
    expect(next).toHaveAttribute("aria-disabled", "true");
    expect(next).toHaveAttribute("title", "A single track has no queue");
    fireEvent.click(next);
    fireEvent.click(screen.getByRole("button", { name: "Previous track" }));
    expect(onKey).not.toHaveBeenCalled();
  });

  it("keeps skip enabled by default", () => {
    render(<TransportKeys {...base} />);
    expect(screen.getByRole("button", { name: "Next track" })).not.toHaveAttribute("aria-disabled");
  });
  it("controls hidden without settings", () => {
    const { rerender } = render(<TransportKeys {...base} shuffle={null} repeat={null} />);
    expect(screen.queryByRole("button", { name: "Shuffle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Repeat/ })).not.toBeInTheDocument();

    // Radio has no track controls, even when the speaker reports the settings.
    rerender(<TransportKeys {...base} showSkip={false} shuffle="SHUFFLE_ON" repeat="REPEAT_ALL" />);
    expect(screen.queryByRole("button", { name: "Shuffle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Repeat/ })).not.toBeInTheDocument();
  });

  it("buttons have accessible names and aria-pressed", () => {
    const onKey = vi.fn();
    const { rerender } = render(
      <TransportKeys {...base} onKey={onKey} shuffle="SHUFFLE_OFF" repeat="REPEAT_OFF" />
    );
    expect(screen.getByRole("button", { name: "Shuffle" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(screen.getByRole("button", { name: "Repeat: off" })).toBeInTheDocument();

    rerender(<TransportKeys {...base} onKey={onKey} shuffle="SHUFFLE_ON" repeat="REPEAT_ONE" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Shuffle" }));
    fireEvent.click(screen.getByRole("button", { name: "Repeat: one" }));
    expect(onKey.mock.calls.map((c) => c[0])).toEqual(["SHUFFLE", "REPEAT"]);
  });

  it("shows only the setting the speaker reports and locks it while a key runs", () => {
    render(<TransportKeys {...base} repeat="REPEAT_ALL" busyKey="REPEAT" />);
    expect(screen.queryByRole("button", { name: "Shuffle" })).not.toBeInTheDocument();
    const repeat = screen.getByRole("button", { name: "Repeat: all" });
    expect(repeat).toBeDisabled();
    expect(repeat).toHaveAttribute("aria-busy", "true");
  });
});
