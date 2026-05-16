/**
 * RestoreCompletion - Summary of restored items
 */
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import type { RestoreStepResponse } from "../../api/restore";

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
        <h4>
          {restoreType === "clean"
            ? t("restore.completion.clean_summary", "Clean Restore Summary")
            : t("restore.completion.backup_summary", "Backup Restore Summary")}
        </h4>

        {succeeded.length > 0 && (
          <div className="restore-completion__section">
            <h5>✅ {t("restore.completion.restored", "Restored")}</h5>
            <ul>
              {succeeded.map((s) => (
                <li key={s.name}>{s.message}</li>
              ))}
            </ul>
          </div>
        )}

        {skipped.length > 0 && (
          <div className="restore-completion__section">
            <h5>⏭️ {t("restore.completion.skipped", "Skipped")}</h5>
            <ul>
              {skipped.map((s) => (
                <li key={s.name}>{s.message}</li>
              ))}
            </ul>
          </div>
        )}

        {failed.length > 0 && (
          <div className="restore-completion__section restore-completion__section--failed">
            <h5>❌ {t("restore.completion.failed", "Failed")}</h5>
            <ul>
              {failed.map((s) => (
                <li key={s.name}>
                  {s.message}
                  {s.error && <span className="restore-completion__error"> — {s.error}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="restore-completion__note">
          {t(
            "restore.completion.note",
            "The device is now in its original state. You can safely disconnect it."
          )}
        </p>
      </div>
    </WizardStep>
  );
}
