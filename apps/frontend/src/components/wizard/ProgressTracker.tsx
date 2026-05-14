/**
 * Progress Tracker for Setup Wizard
 * Shows current step and completion status
 */
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
                    ? t("setup.stepAriaCompleted", {
                        id: step.id,
                        label: step.label,
                        description: step.description || "",
                      })
                    : step.status === "error"
                      ? t("setup.stepAriaError", {
                          id: step.id,
                          label: step.label,
                          description: step.description || "",
                        })
                      : step.status === "in-progress"
                        ? t("setup.stepAriaInProgress", {
                            id: step.id,
                            label: step.label,
                            description: step.description || "",
                          })
                        : t("setup.stepAriaPending", {
                            id: step.id,
                            label: step.label,
                            description: step.description || "",
                          })
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
