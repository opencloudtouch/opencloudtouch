/**
 * Progress Tracker for Setup Wizard
 * Shows current step and completion status
 */
import "./ProgressTracker.css";

export interface WizardStep {
  id: number;
  label: string;
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
              <div className="step-circle">
                {step.status === "completed" ? (
                  <span className="step-icon">✓</span>
                ) : step.status === "error" ? (
                  <span className="step-icon">✗</span>
                ) : (
                  <span className="step-number">{step.id}</span>
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
