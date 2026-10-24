/**
 * RestoreExecution - Step-by-step restore progress view
 * Props, hooks, effect, handlers, request mapping and t() keys unchanged. JSX/classes/icons only.
 * New keys (English defaults inline): restore.execution.running_hint, restore.execution.error_hint,
 * restore.execution.failed_title.
 */
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./RestoreSteps.css";
import { translateStepLabel, translateStepMessage } from "../../utils/restoreMessages";
import { useExecuteRestore } from "../../hooks/useRestore";
import type {
  RestoreWizardRequest,
  RestoreStepResponse,
  BackupSetResponse,
} from "../../api/restore";
import { useEffect, type ReactElement } from "react";
import { Icon } from "./Icon";

interface RestoreExecutionProps {
  readonly stepNumber: number;
  readonly deviceIp: string;
  readonly deviceId: string;
  readonly restoreType: "backup" | "clean";
  readonly backupSet: BackupSetResponse | null;
  readonly onComplete: (steps: RestoreStepResponse[]) => void;
  readonly onPrevious: () => void;
}

// English fallback labels; the UI translates them via restore.step_labels.<name>
const STEP_LABELS: Record<string, string> = {
  pre_snapshot: "Pre-Restore Snapshot",
  config: "Config Files",
  presets: "Presets",
  hosts: "/etc/hosts",
  ntp: "/etc/ntpservers.txt",
  remote_services: "SSH Persistence",
  reboot: "Reboot",
};

const STATUS_ICONS: Record<string, ReactElement> = {
  pending: Icon.Clock(20),
  in_progress: Icon.Loader(20),
  completed: Icon.CircleCheck(20),
  skipped: Icon.SkipForward(20),
  failed: Icon.CircleX(20),
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
      onPrevious={isPending ? undefined : onPrevious}
      onNext={data?.success ? () => onComplete(data.steps) : undefined}
      isNextDisabled={!data?.success}
      isLoading={isPending}
      nextLabel={t("restore.execution.continue", "Continue")}
    >
      {isPending && (
        <div className="restore-execution__progress wz-status" role="status" aria-live="polite">
          <div className="restore-execution__progress-head">
            <span className="wz-spinner" aria-hidden="true" />
            <p>{t("restore.execution.running", "Restore in progress...")}</p>
          </div>
          <p className="restore-execution__hint">
            {t(
              "restore.execution.running_hint",
              "This can take several minutes (usually 8 to 9). Keep this page open and do not disconnect the device."
            )}
          </p>
          <span className="wz-progress wz-progress--indeterminate" aria-hidden="true">
            <span className="wz-progress-bar" />
          </span>
        </div>
      )}

      {error && (
        <div className="restore-execution__error wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX()}
          </span>
          <div className="wz-status-body">
            <p>
              {t("restore.execution.error", "Restore failed: {{message}}", {
                message: (error as Error).message,
              })}
            </p>
            <p className="restore-execution__hint">
              {t("restore.execution.error_hint", "Go back and try again.")}
            </p>
          </div>
        </div>
      )}

      {data && (
        <div className="restore-execution__steps">
          {data.steps.map((step) => (
            <div
              key={step.name}
              className={`restore-execution__step restore-execution__step--${step.status}`}
            >
              <span
                className="restore-execution__icon"
                role="img"
                aria-label={t(`restore.status.${step.status}`, { defaultValue: step.status })}
              >
                {STATUS_ICONS[step.status] ?? Icon.Info(20)}
              </span>
              <span className="restore-execution__label">
                {translateStepLabel(t, step.name, STEP_LABELS[step.name])}
              </span>
              <span className="restore-execution__message">{translateStepMessage(t, step)}</span>
              {step.error && step.error !== step.message && (
                <span className="restore-execution__error-detail">{step.error}</span>
              )}
              {step.duration_seconds > 0 && (
                <span className="restore-execution__duration">
                  {step.duration_seconds.toFixed(1)}s
                </span>
              )}
            </div>
          ))}
          {data.success ? (
            <div className="restore-execution__success wz-status wz-status--success" role="status">
              <span className="wz-icon" aria-hidden="true">
                {Icon.CircleCheck(24)}
              </span>
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
          ) : (
            <div className="restore-execution__failed wz-status wz-status--error" role="alert">
              <span className="wz-icon" aria-hidden="true">
                {Icon.CircleX(24)}
              </span>
              <div className="wz-status-body">
                <strong className="wz-status-title">
                  {t("restore.execution.failed_title", "Restore incomplete")}
                </strong>
                <p>{t("restore.execution.error_hint", "Go back and try again.")}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </WizardStep>
  );
}
