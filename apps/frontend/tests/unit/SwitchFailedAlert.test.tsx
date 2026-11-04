import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SwitchFailedAlert from "../../src/components/SwitchFailedAlert";

describe("SwitchFailedAlert", () => {
  it("offers retry and close as buttons", () => {
    const onRetry = vi.fn();
    const onClose = vi.fn();
    render(<SwitchFailedAlert sourceLabel="AUX" onRetry={onRetry} onClose={onClose} />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);

    fireEvent.click(buttons[0]);
    expect(onRetry).toHaveBeenCalledTimes(1);
    fireEvent.click(buttons[1]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape and stops listening after unmount", () => {
    const onClose = vi.fn();
    const { unmount } = render(
      <SwitchFailedAlert sourceLabel="AUX" onRetry={vi.fn()} onClose={onClose} />
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    unmount();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
