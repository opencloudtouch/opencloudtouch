import { useState, useEffect, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { ToastType } from "../contexts/ToastContext";
import { Icon } from "./Icon";
import "./Toast.css";

/**
 * Toast Notification Component
 *
 * Displays temporary notifications below the header (top-right; full width on phones).
 * Auto-hides after specified duration (default 5s).
 *
 * Types: success, error, info, warning
 */

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  onClose?: () => void;
}

export default function Toast({ message, type = "info", duration = 5000, onClose }: ToastProps) {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    let fadeTimer: ReturnType<typeof setTimeout>;
    const timer = setTimeout(() => {
      setIsVisible(false);
      if (onClose) {
        fadeTimer = setTimeout(onClose, 300); // Wait for fade-out animation
      }
    }, duration);

    return () => {
      clearTimeout(timer);
      clearTimeout(fadeTimer);
    };
  }, [duration, onClose]);

  if (!isVisible) return null;

  const icons: Record<ToastType, ReactElement> = {
    success: Icon.CircleCheck(22),
    error: Icon.CircleX(22),
    warning: Icon.Alert(22),
    info: Icon.Info(22),
  };

  return (
    <div
      className={`toast toast-${type} ${isVisible ? "toast-visible" : "toast-hidden"}`}
      data-test="toast-notification"
      // Announced to screen readers: errors/warnings interrupt (alert), success/info wait (status)
      role={type === "error" || type === "warning" ? "alert" : "status"}
    >
      <div className="toast-icon" aria-hidden="true">
        {icons[type]}
      </div>
      <div className="toast-content">
        <p className="toast-message" data-test="toast-message">
          {message}
        </p>
      </div>
      <button
        className="toast-close"
        onClick={() => {
          setIsVisible(false);
          if (onClose) setTimeout(onClose, 300);
        }}
        aria-label={t("common.close")}
        data-test="toast-close-button"
      >
        {Icon.X(18)}
      </button>
    </div>
  );
}
