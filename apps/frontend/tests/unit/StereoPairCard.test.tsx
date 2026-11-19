import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import StereoPairCard from "../../src/components/StereoPairCard";
import type { StereoPair } from "../../src/api/stereoPairs";

/** The components carry Cypress-style `data-test` attributes (not `data-testid`). */
const byTest = (name: string): HTMLElement => {
  const element = document.querySelector<HTMLElement>(`[data-test="${name}"]`);
  if (!element) throw new Error(`No element with data-test="${name}"`);
  return element;
};

const pair = (over: Partial<StereoPair> = {}): StereoPair => ({
  id: 7,
  name: "Office",
  status: "active",
  source: "oct",
  members: [
    { device_id: "L1", name: "Office left", role: "LEFT", reachable: true },
    { device_id: "R1", name: "Office right", role: "RIGHT", reachable: true },
  ],
  warnings: [],
  ...over,
});

const handlers = () => ({ onRename: vi.fn(), onDissolve: vi.fn(), onRepair: vi.fn() });

describe("StereoPairCard", () => {
  it("shows both speakers with their side and marks the left one as main speaker", () => {
    render(<StereoPairCard pair={pair()} busy={false} {...handlers()} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Office left");
    expect(items[0]).toHaveTextContent("Main speaker");
    expect(items[1]).toHaveTextContent("Office right");
    expect(items[1]).not.toHaveTextContent("Main speaker");
    expect(byTest("stereo-status")).toHaveTextContent("Active");
  });

  it("dissolves via the action button", () => {
    const h = handlers();
    render(<StereoPairCard pair={pair()} busy={false} {...h} />);

    fireEvent.click(screen.getByRole("button", { name: "Dissolve" }));

    expect(h.onDissolve).toHaveBeenCalledTimes(1);
  });

  it("renames on Enter and cancels on Escape", () => {
    const h = handlers();
    render(<StereoPairCard pair={pair()} busy={false} {...h} />);

    fireEvent.click(screen.getByRole("button", { name: /Office/ }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Living room" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(h.onRename).toHaveBeenCalledWith("Living room");

    fireEvent.click(screen.getByRole("button", { name: /Office/ }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Other" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });
    expect(h.onRename).toHaveBeenCalledTimes(1);
  });

  it("disables dissolve with a visible reason when a member is offline", () => {
    const members = pair().members.map((m) =>
      m.role === "RIGHT" ? { ...m, reachable: false } : m
    );
    render(<StereoPairCard pair={pair({ members })} busy={false} {...handlers()} />);

    const button = screen.getByRole("button", { name: "Dissolve" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(/Office right is offline/);
  });

  it("offers only repair on a degraded pair and blocks renaming", () => {
    const h = handlers();
    render(<StereoPairCard pair={pair({ status: "degraded" })} busy={false} {...h} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Only one speaker is paired");
    expect(screen.queryByRole("button", { name: "Dissolve" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Office/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Repair" }));
    expect(h.onRepair).toHaveBeenCalledTimes(1);
  });

  it("shows progress and a way back to the dialog while creating", () => {
    const onShowProgress = vi.fn();
    render(
      <StereoPairCard
        pair={pair({ id: -1, status: "creating" })}
        busy={false}
        progress={{ done: 2, total: 4 }}
        onShowProgress={onShowProgress}
        {...handlers()}
      />
    );

    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "2");
    expect(screen.queryByRole("button", { name: "Dissolve" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show progress" }));
    expect(onShowProgress).toHaveBeenCalledTimes(1);
  });

  it("marks pairs that were created outside OCT", () => {
    render(<StereoPairCard pair={pair({ source: "device" })} busy={false} {...handlers()} />);

    expect(screen.getByText("Imported")).toBeInTheDocument();
  });
});
