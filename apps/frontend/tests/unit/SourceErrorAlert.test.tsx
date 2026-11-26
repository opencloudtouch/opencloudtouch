import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SourceErrorAlert from "../../src/components/dlna/SourceErrorAlert";
import { i18next } from "../../src/i18n";

describe("SourceErrorAlert", () => {
  it.each([
    [1608, "devices.sourceError.notFound.title"],
    [1602, "devices.sourceError.serviceUnreachable.title"],
    [1604, "devices.sourceError.badFormat.title"],
    [1615, "devices.sourceError.subFolders.title"],
    [1699, "devices.sourceError.generic.title"],
  ])("shows the mapped message for code %i", (code, key) => {
    render(<SourceErrorAlert code={code} onDismiss={vi.fn()} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(i18next.t(key));
    expect(alert).toHaveTextContent(i18next.t(key.replace(".title", ".body")));
  });

  it("uses the warning style for 1604 and 1615, error otherwise", () => {
    const { rerender } = render(<SourceErrorAlert code={1604} onDismiss={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveClass("wz-status--warning");
    rerender(<SourceErrorAlert code={1608} onDismiss={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveClass("wz-status--error");
  });

  it("has a dismiss button", () => {
    const onDismiss = vi.fn();
    render(<SourceErrorAlert code={1608} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("Escape dismisses", () => {
    const onDismiss = vi.fn();
    render(<SourceErrorAlert code={1608} onDismiss={onDismiss} />);
    fireEvent.keyDown(screen.getByRole("alert"), { key: "Escape" });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
