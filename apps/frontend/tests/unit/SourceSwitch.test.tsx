import { describe, it, expect, vi } from "vitest";
import type { ComponentProps } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import SourceSwitch from "../../src/components/SourceSwitch";

const setup = (props: Partial<ComponentProps<typeof SourceSwitch>> = {}) => {
  const onSelect = vi.fn();
  render(
    <SourceSwitch
      current="presets"
      switching={null}
      disabled={false}
      onSelect={onSelect}
      {...props}
    />
  );
  return onSelect;
};

describe("SourceSwitch", () => {
  it("is a group of three buttons and presses the current source", () => {
    setup({ current: "bluetooth" });

    expect(screen.getByRole("group", { name: "Choose source" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Presets" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(screen.getByRole("button", { name: "Bluetooth" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: "AUX" })).toHaveAttribute("aria-pressed", "false");
  });

  it("selects another source, but not the one that is already pressed", () => {
    const onSelect = setup({ current: "presets" });

    fireEvent.click(screen.getByRole("button", { name: "Presets" }));
    expect(onSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "AUX" }));
    expect(onSelect).toHaveBeenCalledWith("aux");
  });

  it("presses nothing when the device plays a source that cannot be chosen here", () => {
    setup({ current: null });

    for (const name of ["Presets", "Bluetooth", "AUX"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("aria-pressed", "false");
    }
  });

  it("marks the target busy during a switch and ignores clicks", () => {
    const onSelect = setup({ current: "presets", switching: "aux", disabled: true });

    const aux = screen.getByRole("button", { name: "AUX" });
    expect(aux).toHaveAttribute("aria-busy", "true");
    expect(aux).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(aux);
    fireEvent.click(screen.getByRole("button", { name: "Bluetooth" }));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("is one tab stop (the pressed button) and moves with the arrow keys", () => {
    setup({ current: "bluetooth" });

    const presets = screen.getByRole("button", { name: "Presets" });
    const bluetooth = screen.getByRole("button", { name: "Bluetooth" });
    const aux = screen.getByRole("button", { name: "AUX" });
    expect(bluetooth).toHaveAttribute("tabindex", "0");
    expect(presets).toHaveAttribute("tabindex", "-1");
    expect(aux).toHaveAttribute("tabindex", "-1");

    bluetooth.focus();
    fireEvent.keyDown(bluetooth, { key: "ArrowRight" });
    expect(aux).toHaveFocus();
    fireEvent.keyDown(aux, { key: "ArrowRight" });
    expect(presets).toHaveFocus();
    fireEvent.keyDown(presets, { key: "ArrowLeft" });
    expect(aux).toHaveFocus();
    fireEvent.keyDown(aux, { key: "Home" });
    expect(presets).toHaveFocus();
    fireEvent.keyDown(presets, { key: "End" });
    expect(aux).toHaveFocus();
  });

  it("makes Presets the tab stop when the source cannot be chosen here", () => {
    setup({ current: null });
    expect(screen.getByRole("button", { name: "Presets" })).toHaveAttribute("tabindex", "0");
  });

  it("points to the explanation why it is disabled", () => {
    setup({ disabled: true, describedBy: "why" });
    expect(screen.getByRole("button", { name: "AUX" })).toHaveAttribute("aria-describedby", "why");
  });
});
