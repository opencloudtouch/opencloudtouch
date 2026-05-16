/**
 * RestoreExecution - Step-by-step restore progress view
 */
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import { useExecuteRestore } from "../../hooks/useRestore";
import type {
  RestoreWizardRequest,
  RestoreStepResponse,
  BackupSetResponse,
} from "../../api/restore";
import { useEffect } from "react";

interface RestoreExecutionProps {
  stepNumber: number;
  deviceIp: string;
  deviceId: string;
  restoreType: "backup" | "clean";
  backupSet: BackupSetResponse | null;
  onComplete: (steps: RestoreStepResponse[]) => void;
  onPrevious: () => void;
}

const STEP_LABELS: Record<string, string> = {
  pre_snapshot: "Pre-Restore Snapshot",
  config: "Config Files",
  presets: "Presets",
  hosts: "/etc/hosts",
  remote_services: "SSH Persistence",
  reboot: "Reboot",
};

const STATUS_ICONS: Record<string, string> = {
  pending: "⏳",
  in_progress: "🔄",
  completed: "✅",
  skipped: "⏭️",
  failed: "❌",
};

export default function RestoreExecution({
  stepNumber,
  deviceIp,
  deviceId,
  restoreType,
  backupSet,
  onComplete,
  onPrevious,
}: RestoreExecutionProps) {
  const { t } = useTranslation();
  const { mutate: restore, data, isPending, error } = useExecuteRestore();

  useEffect(() => {
    const request: RestoreWizardRequest = {
      device_ip: deviceIp,
      device_id: deviceId,
      restore_type: restoreType,
      backup_set: backupSet
        ? {
            device_id: backupSet.device_id,
            backup_date: backupSet.backup_date,
            files: backupSet.files.map((f) => ({
              file_path: f.file_path,
              volume_type: f.volume_type,
            })),
          }
        : null,
      skip_snapshot: false,
    };
    restore(request);
  }, [deviceIp, deviceId, restoreType, backupSet, restore]);

  return (
    <WizardStep
      stepNumber={stepNumber}
      title={t("restore.execution.title", "Restoring Device")}
      description={t("restore.execution.description", "Undoing all OCT modifications...")}
      onPrevious={!isPending ? onPrevious : undefined}
      onNext={data?.success ? () => onComplete(data.steps) : undefined}
      isNextDisabled={!data?.success}
      isLoading={isPending}
      nextLabel={t("restore.execution.continue", "Continue")}
    >
      {isPending && (
        <div className="restore-execution__progress">
          <p>{t("restore.execution.running", "Restore in progress...")}</p>
        </div>
      )}

      {error && (
        <div className="restore-execution__error">
          <p>
            {t("restore.execution.error", "Restore failed: {{message}}", {
              message: (error as Error).message,
            })}
          </p>
        </div>
      )}

      {data && (
        <div className="restore-execution__steps">
          {data.steps.map((step) => (
            <div
              key={step.name}
              className={`restore-execution__step restore-execution__step--${step.status}`}
            >
              <span className="restore-execution__icon">{STATUS_ICONS[step.status] ?? "❓"}</span>
              <span className="restore-execution__label">
                {STEP_LABELS[step.name] ?? step.name}
              </span>
              <span className="restore-execution__message">{step.message}</span>
              {step.error && <span className="restore-execution__error-detail">{step.error}</span>}
              {step.duration_seconds > 0 && (
                <span className="restore-execution__duration">
                  {step.duration_seconds.toFixed(1)}s
                </span>
              )}
            </div>
          ))}
          {data.success && (
            <div className="restore-execution__success">
              <p>
                {t(
                  "restore.execution.success",
                  "All steps completed successfully! Total: {{time}}s",
                  {
                    time: data.total_duration_seconds.toFixed(1),
                  }
                )}
              </p>
            </div>
          )}
        </div>
      )}
    </WizardStep>
  );
}
