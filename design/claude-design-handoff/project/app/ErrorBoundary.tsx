import { Component, ReactNode } from "react";
import { i18next } from "../i18n";
import { Icon } from "./Icon";
import "./ErrorBoundary.css";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error Boundary Component
 * Catches JavaScript errors anywhere in the child component tree
 * Displays fallback UI instead of crashing the whole app
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console in development
    console.error("ErrorBoundary caught an error:", error, errorInfo);

    // TODO: In production, log to error reporting service (e.g., Sentry)
    // logErrorToService(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      // Custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleReset);
      }

      // Default fallback UI (replaces the whole app, so it brings its own <main> and h1)
      return (
        <main className="eb" id="main-content">
          <div className="eb-card" role="alert">
            <div className="eb-icon" aria-hidden="true">
              {Icon.Alert(32)}
            </div>
            <h1 className="eb-title">{i18next.t("errors.errorBoundaryTitle")}</h1>
            <p className="eb-message">{i18next.t("errors.errorBoundaryMessage")}</p>

            <details className="eb-details">
              <summary>
                <span>{i18next.t("errors.errorDetails")}</span>
                <span className="eb-chevron" aria-hidden="true">
                  {Icon.ChevronDown(18)}
                </span>
              </summary>
              <pre tabIndex={0}>{this.state.error.toString()}</pre>
              {this.state.error.stack && (
                <pre className="eb-stack" tabIndex={0}>
                  {this.state.error.stack}
                </pre>
              )}
            </details>

            <div className="eb-actions">
              <button
                className="btn btn-primary"
                onClick={() => window.location.reload()}
                aria-label={i18next.t("common.reloadPage")}
              >
                {Icon.RefreshCw(18)} {i18next.t("common.reloadPage")}
              </button>
              <button
                className="btn btn-secondary"
                onClick={this.handleReset}
                aria-label={i18next.t("common.retry")}
              >
                {Icon.Rotate(18)} {i18next.t("common.retry")}
              </button>
            </div>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
