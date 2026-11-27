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

  it("keeps previous/next visible but disabled for radio and offers pause while playing", () => {
    render(<TransportKeys {...base} showSkip={false} playing />);

    expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Previous track" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next track" })).toBeDisabled();
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
  it("controls stay visible but disabled without settings", () => {
    const onKey = vi.fn();
    render(<TransportKeys {...base} onKey={onKey} shuffle={null} repeat={null} />);
    const shuffle = screen.getByRole("button", { name: "Shuffle" });
    const repeat = screen.getByRole("button", { name: /^Repeat/ });
    expect(shuffle).toBeDisabled();
    expect(shuffle).toHaveAttribute("aria-pressed", "false");
    expect(repeat).toBeDisabled();
    fireEvent.click(shuffle);
    fireEvent.click(repeat);
    expect(onKey).not.toHaveBeenCalled();
  });

  it("radio shows all keys but disables skip, shuffle and repeat", () => {
    render(<TransportKeys {...base} showSkip={false} shuffle="SHUFFLE_ON" repeat="REPEAT_ALL" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Repeat: all" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next track" })).toBeDisabled();
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

  it("enables only the setting the speaker reports and locks it while a key runs", () => {
    render(<TransportKeys {...base} repeat="REPEAT_ALL" busyKey="REPEAT" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toBeDisabled();
    const repeat = screen.getByRole("button", { name: "Repeat: all" });
    expect(repeat).toBeDisabled();
    expect(repeat).toHaveAttribute("aria-busy", "true");
  });
});
