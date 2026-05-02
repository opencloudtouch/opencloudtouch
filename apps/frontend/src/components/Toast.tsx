import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ToastType } from "../contexts/ToastContext";
import "./Toast.css";

/**
 * Toast Notification Component
 *
 * Displays temporary notifications in the top-right corner.
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

  const icons: Record<ToastType, React.ReactElement> = {
    success: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    error: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    warning: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    info: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  };

  return (
    <div
      className={`toast toast-${type} ${isVisible ? "toast-visible" : "toast-hidden"}`}
      data-test="toast-notification"
    >
      <div className="toast-icon">{icons[type]}</div>
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
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path
            d="M6 6l8 8M14 6l-8 8"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
