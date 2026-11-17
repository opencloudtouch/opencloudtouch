import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import DlnaRemoveDialog from "../../src/components/dlna/DlnaRemoveDialog";
import type { DlnaSetupApi } from "../../src/components/dlna/dlnaSetupTypes";

const api = {
  slots: vi.fn().mockResolvedValue([{ preset_number: 2, name: "Example Folder" }]),
  remove: vi.fn().mockResolvedValue(undefined),
} as unknown as DlnaSetupApi;

describe("DlnaRemoveDialog focus", () => {
  it("puts the focus on Cancel when it opens and keeps it there after the presets loaded", async () => {
    render(
      <DlnaRemoveDialog api={api} serverId="srv" serverName="Example Server" onClose={vi.fn()} />
    );
    const dialog = document.querySelector("dialog")!;
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    expect(document.activeElement).toHaveTextContent("Cancel");

    await waitFor(() => expect(screen.getByRole("alertdialog")).toBeInTheDocument());
    expect(document.activeElement).toHaveTextContent("Cancel");
  });
});
