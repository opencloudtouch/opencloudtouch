/** Progress Tracker: logic unchanged, markup restyled. File: components/wizard/ProgressTracker.tsx
 *  New i18n key: setup.stepAriaSkipped = "Schritt {{id}}: {{label}} — {{description}} – übersprungen"
 *  Additive: status "skipped" (clean restore skips the backup scan). Dash icon, dashed green ring, green connector after it. */
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./wizard-base.css"; // replaces ProgressTracker.css

export interface WizardStep {
  id: number;
  label: string;
  description?: string;
  status: "pending" | "in-progress" | "completed" | "error" | "skipped";
}

interface ProgressTrackerProps {
  steps: WizardStep[];
  currentStep: number;
}

export default function ProgressTracker({ steps, currentStep }: ProgressTrackerProps) {
  const { t } = useTranslation();
  const current = steps.find((s) => s.id === currentStep);

  const ariaLabelFor = (step: WizardStep) => {
    const key =
      step.status === "completed"
        ? "setup.stepAriaCompleted"
        : step.status === "skipped"
          ? "setup.stepAriaSkipped"
          : step.status === "error"
            ? "setup.stepAriaError"
            : step.status === "in-progress"
              ? "setup.stepAriaInProgress"
              : "setup.stepAriaPending";
    return t(key, { id: step.id, label: step.label, description: step.description || "" });
  };

  return (
    <div className="progress-tracker">
      <div className="progress-tracker-compact" aria-hidden="true">
        {t("setup.trackerCompact", {
          current: currentStep,
          total: steps.length,
          label: current?.label ?? "",
        })}
      </div>
      <div className="progress-steps">
        {steps.map((step, index) => (
          <div
            key={step.id}
            className={`progress-step ${step.status} ${step.id === currentStep ? "active" : ""}`}
            aria-current={step.id === currentStep ? "step" : undefined}
          >
            <div className="step-indicator">
              {index > 0 && <div className="step-connector" />}
              <div
                className="step-circle"
                role="img"
                title={step.description ?? step.label}
                aria-label={ariaLabelFor(step)}
              >
                {step.status === "completed" ? (
                  <span className="step-icon" aria-hidden="true">
                    {Icon.Check()}
                  </span>
                ) : step.status === "skipped" ? (
                  <span className="step-icon" aria-hidden="true">
                    {Icon.Minus()}
                  </span>
                ) : step.status === "error" ? (
                  <span className="step-icon" aria-hidden="true">
                    {Icon.X()}
                  </span>
                ) : (
                  <span className="step-number" aria-hidden="true">
                    {step.id}
                  </span>
                )}
              </div>
            </div>
            <div className="step-label">{step.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
