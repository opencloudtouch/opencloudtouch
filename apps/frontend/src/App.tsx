import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
  if (isLoading) {
    return (
      <div className="app">
        <div className="loading-container">
          <div className="spinner" />
          <p className="loading-message">OpenCloudTouch wird geladen...</p>
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
          <p className="error-message">{error.message}</p>
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

  return (
    <ErrorBoundary>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
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
