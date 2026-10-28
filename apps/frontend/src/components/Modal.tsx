import { useEffect, useRef, type ReactNode } from "react";
import "./Modal.css";

/**
 * Modal: shared dialog on the native <dialog> element (showModal()).
 * Gives every dialog: focus trap + inert background (native), Esc, backdrop click, focus return to the opener,
 * body/main scroll lock, aria-labelledby/-describedby, role="alertdialog" variant, sizes sm | md | lg
 * (lg = full-screen sheet on phones <= 600px).
 * Put `data-autofocus` on the element that should get the first focus; otherwise the browser picks the first tabbable one.
 */
export interface ModalProps {
  open: boolean;
  onClose: () => void;
  /** id of the visible title element inside the dialog */
  labelledBy: string;
  describedBy?: string;
  size?: "sm" | "md" | "lg";
  role?: "dialog" | "alertdialog";
  /** click on the dimmed area closes (default true) */
  closeOnBackdrop?: boolean;
  /** native Esc calls onClose (default true); set false when the caller handles Esc itself */
  closeOnEscape?: boolean;
  /** extra attributes for the overlay / panel, e.g. { "data-test": "modal-overlay" } */
  overlayData?: Record<string, string>;
  panelData?: Record<string, string>;
  children: ReactNode;
}

let lockCount = 0;
function lockScroll() {
  if (lockCount++ === 0) document.body.classList.add("dlg-scroll-lock");
}
function unlockScroll() {
  if (--lockCount === 0) document.body.classList.remove("dlg-scroll-lock");
}

export default function Modal({
  open,
  onClose,
  labelledBy,
  describedBy,
  size = "md",
  role = "dialog",
  closeOnBackdrop = true,
  closeOnEscape = true,
  overlayData,
  panelData,
  children,
}: Readonly<ModalProps>) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    // jsdom has no showModal(): fall back to the open attribute
    if (typeof dialog.showModal === "function") {
      if (!dialog.open) dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    lockScroll();
    dialog.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => {
      unlockScroll();
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      // return focus to the opener; if it is gone (e.g. an empty preset became assigned) fall back to <main>
      if (opener?.isConnected) opener.focus();
      else document.getElementById("main-content")?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      className={`dlg dlg--${size}`}
      role={role}
      aria-modal="true"
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      onClick={(e) => {
        // a click on the backdrop lands on the overlay that fills the dialog, not on the panel
        if (
          closeOnBackdrop &&
          e.target instanceof Element &&
          e.target.classList.contains("dlg-overlay")
        ) {
          onClose();
        }
      }}
      onCancel={(e) => {
        e.preventDefault(); // React state stays the single source of truth
        if (closeOnEscape) onClose();
      }}
    >
      <div className="dlg-overlay" {...overlayData}>
        <div className="dlg-panel" {...panelData}>
          {children}
        </div>
      </div>
    </dialog>
  );
}
