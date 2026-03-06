import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { ToastProvider } from "./contexts/ToastContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Navigation from "./components/Navigation";
import EmptyState from "./components/EmptyState";
import RadioPresets from "./pages/RadioPresets";
import LocalControl from "./pages/LocalControl";
import MultiRoom from "./pages/MultiRoom";
import Firmware from "./pages/Firmware";
import Settings from "./pages/Settings";
import Licenses from "./pages/Licenses";
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

function AppRouter({ devices, isLoading, error, onRetry }: AppRouterProps) {
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
        ? "OpenCloudTouch wird geladen..."
        : loadingSeconds < 10
          ? "Verbindung zum Server wird hergestellt..."
          : "Dies dauert länger als erwartet. Bitte warten oder Seite neu laden.";
    return (
      <div className="app">
        <div
          className="loading-container"
          role="status"
          aria-live="polite"
          aria-label="Ladevorgang"
        >
          <div className="spinner" aria-hidden="true" />
          <p className="loading-message">{loadingMessage}</p>
          {loadingSeconds >= 3 && loadingSeconds < 10 && (
            <p className="loading-hint">Dies kann einige Sekunden dauern...</p>
          )}
          {loadingSeconds >= 8 && (
            <>
              <button className="btn btn-secondary loading-retry" onClick={onRetry}>
                🔄 Erneut versuchen
              </button>
              <p className="loading-hint">
                Falls das Problem anhält: Stellen Sie sicher, dass Ihr OpenCloudTouch-Server
                erreichbar ist und aktualisieren Sie die Seite.
              </p>
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
          <h2 className="error-title">Fehler beim Laden der Geräte</h2>
          <p className="error-message">
            Geräte konnten nicht geladen werden. Bitte prüfen Sie die Verbindung und versuchen Sie
            es erneut.
          </p>
          <button className="btn btn-primary" onClick={onRetry} aria-label="Erneut versuchen">
            Erneut versuchen
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <Routes>
        {/* Setup Wizard — always available, manages its own loading/empty states */}
        <Route path="/setup-wizard" element={<SetupWizard devices={devices} isLoading={false} />} />

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
              <>
                <header className="app-header" data-test="app-header">
                  <Navigation />
                </header>
                <main className="app-main">
                  <Routes>
                    <Route path="/" element={<RadioPresets devices={devices} />} />
                    <Route path="/local" element={<LocalControl devices={devices} />} />
                    <Route path="/multiroom" element={<MultiRoom devices={devices} />} />
                    <Route path="/firmware" element={<Firmware devices={devices} />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/licenses" element={<Licenses />} />
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </main>
              </>
            ) : (
              <Navigate to="/welcome" replace />
            )
          }
        />
      </Routes>
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
          <AppRouter
            devices={devices}
            isLoading={isLoading}
            error={error}
            onRetry={() => refetch()}
          />
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
