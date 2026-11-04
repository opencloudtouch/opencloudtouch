import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Modal from "../../src/components/Modal";

function renderModal(props: Partial<React.ComponentProps<typeof Modal>> = {}) {
  return render(
    <Modal open onClose={vi.fn()} labelledBy="m-title" {...props}>
      <h2 id="m-title">Title</h2>
    </Modal>,
  );
}

describe("Modal", () => {
  it("relies on the native dialog semantics (no redundant role or aria-modal)", () => {
    renderModal();
    const dialog = document.querySelector("dialog")!;
    expect(dialog).toHaveAttribute("open");
    expect(dialog).not.toHaveAttribute("role");
    expect(dialog).not.toHaveAttribute("aria-modal");
    expect(dialog).toHaveAttribute("aria-labelledby", "m-title");
    expect(screen.getByRole("dialog")).toBe(dialog);
  });

  it("keeps an explicit alertdialog role", () => {
    renderModal({ role: "alertdialog" });
    expect(screen.getByRole("alertdialog")).toBe(document.querySelector("dialog"));
  });

  it("renders nothing while closed", () => {
    renderModal({ open: false });
    expect(document.querySelector("dialog")).toBeNull();
  });
});
