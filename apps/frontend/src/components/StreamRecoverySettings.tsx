import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { i18next } from "../i18n";
import { useToast } from "../contexts/ToastContext";
import { useDevices } from "../hooks/useDevices";
import {
  useSaveStreamRecovery,
  useStreamRecoveryConfig,
  useStreamRecoveryEvents,
} from "../hooks/useStreamRecovery";
import type { StreamRecoveryEvent } from "../api/streamRecovery";
import { getApiErrorMessage, getFieldErrors } from "../utils/apiErrors";
import {
  MAX_ATTEMPTS,
  MAX_MINUTES,
  MIN_ATTEMPTS,
  MIN_MINUTES,
  isDirty,
  minutesToSeconds,
  parseAttempts,
  parseMinutes,
  secondsToMinutes,
  splitPlayTime,
  type StreamRecoveryForm,
} from "../utils/streamRecovery";
import { Skeleton } from "./LoadingSkeleton";
import "./StreamRecoverySettings.css";

const OUTCOMES = new Set(["resumed", "gave_up", "skipped_no_preset", "skipped_rate_limited"]);

function reasonFor(t: TFunction, code: string): string {
  return i18next.exists(`errors.api.${code}`)
    ? t(`errors.api.${code}`)
    : t("errors.api.unknownWithCode", { code });
}

function formatPlayTime(t: TFunction, seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "–";
  return t("settings.streamRecovery.playTime", splitPlayTime(seconds));
}

function EventRow({
  event,
  deviceName,
}: Readonly<{ event: StreamRecoveryEvent; deviceName: string }>) {
  const { t } = useTranslation();
  const outcome = OUTCOMES.has(event.outcome)
    ? t(`settings.streamRecovery.outcome.${event.outcome}`)
    : event.outcome;
  return (
    <tr>
      <td>{new Date(event.occurred_at).toLocaleString()}</td>
      <td>{deviceName}</td>
      <td>{event.station_name ?? "–"}</td>
      <td>{event.preset_number ?? "–"}</td>
      <td>
        {outcome}
        {event.outcome === "gave_up" && event.error_code ? (
          <> ({reasonFor(t, event.error_code)})</>
        ) : null}
      </td>
      <td>{formatPlayTime(t, event.play_seconds)}</td>
      <td>{event.attempts}</td>
    </tr>
  );
}

function ActivityLog({ expanded }: Readonly<{ expanded: boolean }>) {
  const { t } = useTranslation();
  const { data: devices } = useDevices();
  const {
    data: events,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useStreamRecoveryEvents(expanded);
  const [refreshed, setRefreshed] = useState(false);

  if (!expanded) return null;

  const nameOf = (id: string) => devices?.find((d) => d.device_id === id)?.name ?? id;
  const refresh = async () => {
    setRefreshed(false);
    await refetch();
    setRefreshed(true);
  };

  return (
    <div id="stream-recovery-activity">
      <button type="button" className="btn" onClick={refresh} disabled={isFetching}>
        {t("settings.streamRecovery.refresh")}
      </button>
      <p role="status" aria-live="polite" className="visually-hidden">
        {refreshed && !isFetching && !isError ? t("settings.streamRecovery.refreshed") : ""}
      </p>
      {isLoading && <Skeleton height="60px" />}
      {isError && (
        <div className="alert alert-error" role="alert">
          {t("settings.streamRecovery.activityError")}{" "}
          <button type="button" className="btn" onClick={() => refetch()}>
            {t("common.retry")}
          </button>
        </div>
      )}
      {events?.length === 0 && (
        <p className="stream-recovery-hint">{t("settings.streamRecovery.activityEmpty")}</p>
      )}
      {events && events.length > 0 && (
        <div className="stream-recovery-table-wrap">
          <table className="stream-recovery-table">
            <thead>
              <tr>
                <th>{t("settings.streamRecovery.col.time")}</th>
                <th>{t("settings.streamRecovery.col.device")}</th>
                <th>{t("settings.streamRecovery.col.station")}</th>
                <th>{t("settings.streamRecovery.col.preset")}</th>
                <th>{t("settings.streamRecovery.col.outcome")}</th>
                <th>{t("settings.streamRecovery.col.playTime")}</th>
                <th>{t("settings.streamRecovery.col.attempts")}</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <EventRow key={event.id} event={event} deviceName={nameOf(event.device_id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function StreamRecoverySettings() {
  const { t } = useTranslation();
  const { show } = useToast();
  const { data, isLoading, isError, refetch } = useStreamRecoveryConfig();
  const save = useSaveStreamRecovery();

  const [form, setForm] = useState<StreamRecoveryForm>({
    enabled: false,
    minutes: "",
    attempts: "",
  });
  const [baseline, setBaseline] = useState<StreamRecoveryForm | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [status, setStatus] = useState("");
  const [expanded, setExpanded] = useState(false);

  // The baseline follows the server state after load, save and refetch.
  useEffect(() => {
    if (!data) return;
    const next: StreamRecoveryForm = {
      enabled: data.enabled,
      minutes: String(secondsToMinutes(data.min_play_seconds)),
      attempts: String(data.max_attempts_per_hour),
    };
    setBaseline(next);
    setForm(next);
  }, [data]);

  if (isLoading || (!data && !isError)) {
    return (
      <section className="settings-section" id="stream-recovery" aria-busy="true">
        <Skeleton height="120px" />
      </section>
    );
  }

  if (isError || !baseline) {
    return (
      <section className="settings-section" id="stream-recovery">
        <h2 className="section-title">{t("settings.streamRecovery.sectionTitle")}</h2>
        <div className="alert alert-error" role="alert">
          {t("settings.streamRecovery.loadError")}{" "}
          <button type="button" className="btn" onClick={() => refetch()}>
            {t("common.retry")}
          </button>
        </div>
      </section>
    );
  }

  const minutes = parseMinutes(form.minutes);
  const attempts = parseAttempts(form.attempts);
  const minutesMessage =
    minutes === null
      ? t("settings.streamRecovery.minutesInvalid", { min: MIN_MINUTES, max: MAX_MINUTES })
      : serverErrors.min_play_seconds;
  const attemptsMessage =
    attempts === null
      ? t("settings.streamRecovery.attemptsInvalid", { min: MIN_ATTEMPTS, max: MAX_ATTEMPTS })
      : serverErrors.max_attempts_per_hour;
  const valid = minutes !== null && attempts !== null;
  const canSave = valid && isDirty(form, baseline) && !save.isPending;

  const update = (patch: Partial<StreamRecoveryForm>) => {
    setForm((current) => ({ ...current, ...patch }));
    setServerErrors({});
    setFormError("");
    setStatus("");
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSave || minutes === null || attempts === null) return;
    save.mutate(
      {
        enabled: form.enabled,
        min_play_seconds: minutesToSeconds(minutes),
        max_attempts_per_hour: attempts,
      },
      {
        onSuccess: () => {
          const message = t("settings.streamRecovery.saved");
          setStatus(message);
          show(message, "success");
        },
        onError: (error) => {
          const fields = getFieldErrors(error, t);
          setServerErrors(fields);
          if (Object.keys(fields).length === 0) {
            setFormError(getApiErrorMessage(t, error, "settings.streamRecovery.saveFailed"));
          }
          setStatus(t("settings.streamRecovery.saveFailed"));
        },
      }
    );
  };

  return (
    <section className="settings-section" id="stream-recovery">
      <h2 className="section-title">{t("settings.streamRecovery.sectionTitle")}</h2>
      <div className="settings-card">
        <form onSubmit={onSubmit} aria-busy={save.isPending}>
          <label className="stream-recovery-switch">
            <input
              type="checkbox"
              role="switch"
              checked={form.enabled}
              aria-describedby="stream-recovery-explanation"
              onChange={(e) => update({ enabled: e.target.checked })}
            />
            {t("settings.streamRecovery.enable")}
          </label>
          <p id="stream-recovery-explanation" className="stream-recovery-hint">
            {t("settings.streamRecovery.explanation")}
          </p>

          <div className="stream-recovery-field">
            <label htmlFor="stream-recovery-minutes">
              {t("settings.streamRecovery.minutesLabel")}
            </label>
            <input
              id="stream-recovery-minutes"
              className="stream-recovery-number"
              type="number"
              step={1}
              min={MIN_MINUTES}
              max={MAX_MINUTES}
              value={form.minutes}
              disabled={!form.enabled}
              aria-invalid={Boolean(minutesMessage)}
              aria-describedby={minutesMessage ? "stream-recovery-minutes-error" : undefined}
              onChange={(e) => update({ minutes: e.target.value })}
            />
            {minutesMessage && (
              <span id="stream-recovery-minutes-error" className="stream-recovery-error">
                {minutesMessage}
              </span>
            )}
          </div>

          <div className="stream-recovery-field">
            <label htmlFor="stream-recovery-attempts">
              {t("settings.streamRecovery.attemptsLabel")}
            </label>
            <input
              id="stream-recovery-attempts"
              className="stream-recovery-number"
              type="number"
              step={1}
              min={MIN_ATTEMPTS}
              max={MAX_ATTEMPTS}
              value={form.attempts}
              disabled={!form.enabled}
              aria-invalid={Boolean(attemptsMessage)}
              aria-describedby={attemptsMessage ? "stream-recovery-attempts-error" : undefined}
              onChange={(e) => update({ attempts: e.target.value })}
            />
            {attemptsMessage && (
              <span id="stream-recovery-attempts-error" className="stream-recovery-error">
                {attemptsMessage}
              </span>
            )}
          </div>

          {formError && (
            <div className="alert alert-error" role="alert">
              {formError}
            </div>
          )}

          <div className="stream-recovery-actions">
            <button type="submit" className="btn btn-primary" disabled={!canSave}>
              {save.isPending
                ? t("settings.streamRecovery.saving")
                : t("settings.streamRecovery.save")}
            </button>
            <span role="status" aria-live="polite">
              {status}
            </span>
          </div>
        </form>

        <button
          type="button"
          className="btn stream-recovery-activity-toggle"
          aria-expanded={expanded}
          aria-controls="stream-recovery-activity"
          onClick={() => setExpanded((open) => !open)}
        >
          {t("settings.streamRecovery.activityToggle")}
        </button>
        <ActivityLog expanded={expanded} />
      </div>
    </section>
  );
}
