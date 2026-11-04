import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { ToastProvider } from "./contexts/ToastContext";
import { DeviceEventProvider } from "./contexts/DeviceEventContext";
import { MotionConfig } from "framer-motion";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Navigation from "./components/Navigation";
import EmptyState from "./components/EmptyState";
import { Icon } from "./components/Icon";
import Devices from "./pages/Devices";
import MultiRoom from "./pages/MultiRoom";
import Settings from "./pages/Settings";
import About from "./pages/About";
import Licenses from "./pages/Licenses";
import Diagnostics from "./pages/Diagnostics";
import SetupWizard from "./pages/SetupWizard";
import NotFound from "./pages/NotFound";
import { Device } from "./api/devices";
import { useDevices } from "./hooks/useDevices";
import "./ui-base.css";
import "./app-shell.css";

/**
 * AppRouter - Handles routing logic with device-based guards
 */
interface AppRouterProps {
  devices: Device[];
  isLoading: boolean;
  error: Error | null;
  onRetry: () => void;
}

function AppRouter({ devices: initialDevices, isLoading, error, onRetry }: AppRouterProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const devices = initialDevices;

  // The device was deleted in the backend: drop it from the cached list at once. (It used to be hidden by a local
  // "removed" set that was never cleared, so a device found again by a later scan stayed invisible until a reload.)
  const handleRemoveDevice = (deviceId: string) => {
    queryClient.setQueryData<Device[]>(["devices"], (old) =>
      (old ?? []).filter((d) => d.device_id !== deviceId)
    );
  };

  // REFACT-137: Show hint after 3s loading, retry hint after 8s
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  useEffect(() => {
    if (!isLoading) {
      setLoadingSeconds(0);
      return;
    }
    const timer = setInterval(() => {
      setLoadingSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [isLoading]);

  if (isLoading) {
    const loadingMessage =
      loadingSeconds < 4
        ? t("common.openCloudTouchLoading")
        : loadingSeconds < 10
          ? t("common.connectingToServer")
          : t("common.loadingTimeout");
    return (
      <div className="app">
        <main id="main-content" tabIndex={-1} className="app-main app-main--center">
          <div
            className="app-state"
            role="status"
            aria-live="polite"
            aria-label={t("common.loading")}
          >
            <div className="spinner" aria-hidden="true" />
            <p className="app-state-message">{loadingMessage}</p>
            {loadingSeconds >= 3 && loadingSeconds < 10 && (
              <p className="app-state-hint">{t("common.loadingHint")}</p>
            )}
            {loadingSeconds >= 8 && (
              <>
                <button className="btn btn-secondary" onClick={onRetry}>
                  {Icon.RefreshCw(18)} {t("common.retry")}
                </button>
                <p className="app-state-hint">{t("common.retryHint")}</p>
              </>
            )}
          </div>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <main id="main-content" tabIndex={-1} className="app-main app-main--center">
          <div className="app-state" role="alert">
            <div className="app-state-icon" aria-hidden="true">
              {Icon.Alert(32)}
            </div>
            <h1 className="app-state-title">{t("errors.devicesLoadTitle")}</h1>
            <p className="app-state-message">{t("errors.devicesLoadMessage")}</p>
            <button className="btn btn-primary" onClick={onRetry} aria-label={t("common.retry")}>
              {Icon.RefreshCw(18)} {t("common.retry")}
            </button>
          </div>
        </main>
      </div>
    );
  }
  return (
    <Routes>
      {/* Welcome Screen - shown when no devices, rendered WITHOUT NavBar/main */}
      <Route
        path="/welcome"
        element={
          devices.length === 0 ? (
            <div className="app">
              <main id="main-content" className="app-main" tabIndex={-1}>
                <EmptyState />
              </main>
            </div>
          ) : (
            <Navigate to="/" replace />
          )
        }
      />

      {/* All other routes - with NavBar and main wrapper */}
      <Route
        path="/*"
        element={
          <div className="app">
            <a className="skip-link" href="#main-content">
              {t("a11y.skipToContent")}
            </a>
            <header className="app-header" data-test="app-header">
              <Navigation />
            </header>
            <main id="main-content" tabIndex={-1} className="app-main">
              <Routes>
                {/* Setup Wizard — always available, manages its own loading/empty states */}
                <Route
                  path="/setup-wizard"
                  element={<SetupWizard devices={devices} isLoading={false} />}
                />

                {/* Main App Routes - require devices */}
                <Route
                  path="/*"
                  element={
                    devices.length > 0 ? (
                      <Routes>
                        <Route
                          path="/"
                          element={
                            <Devices devices={devices} onRemoveDevice={handleRemoveDevice} />
                          }
                        />
                        <Route path="/multiroom" element={<MultiRoom devices={devices} />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route path="/diagnostics" element={<Diagnostics />} />
                        <Route path="/about" element={<About />} />
                        <Route path="/licenses" element={<Licenses />} />
                        <Route path="*" element={<NotFound />} />
                      </Routes>
                    ) : (
                      <Navigate to="/welcome" replace />
                    )
                  }
                />
              </Routes>
            </main>
          </div>
        }
      />
    </Routes>
  );
}

function App() {
  const { data: devices = [], isLoading, error, refetch } = useDevices();

  const routerFutureFlags = {
    future: { v7_startTransition: true, v7_relativeSplatPath: true },
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const routerFutureFlagsAny = routerFutureFlags as any;

  return (
    <ErrorBoundary>
      {/* reducedMotion="user": framer-motion animations respect the OS "reduce motion" setting */}
      <MotionConfig reducedMotion="user">
        <BrowserRouter {...routerFutureFlagsAny}>
          <ToastProvider>
            <DeviceEventProvider>
              <AppRouter
                devices={devices}
                isLoading={isLoading}
                error={error}
                onRetry={() => refetch()}
              />
            </DeviceEventProvider>
          </ToastProvider>
        </BrowserRouter>
      </MotionConfig>
    </ErrorBoundary>
  );
}

export default App;
