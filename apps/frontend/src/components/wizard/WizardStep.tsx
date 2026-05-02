/**
 * WizardStep - Base component for wizard steps
 */
import { ReactNode } from "react";
import { useTranslation } from "react-i18next";
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
  /** Explanatory text for why 'Next' is disabled. Shown as tooltip + hint. */
  nextDisabledReason?: string;
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
  nextLabel,
  previousLabel,
  skipLabel,
  isNextDisabled = false,
  isPreviousDisabled = false,
  isLoading = false,
  nextDisabledReason,
}: WizardStepProps) {
  const { t } = useTranslation();

  const labelNext = nextLabel ?? t("setup.next");
  const labelPrev = previousLabel ?? t("setup.back");
  const labelSkip = skipLabel ?? t("setup.skip");

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
        <div className="wizard-step-number">{t("setup.stepLabel", { step: stepNumber })}</div>
        <h2 className="wizard-step-title">{title}</h2>
        {description && <p className="wizard-step-description">{description}</p>}
      </div>

      {/* Warning Banner */}
      {warning && (
        <div className="wizard-warning" role="alert">
          <span className="wizard-warning-icon" aria-hidden="true">
            {"\u26A0\uFE0F"}
          </span>
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
            aria-label={labelPrev}
          >
            {"\u2190"} {labelPrev}
          </button>
        )}

        <div className="wizard-actions-right">
          {onSkip && (
            <button
              className="btn btn-ghost wizard-btn-skip"
              onClick={onSkip}
              disabled={isLoading}
              aria-label={labelSkip}
            >
              {labelSkip}
            </button>
          )}

          {isNextDisabled && nextDisabledReason && !isLoading && (
            <span className="wizard-next-hint" role="status" aria-live="polite">
              {"\u2139\uFE0F"} {nextDisabledReason}
            </span>
          )}

          {onNext && (
            <button
              className="btn btn-primary wizard-btn-next"
              onClick={onNext}
              disabled={isNextDisabled || isLoading}
              aria-label={labelNext}
              title={isNextDisabled && nextDisabledReason ? nextDisabledReason : undefined}
            >
              {isLoading ? (
                <>
                  <span className="spinner-small" />
                  {t("common.loading")}
                </>
              ) : (
                <>
                  {labelNext} {"\u2192"}
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
