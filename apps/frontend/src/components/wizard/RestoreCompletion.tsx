/**
 * RestoreCompletion - Summary of restored items
 * Props, filters, handlers and t() keys unchanged. JSX/classes/icons only.
 */
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./RestoreSteps.css";
import { translateStepMessage } from "../../utils/restoreMessages";
import type { RestoreStepResponse } from "../../api/restore";
import { Icon } from "./Icon";

interface RestoreCompletionProps {
  stepNumber: number;
  restoreType: "backup" | "clean";
  steps: RestoreStepResponse[];
  onFinish: () => void;
}

export default function RestoreCompletion({
  stepNumber,
  restoreType,
  steps,
  onFinish,
}: Readonly<RestoreCompletionProps>) {
  const { t } = useTranslation();

  const succeeded = steps.filter((s) => s.status === "completed");
  const skipped = steps.filter((s) => s.status === "skipped");
  const failed = steps.filter((s) => s.status === "failed");

  return (
    <WizardStep
      stepNumber={stepNumber}
      title={t("restore.completion.title", "Restore Complete")}
      description={t("restore.completion.description", "Device has been restored successfully.")}
      onNext={onFinish}
      nextLabel={t("restore.completion.done", "Done")}
    >
      <div className="restore-completion">
        <h3>
          {restoreType === "clean"
            ? t("restore.completion.clean_summary", "Clean Restore Summary")
            : t("restore.completion.backup_summary", "Backup Restore Summary")}
        </h3>

        {succeeded.length > 0 && (
          <div className="restore-completion__section restore-completion__section--restored">
            <h4>
              <span className="wz-icon" aria-hidden="true">
                {Icon.CircleCheck(20)}
              </span>
              {t("restore.completion.restored", "Restored")}
            </h4>
            <ul>
              {succeeded.map((s) => (
                <li key={s.name}>
                  <span className="wz-icon" aria-hidden="true">
                    {Icon.Check(18)}
                  </span>
                  <span>{translateStepMessage(t, s)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {skipped.length > 0 && (
          <div className="restore-completion__section restore-completion__section--skipped">
            <h4>
              <span className="wz-icon" aria-hidden="true">
                {Icon.SkipForward(20)}
              </span>
              {t("restore.completion.skipped", "Skipped")}
            </h4>
            <ul>
              {skipped.map((s) => (
                <li key={s.name}>
                  <span className="wz-icon" aria-hidden="true">
                    {Icon.Minus(18)}
                  </span>
                  <span>{translateStepMessage(t, s)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {failed.length > 0 && (
          <div className="restore-completion__section restore-completion__section--failed">
            <h4>
              <span className="wz-icon" aria-hidden="true">
                {Icon.CircleX(20)}
              </span>
              {t("restore.completion.failed", "Failed")}
            </h4>
            <ul>
              {failed.map((s) => (
                <li key={s.name}>
                  <span className="wz-icon" aria-hidden="true">
                    {Icon.X(18)}
                  </span>
                  <span>
                    {translateStepMessage(t, s)}
                    {s.error && s.error !== s.message && (
                      <span className="restore-completion__error"> — {s.error}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="restore-completion__note wz-status">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Info(20)}
          </span>
          <span>
            {t(
              "restore.completion.note",
              "The device is now in its original state. You can safely disconnect it."
            )}
          </span>
        </p>
      </div>
    </WizardStep>
  );
}
