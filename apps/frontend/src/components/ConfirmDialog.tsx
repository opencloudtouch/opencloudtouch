import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import "./ConfirmDialog.css";

/**
 * ConfirmDialog — accessible modal replacement for window.confirm().
 *
 * REFACT-107: Native browser dialogs block the main thread and cannot
 * be styled. This component renders an ARIA-compliant dialog instead.
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
  /** Label for the confirm button (default: "Bestätigen") */
  confirmLabel?: string;
  /** Label for the cancel button (default: "Abbrechen") */
  cancelLabel?: string;
  /** Called when the user confirms */
  onConfirm: () => void;
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
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t("common.confirm");
  const resolvedConfirmLabel = confirmLabel ?? t("common.confirm");
  const resolvedCancelLabel = cancelLabel ?? t("common.cancel");
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Focus the cancel button when dialog opens (safe default)
  useEffect(() => {
    if (open) {
      cancelRef.current?.focus();
    }
  }, [open]);

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

  if (!open) return null;

  return (
    <div
      className="confirm-dialog-overlay"
      onClick={onCancel}
      onKeyDown={(e) => {
        if (e.key === "Escape") onCancel();
      }}
      role="presentation"
      data-testid="confirm-dialog-overlay"
    >
      <div
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="confirm-dialog-title">
          {resolvedTitle}
        </h2>
        <p id="confirm-dialog-message" className="confirm-dialog-message">
          {message}
        </p>
        <div className="confirm-dialog-actions">
          <button
            ref={cancelRef}
            className="confirm-dialog-btn confirm-dialog-btn--cancel"
            onClick={onCancel}
            data-testid="confirm-dialog-cancel"
          >
            {resolvedCancelLabel}
          </button>
          <button
            className="confirm-dialog-btn confirm-dialog-btn--confirm"
            onClick={onConfirm}
            data-testid="confirm-dialog-confirm"
          >
            {resolvedConfirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
