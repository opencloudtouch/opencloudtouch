/** WizardStep: props and behaviour unchanged, markup restyled. File: components/wizard/WizardStep.tsx */
import { ReactNode, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Icon } from "./Icon";
import "./wizard-base.css"; // replaces WizardStep.css

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
  const titleRef = useRef<HTMLHeadingElement>(null);

  // Each wizard step is a new "page": move focus to its title so screen reader and keyboard users start there.
  useEffect(() => {
    titleRef.current?.focus({ preventScroll: true });
  }, []);
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
      <div className="wizard-step-header">
        <div className="wizard-step-number">{t("setup.stepLabel", { step: stepNumber })}</div>
        <h2 ref={titleRef} tabIndex={-1} className="wizard-step-title">
          {title}
        </h2>
        {description && <p className="wizard-step-description">{description}</p>}
      </div>

      {warning && (
        <div className="wizard-warning" role="alert">
          <span className="wizard-warning-icon" aria-hidden="true">
            {Icon.Alert()}
          </span>
          <span className="wizard-warning-text">{warning}</span>
        </div>
      )}

      <div className="wizard-step-content">{children}</div>

      <div className="wizard-step-actions">
        {onPrevious && (
          <button
            className="btn btn-secondary wizard-btn-previous"
            onClick={onPrevious}
            disabled={isPreviousDisabled || isLoading}
            aria-label={labelPrev}
          >
            {Icon.ArrowLeft()} {labelPrev}
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
              {Icon.Info()} <span>{nextDisabledReason}</span>
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
                  {labelNext} {Icon.ArrowRight()}
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
