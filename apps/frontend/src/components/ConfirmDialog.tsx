import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import Modal from "./Modal";

/**
 * ConfirmDialog — accessible modal replacement for window.confirm().
 *
 * REFACT-107: Native browser dialogs block the main thread and cannot
 * be styled. This component renders an alertdialog on the shared Modal
 * (native <dialog>: focus trap, inert background, focus return).
 *
 * Usage:
 *   <ConfirmDialog
 *     open={showDialog}
 *     title="Löschen"
 *     message="Möchten Sie das Preset wirklich löschen?"
 *     onConfirm={() => { deletePreset(); setShowDialog(false); }}
 *     onCancel={() => setShowDialog(false)}
 *   />
 */

interface ConfirmDialogProps {
  /** Whether the dialog is visible */
  open: boolean;
  /** Dialog heading */
  title?: string;
  /** Body text shown to the user */
  message: string;
  /** Label for the confirm button (default: t("common.confirm")) */
  confirmLabel?: string;
  /** Label for the cancel button (default: t("common.cancel")) */
  cancelLabel?: string;
  /** Called when the user confirms */
  onConfirm: () => void;
  /** Hide Cancel for informational dialogs that only need an OK action. */
  showCancelButton?: boolean;
  /** Stage 5 (optional, additive): red confirm button for destructive actions */
  destructive?: boolean;
  /** Called when the user cancels (Escape, overlay click, cancel button) */
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
  showCancelButton = true,
  destructive = false,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t("common.confirm");
  const resolvedConfirmLabel = confirmLabel ?? t("common.confirm");
  const resolvedCancelLabel = cancelLabel ?? t("common.cancel");
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  // Focus the cancel button when dialog opens (safe default)
  useEffect(() => {
    if (open) {
      (showCancelButton ? cancelRef : confirmRef).current?.focus();
    }
  }, [open, showCancelButton]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onCancel]);

  return (
    <Modal
      open={open}
      onClose={onCancel}
      size="sm"
      role="alertdialog"
      labelledBy="confirm-dialog-title"
      describedBy="confirm-dialog-message"
      closeOnEscape={false}
      overlayData={{ "data-testid": "confirm-dialog-overlay" }}
    >
      <div className="dlg-head">
        <h2 id="confirm-dialog-title" className="dlg-title">
          {resolvedTitle}
        </h2>
      </div>
      <div className="dlg-body">
        <p id="confirm-dialog-message" className="dlg-text">
          {message}
        </p>
      </div>
      <div className="dlg-actions">
        {showCancelButton && (
          <button
            ref={cancelRef}
            className="btn btn-secondary"
            onClick={onCancel}
            data-testid="confirm-dialog-cancel"
          >
            {resolvedCancelLabel}
          </button>
        )}
        <button
          ref={confirmRef}
          className={`btn ${destructive ? "btn-danger" : "btn-primary"}`}
          onClick={onConfirm}
          data-testid="confirm-dialog-confirm"
        >
          {resolvedConfirmLabel}
        </button>
      </div>
    </Modal>
  );
}
