import { createContext, use, useState, useCallback, ReactNode } from "react";
import Toast from "../components/Toast";

/**
 * Toast Context
 *
 * Provides global toast notification functionality.
 * Any component can trigger toast messages via useToast() hook.
 *
 * Usage:
 *   const { show } = useToast()
 *   show('Message', 'warning')
 *
 * Types: info, success, warning, error
 */

export type ToastType = "info" | "success" | "warning" | "error";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastOptions {
  duration?: number;
  /** Stays until the user closes it (or another toast replaces it). */
  persistent?: boolean;
  action?: ToastAction;
  /** Called when the user closes the toast with its close button (not on auto-hide). */
  onDismiss?: () => void;
}

export interface ToastData extends ToastOptions {
  message: string;
  type: ToastType;
  duration: number;
}

export interface ToastContextValue {
  show: (message: string, type?: ToastType, options?: number | ToastOptions) => void;
  hide: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toast, setToast] = useState<ToastData | null>(null);

  const show = useCallback(
    (message: string, type: ToastType = "info", options: number | ToastOptions = 5000) => {
      const opts = typeof options === "number" ? { duration: options } : options;
      setToast({ ...opts, message, type, duration: opts.duration ?? 5000 });
    },
    []
  );

  const hide = useCallback(() => {
    setToast(null);
  }, []);

  return (
    <ToastContext value={{ show, hide }}>
      {children}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          persistent={toast.persistent}
          action={toast.action}
          onDismiss={toast.onDismiss}
          onClose={hide}
        />
      )}
    </ToastContext>
  );
}

export function useToast(): ToastContextValue {
  const context = use(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
