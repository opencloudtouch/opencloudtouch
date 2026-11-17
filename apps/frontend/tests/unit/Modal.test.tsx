import { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

describe("Modal focus return", () => {
  function Harness({ remount }: Readonly<{ remount: boolean }>) {
    const [open, setOpen] = useState(false);
    const [version, setVersion] = useState(0);
    return (
      <>
        <button
          key={remount ? version : 0}
          data-testid="opener"
          onClick={() => setOpen(true)}
        >
          Open
        </button>
        <Modal open={open} onClose={() => setOpen(false)} labelledBy="m-title">
          <h2 id="m-title">Title</h2>
          <button onClick={() => setVersion((v) => v + 1)}>Inside</button>
        </Modal>
      </>
    );
  }

  it("returns the focus to the opener after Escape", () => {
    render(<Harness remount={false} />);
    const opener = screen.getByTestId("opener");
    opener.focus();
    fireEvent.click(opener);
    fireEvent(document.querySelector("dialog")!, new Event("cancel", { cancelable: true }));

    expect(opener).toHaveFocus();
  });

  it("returns the focus to the replacement when the opener was re-created while open", () => {
    render(<Harness remount />);
    const opener = screen.getByTestId("opener");
    opener.focus();
    fireEvent.click(opener);
    fireEvent.click(screen.getByText("Inside"));
    expect(opener.isConnected).toBe(false);
    fireEvent(document.querySelector("dialog")!, new Event("cancel", { cancelable: true }));

    expect(screen.getByTestId("opener")).toHaveFocus();
  });
});
