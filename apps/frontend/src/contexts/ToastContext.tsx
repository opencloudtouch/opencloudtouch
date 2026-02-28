import { createContext, useContext, useState, useCallback, ReactNode } from "react";
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

export interface ToastData {
  message: string;
  type: ToastType;
  duration: number;
}

export interface ToastContextValue {
  show: (message: string, type?: ToastType, duration?: number) => void;
  hide: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toast, setToast] = useState<ToastData | null>(null);

  const show = useCallback((message: string, type: ToastType = "info", duration: number = 5000) => {
    setToast({ message, type, duration });
  }, []);

  const hide = useCallback(() => {
    setToast(null);
  }, []);

  return (
    <ToastContext.Provider value={{ show, hide }}>
      {children}
      {toast && (
        <Toast message={toast.message} type={toast.type} duration={toast.duration} onClose={hide} />
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
