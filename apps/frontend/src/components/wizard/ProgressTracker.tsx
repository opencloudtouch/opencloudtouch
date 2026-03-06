/**
 * Progress Tracker for Setup Wizard
 * Shows current step and completion status
 */
import "./ProgressTracker.css";

export interface WizardStep {
  id: number;
  label: string;
  /** Vollständige Beschreibung für Screen-Reader und Tooltip-Hover (REFACT-203) */
  description?: string;
  status: "pending" | "in-progress" | "completed" | "error";
}

interface ProgressTrackerProps {
  steps: WizardStep[];
  currentStep: number;
}

export default function ProgressTracker({ steps, currentStep }: ProgressTrackerProps) {
  return (
    <div className="progress-tracker">
      <div className="progress-steps">
        {steps.map((step, index) => (
          <div
            key={step.id}
            className={`progress-step ${step.status} ${step.id === currentStep ? "active" : ""}`}
          >
            <div className="step-indicator">
              <div
                className="step-circle"
                title={step.description ?? step.label}
                aria-label={
                  step.status === "completed"
                    ? `Schritt ${step.id}: ${step.label}${step.description ? ` — ${step.description}` : ""} – abgeschlossen`
                    : step.status === "error"
                      ? `Schritt ${step.id}: ${step.label}${step.description ? ` — ${step.description}` : ""} – Fehler`
                      : step.status === "in-progress"
                        ? `Schritt ${step.id}: ${step.label}${step.description ? ` — ${step.description}` : ""} – läuft`
                        : `Schritt ${step.id}: ${step.label}${step.description ? ` — ${step.description}` : ""} – ausstehend`
                }
              >
                {step.status === "completed" ? (
                  <span className="step-icon" aria-hidden="true">
                    ✓
                  </span>
                ) : step.status === "error" ? (
                  <span className="step-icon" aria-hidden="true">
                    ✗
                  </span>
                ) : (
                  <span className="step-number" aria-hidden="true">
                    {step.id}
                  </span>
                )}
              </div>
              {index < steps.length - 1 && <div className="step-connector" />}
            </div>
            <div className="step-label">{step.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
