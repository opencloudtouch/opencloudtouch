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

    expect(
      screen.getByText("Playback is controlled on the connected device.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("disables all keys when locked and marks the busy key", () => {
    const { rerender } = render(<TransportKeys {...base} disabled />);
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();

    rerender(<TransportKeys {...base} busyKey="NEXT_TRACK" />);
    expect(screen.getByRole("button", { name: "Next track" })).toHaveAttribute(
      "aria-busy",
      "true"
    );
    expect(screen.getByRole("button", { name: "Play" })).toBeDisabled();
  });
});
