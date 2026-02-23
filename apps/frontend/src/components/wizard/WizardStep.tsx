/**
 * WizardStep - Base component for wizard steps
 */
import { ReactNode } from "react";
import { motion } from "framer-motion";
import "./WizardStep.css";

export interface WizardStepProps {
  stepNumber: number;
  title: string;
  description?: string;
  children: ReactNode;
  warning?: string;
  onNext?: () => void;
  onPrevious?: () => void;
  onSkip?: () => void;
  nextLabel?: string;
  previousLabel?: string;
  skipLabel?: string;
  isNextDisabled?: boolean;
  isPreviousDisabled?: boolean;
  isLoading?: boolean;
}

export default function WizardStep({
  stepNumber,
  title,
  description,
  children,
  warning,
  onNext,
  onPrevious,
  onSkip,
  nextLabel = "Weiter",
  previousLabel = "Zurück",
  skipLabel = "Überspringen",
  isNextDisabled = false,
  isPreviousDisabled = false,
  isLoading = false,
}: WizardStepProps) {
  return (
    <motion.div
      className="wizard-step"
      initial={{ opacity: 0, x: 50 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -50 }}
      transition={{ duration: 0.3 }}
    >
      {/* Step Header */}
      <div className="wizard-step-header">
        <div className="wizard-step-number">Schritt {stepNumber}</div>
        <h2 className="wizard-step-title">{title}</h2>
        {description && <p className="wizard-step-description">{description}</p>}
      </div>

      {/* Warning Banner */}
      {warning && (
        <div className="wizard-warning" role="alert">
          <span className="wizard-warning-icon">⚠️</span>
          <span className="wizard-warning-text">{warning}</span>
        </div>
      )}

      {/* Step Content */}
      <div className="wizard-step-content">{children}</div>

      {/* Step Actions */}
      <div className="wizard-step-actions">
        {onPrevious && (
          <button
            className="btn btn-secondary wizard-btn-previous"
            onClick={onPrevious}
            disabled={isPreviousDisabled || isLoading}
            aria-label={previousLabel}
          >
            ← {previousLabel}
          </button>
        )}

        <div className="wizard-actions-right">
          {onSkip && (
            <button
              className="btn btn-ghost wizard-btn-skip"
              onClick={onSkip}
              disabled={isLoading}
              aria-label={skipLabel}
            >
              {skipLabel}
            </button>
          )}

          {onNext && (
            <button
              className="btn btn-primary wizard-btn-next"
              onClick={onNext}
              disabled={isNextDisabled || isLoading}
              aria-label={nextLabel}
            >
              {isLoading ? (
                <>
                  <span className="spinner-small" />
                  Verarbeite...
                </>
              ) : (
                <>{nextLabel} →</>
              )}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
