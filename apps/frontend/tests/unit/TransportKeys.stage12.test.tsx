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

describe("TransportKeys: shuffle and repeat", () => {
  it("shows nothing extra when the speaker reports nothing", () => {
    render(<TransportKeys {...base} />);
    expect(screen.queryByRole("button", { name: "Shuffle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Repeat" })).not.toBeInTheDocument();
  });

  it("shows only the reported setting", () => {
    const { rerender } = render(<TransportKeys {...base} shuffle="off" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Repeat" })).not.toBeInTheDocument();
    rerender(<TransportKeys {...base} repeat="off" />);
    expect(screen.queryByRole("button", { name: "Shuffle" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repeat" })).toBeInTheDocument();
  });

  it("hides both for radio, standby (no skip) and AUX", () => {
    const { rerender } = render(<TransportKeys {...base} showSkip={false} shuffle="on" repeat="all" />);
    expect(screen.queryByRole("button", { name: "Shuffle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Repeat" })).not.toBeInTheDocument();
    rerender(<TransportKeys {...base} noControl shuffle="on" repeat="all" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps constant names and sets aria-pressed", () => {
    const { rerender } = render(<TransportKeys {...base} shuffle="off" repeat="off" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Repeat" })).toHaveAttribute("aria-pressed", "false");
    rerender(<TransportKeys {...base} shuffle="on" repeat="all" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Repeat" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Repeat" })).toHaveAccessibleDescription("Repeat all");
    rerender(<TransportKeys {...base} shuffle="on" repeat="one" />);
    expect(screen.getByRole("button", { name: "Repeat" })).toHaveAccessibleDescription("Repeat one");
  });

  it("marks the badge decorative and only for repeat one", () => {
    const { rerender, container } = render(<TransportKeys {...base} repeat="all" />);
    expect(container.querySelector(".tp-badge")).toBeNull();
    rerender(<TransportKeys {...base} repeat="one" />);
    expect(container.querySelector(".tp-badge")).toHaveAttribute("aria-hidden", "true");
  });

  it("keeps the tab order previous, play, next, shuffle, repeat", () => {
    render(<TransportKeys {...base} shuffle="off" repeat="off" />);
    expect(screen.getAllByRole("button").map((b) => b.getAttribute("data-test"))).toEqual([
      "dv-PREV_TRACK",
      "dv-PLAY_PAUSE",
      "dv-NEXT_TRACK",
      "dv-SHUFFLE",
      "dv-REPEAT",
    ]);
  });

  it("sends the new key ids", () => {
    const onKey = vi.fn();
    render(<TransportKeys {...base} onKey={onKey} shuffle="off" repeat="off" />);
    fireEvent.click(screen.getByRole("button", { name: "Shuffle" }));
    fireEvent.click(screen.getByRole("button", { name: "Repeat" }));
    expect(onKey.mock.calls.map((c) => c[0])).toEqual(["SHUFFLE", "REPEAT"]);
  });

  it("busy: spinner on the pressed control, all keys disabled", () => {
    render(<TransportKeys {...base} busyKey="REPEAT" shuffle="off" repeat="all" />);
    expect(screen.getByRole("button", { name: "Repeat" })).toHaveAttribute("aria-busy", "true");
    for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
  });

  it("disables shuffle and repeat when locked", () => {
    render(<TransportKeys {...base} disabled shuffle="on" repeat="off" />);
    expect(screen.getByRole("button", { name: "Shuffle" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Repeat" })).toBeDisabled();
  });
});
