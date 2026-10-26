import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import type { EndAction } from "../api/sleepTimer";
import {
  useCancelSleepTimer,
  useSleepTimerStatus,
  useStartSleepTimer,
} from "../hooks/useSleepTimer";
import { getApiErrorMessage, getFieldErrors } from "../utils/apiErrors";
import {
  DURATION_PRESETS,
  FADE_OPTIONS,
  MAX_DURATION,
  MIN_DURATION,
  clampFade,
  derivePhase,
  formatCountdown,
  isFadeAllowed,
  loadDefaults,
  parseDuration,
  remainingMs,
  saveDefaults,
} from "../utils/sleepTimer";
import { Skeleton } from "./LoadingSkeleton";
import "./SleepTimer.css";

const CUSTOM = "custom";

interface SleepTimerProps {
  deviceId: string;
  /** The speaker is offline: a new timer cannot be started, a running one stays */
  deviceOffline: boolean;
}

export default function SleepTimer({ deviceId, deviceOffline }: Readonly<SleepTimerProps>) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useSleepTimerStatus(deviceId);
  const start = useStartSleepTimer(deviceId);
  const cancel = useCancelSleepTimer(deviceId);

  const [initial] = useState(loadDefaults);
  const [choice, setChoice] = useState(
    (DURATION_PRESETS as readonly number[]).includes(initial.duration)
      ? String(initial.duration)
      : CUSTOM
  );
  const [customText, setCustomText] = useState(String(initial.duration));
  const [fade, setFade] = useState(initial.fade);
  const [endAction, setEndAction] = useState<EndAction>(initial.endAction);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const [ended, setEnded] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const status = data?.status;
  const offsetMs = data?.offsetMs ?? 0;
  const active = Boolean(status?.active && status.ends_at);
  const endsAt = status?.ends_at ?? null;

  // One-second tick for the countdown, only while a timer runs
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active, endsAt]);

  // "Timer is no longer active" once, but only when it ran down (not when cancelled)
  const previousRef = useRef<{ endsAt: string; offsetMs: number } | null>(null);
  useEffect(() => {
    if (!data) return;
    if (data.status.active && data.status.ends_at) {
      previousRef.current = { endsAt: data.status.ends_at, offsetMs: data.offsetMs };
      setEnded(false);
      return;
    }
    const last = previousRef.current;
    previousRef.current = null;
    if (last && remainingMs(last.endsAt, last.offsetMs, Date.now()) <= 0) {
      setEnded(true);
      setAnnouncement(t("player.sleepTimer.noLongerActive"));
    }
  }, [data, t]);

  // The countdown reached 0: look at the server right away (then every 3 s)
  const refetchedForRef = useRef<string | null>(null);
  const remaining = active && endsAt ? remainingMs(endsAt, offsetMs, now) : 0;
  useEffect(() => {
    if (active && endsAt && remaining <= 0 && refetchedForRef.current !== endsAt) {
      refetchedForRef.current = endsAt;
      void refetch();
    }
  }, [active, endsAt, remaining, refetch]);

  const phase =
    active && endsAt ? derivePhase(endsAt, status?.fade_seconds ?? 0, offsetMs, now) : "running";
  const durationMinutes = choice === CUSTOM ? parseDuration(customText) : Number(choice);
  const durationError =
    choice === CUSTOM && durationMinutes === null
      ? t("player.sleepTimer.customInvalid", { min: MIN_DURATION, max: MAX_DURATION })
      : "";
  const fadeError = fieldErrors.fade_seconds;
  const canStart = durationMinutes !== null && !deviceOffline && !start.isPending;

  const changeDuration = (nextChoice: string, nextCustom: string) => {
    setChoice(nextChoice);
    setCustomText(nextCustom);
    const minutes = nextChoice === CUSTOM ? parseDuration(nextCustom) : Number(nextChoice);
    if (minutes !== null) setFade((current) => clampFade(current, minutes));
    setFieldErrors({});
    setFormError("");
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!canStart || durationMinutes === null) return;
    saveDefaults({ duration: durationMinutes, fade, endAction });
    setFieldErrors({});
    setFormError("");
    start.mutate(
      { duration_minutes: durationMinutes, fade_seconds: fade, end_action: endAction },
      {
        onSuccess: () => {
          setEnded(false);
          setAnnouncement(t("player.sleepTimer.started"));
        },
        onError: (error) => {
          const fields = getFieldErrors(error, t);
          setFieldErrors(fields);
          if (Object.keys(fields).length === 0) setFormError(getApiErrorMessage(t, error));
        },
      }
    );
  };

  const onCancel = () => {
    cancel.mutate(undefined, {
      onSuccess: () => setAnnouncement(t("player.sleepTimer.cancelled")),
      onError: (error) => setFormError(getApiErrorMessage(t, error)),
    });
  };

  const title = t("player.sleepTimer.title");

  return (
    <section className="sleep-timer" aria-labelledby="sleep-timer-title">
      <h3 id="sleep-timer-title" className="sleep-timer-title">
        {title}
      </h3>
      <p role="status" aria-live="polite" className="visually-hidden">
        {announcement}
      </p>

      {isLoading && <Skeleton height="60px" />}

      {isError && !data && (
        <div className="alert alert-error" role="alert">
          {t("player.sleepTimer.loadError")}{" "}
          <button type="button" className="btn" onClick={() => refetch()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && active && status && endsAt && (
        <div>
          <span
            className="sleep-timer-countdown"
            role="timer"
            aria-label={t("player.sleepTimer.countdownLabel")}
          >
            {formatCountdown(remaining)}
          </span>
          <p className="sleep-timer-phase">
            {phase === "ending"
              ? t("player.sleepTimer.ending")
              : `${phase === "fading" ? `${t("player.sleepTimer.fading")} ` : ""}${t(
                  "player.sleepTimer.endsWith",
                  { action: t(`player.sleepTimer.endAction.${status.end_action ?? "stop"}`) }
                )}`}
          </p>
          {formError && (
            <div className="alert alert-error" role="alert">
              {formError}
            </div>
          )}
          <button type="button" className="btn" onClick={onCancel} disabled={cancel.isPending}>
            {t("player.sleepTimer.cancel")}
          </button>
        </div>
      )}

      {data && !active && (
        <form className="sleep-timer-form" onSubmit={onSubmit} aria-busy={start.isPending}>
          {ended && <p className="sleep-timer-notice">{t("player.sleepTimer.noLongerActive")}</p>}

          <div className="sleep-timer-field">
            <label htmlFor="sleep-timer-duration">{t("player.sleepTimer.durationLabel")}</label>
            <select
              id="sleep-timer-duration"
              value={choice}
              onChange={(e) => changeDuration(e.target.value, customText)}
            >
              {DURATION_PRESETS.map((minutes) => (
                <option key={minutes} value={String(minutes)}>
                  {t("player.sleepTimer.minutes", { minutes })}
                </option>
              ))}
              <option value={CUSTOM}>{t("player.sleepTimer.custom")}</option>
            </select>
          </div>

          {choice === CUSTOM && (
            <div className="sleep-timer-field">
              <label htmlFor="sleep-timer-custom">{t("player.sleepTimer.customLabel")}</label>
              <input
                id="sleep-timer-custom"
                type="number"
                step={1}
                min={MIN_DURATION}
                max={MAX_DURATION}
                value={customText}
                aria-invalid={Boolean(durationError)}
                aria-describedby={durationError ? "sleep-timer-custom-error" : undefined}
                onChange={(e) => changeDuration(CUSTOM, e.target.value)}
              />
              {durationError && (
                <span id="sleep-timer-custom-error" className="sleep-timer-error">
                  {durationError}
                </span>
              )}
            </div>
          )}

          <div className="sleep-timer-field">
            <label htmlFor="sleep-timer-fade">{t("player.sleepTimer.fadeLabel")}</label>
            <select
              id="sleep-timer-fade"
              value={fade}
              aria-invalid={Boolean(fadeError)}
              aria-describedby={fadeError ? "sleep-timer-fade-error" : undefined}
              onChange={(e) => {
                setFade(Number(e.target.value));
                setFieldErrors({});
              }}
            >
              {FADE_OPTIONS.map((seconds) => (
                <option
                  key={seconds}
                  value={seconds}
                  disabled={durationMinutes !== null && !isFadeAllowed(seconds, durationMinutes)}
                >
                  {seconds === 0
                    ? t("player.sleepTimer.fadeOff")
                    : t("player.sleepTimer.fadeSeconds", { seconds })}
                </option>
              ))}
            </select>
            {fadeError && (
              <span id="sleep-timer-fade-error" className="sleep-timer-error">
                {fadeError}
              </span>
            )}
          </div>

          <div className="sleep-timer-field">
            <label htmlFor="sleep-timer-end">{t("player.sleepTimer.endLabel")}</label>
            <select
              id="sleep-timer-end"
              value={endAction}
              onChange={(e) => setEndAction(e.target.value as EndAction)}
            >
              <option value="stop">{t("player.sleepTimer.endAction.stop")}</option>
              <option value="standby">{t("player.sleepTimer.endAction.standby")}</option>
            </select>
          </div>

          {deviceOffline && (
            <p id="sleep-timer-offline" className="sleep-timer-hint">
              {t("player.sleepTimer.offlineHint")}
            </p>
          )}
          {formError && (
            <div className="alert alert-error" role="alert">
              {formError}
            </div>
          )}

          <div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!canStart}
              aria-describedby={deviceOffline ? "sleep-timer-offline" : undefined}
            >
              {start.isPending ? t("player.sleepTimer.starting") : t("player.sleepTimer.start")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
