import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ToastProvider } from "./contexts/ToastContext";
import { DeviceEventProvider } from "./contexts/DeviceEventContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Navigation from "./components/Navigation";
import EmptyState from "./components/EmptyState";
import RadioPresets from "./pages/RadioPresets";
import LocalControl from "./pages/LocalControl";
import MultiRoom from "./pages/MultiRoom";
import Firmware from "./pages/Firmware";
import Settings from "./pages/Settings";
import About from "./pages/About";
import Licenses from "./pages/Licenses";
import Diagnostics from "./pages/Diagnostics";
import SetupWizard from "./pages/SetupWizard";
import NotFound from "./pages/NotFound";
import { Device } from "./api/devices";
import { useDevices } from "./hooks/useDevices";
import "./App.css";

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
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());

  // Derive visible devices: parent data minus locally removed ones
  const devices = initialDevices.filter((d) => !removedIds.has(d.device_id));

  const handleRemoveDevice = (deviceId: string) => {
    setRemovedIds((prev) => new Set(prev).add(deviceId));
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
        <div
          className="loading-container"
          role="status"
          aria-live="polite"
          aria-label={t("common.loading")}
        >
          <div className="spinner" aria-hidden="true" />
          <p className="loading-message">{loadingMessage}</p>
          {loadingSeconds >= 3 && loadingSeconds < 10 && (
            <p className="loading-hint">{t("common.loadingHint")}</p>
          )}
          {loadingSeconds >= 8 && (
            <>
              <button className="btn btn-secondary loading-retry" onClick={onRetry}>
                🔄 {t("common.retry")}
              </button>
              <p className="loading-hint">{t("common.retryHint")}</p>
            </>
          )}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <div className="error-container">
          <div className="error-icon">⚠️</div>
          <h2 className="error-title">{t("errors.devicesLoadTitle")}</h2>
          <p className="error-message">{t("errors.devicesLoadMessage")}</p>
          <button className="btn btn-primary" onClick={onRetry} aria-label={t("common.retry")}>
            {t("common.retry")}
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="app">
      <header className="app-header" data-test="app-header">
        <Navigation />
      </header>
      <main className="app-main">
        <Routes>
          {/* Setup Wizard — always available, manages its own loading/empty states */}
          <Route
            path="/setup-wizard"
            element={<SetupWizard devices={devices} isLoading={false} />}
          />

          {/* Welcome Screen - shown when no devices */}
          <Route
            path="/welcome"
            element={devices.length === 0 ? <EmptyState /> : <Navigate to="/" replace />}
          />

          {/* Main App Routes - require devices */}
          <Route
            path="/*"
            element={
              devices.length > 0 ? (
                <Routes>
                  <Route
                    path="/"
                    element={<RadioPresets devices={devices} onRemoveDevice={handleRemoveDevice} />}
                  />
                  <Route path="/local" element={<LocalControl devices={devices} />} />
                  <Route path="/multiroom" element={<MultiRoom devices={devices} />} />
                  <Route path="/firmware" element={<Firmware devices={devices} />} />
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
    </ErrorBoundary>
  );
}

export default App;
