import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import {
  getBass,
  getDeviceSettingsCapabilities,
  isDeviceOfflineError,
  setBass,
  type BassCapabilities,
} from "../api/devices";
import "./DeviceSettingsButton.css";

interface DeviceSettingsButtonProps {
  readonly deviceId: string;
  readonly deviceName: string;
}

export default function DeviceSettingsButton({ deviceId, deviceName }: DeviceSettingsButtonProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [capabilities, setCapabilities] = useState<BassCapabilities | null>(null);
  const [value, setValue] = useState(0);
  const [confirmed, setConfirmed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const valueRef = useRef(0);
  const confirmedRef = useRef(0);
  const savingRef = useRef(false);
  const pendingRef = useRef<number | null>(null);
  const requestGenerationRef = useRef(0);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pointerActiveRef = useRef(false);

  const clearSaveTimer = () => {
    if (saveTimerRef.current !== null) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  };

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError(null);
    setCapabilities(null);

    async function load() {
      try {
        const flags = await getDeviceSettingsCapabilities(deviceId);
        const bass = flags.settings?.bass;
        if (!active) return;
        if (!flags.features?.bass_control || !bass?.available) return;
        const state = await getBass(deviceId);
        if (!active) return;
        setCapabilities(bass);
        valueRef.current = state.target;
        confirmedRef.current = state.target;
        setValue(state.target);
        setConfirmed(state.target);
      } catch (err) {
        if (active) setError(t(isDeviceOfflineError(err) ? "deviceSettings.offline" : "deviceSettings.loadFailed"));
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    closeButtonRef.current?.focus();

    return () => {
      active = false;
      clearSaveTimer();
      pointerActiveRef.current = false;
      requestGenerationRef.current += 1;
      pendingRef.current = null;
      savingRef.current = false;
      setSaving(false);
    };
  }, [open, deviceId, t]);

  const close = () => {
    clearSaveTimer();
    pointerActiveRef.current = false;
    // Pending responses must not update a closed (or subsequently reopened) dialog.
    requestGenerationRef.current += 1;
    pendingRef.current = null;
    savingRef.current = false;
    setSaving(false);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const changeValue = (next: number) => {
    valueRef.current = next;
    setValue(next);
  };

  const save = async (next: number) => {
    if (savingRef.current) {
      // Keep the latest release while a previous write is still in flight.
      pendingRef.current = next;
      return;
    }
    if (next === confirmedRef.current) return;
    savingRef.current = true;
    const generation = requestGenerationRef.current;
    setSaving(true);
    setError(null);
    try {
      await setBass(deviceId, next);
      if (generation !== requestGenerationRef.current) return;
      confirmedRef.current = next;
      setConfirmed(next);
    } catch (err) {
      if (generation !== requestGenerationRef.current) return;
      pendingRef.current = null;
      changeValue(confirmedRef.current);
      setError(t(isDeviceOfflineError(err) ? "deviceSettings.offline" : "deviceSettings.saveFailed"));
      return;
    } finally {
      if (generation === requestGenerationRef.current) {
        savingRef.current = false;
        setSaving(false);
      }
    }
    if (generation !== requestGenerationRef.current) return;
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending !== null && pending !== confirmedRef.current) {
      void save(pending);
    }
  };

  const scheduleSave = () => {
    clearSaveTimer();
    saveTimerRef.current = setTimeout(() => {
      saveTimerRef.current = null;
      if (!pointerActiveRef.current) {
        void save(valueRef.current);
      }
    }, 400);
  };

  const onDialogKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== "Tab") return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        "button, input, select, textarea, a[href], [tabindex]"
      )
    ).filter((element) =>
      element.tabIndex >= 0 &&
      !element.hasAttribute("disabled")
    );
    if (!focusable.length) return;
    const first = focusable.at(0);
    const last = focusable.at(-1);
    if (!first || !last) return;
    if (!dialog.contains(document.activeElement)) {
      e.preventDefault();
      (e.shiftKey ? last : first).focus();
      return;
    }
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      onDialogKeyDown(event);
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  });

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="device-settings-trigger"
        aria-label={t("deviceSettings.open", { name: deviceName })}
        title={t("deviceSettings.title")}
        onClick={() => setOpen(true)}
        data-test="device-settings-button"
      >
        <svg
          width="19"
          height="19"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
          <path d="M12.22 2h-.44a2 2 0 0 0-2 1.72l-.15 1.06a2 2 0 0 1-2.69 1.57l-.96-.4a2 2 0 0 0-2.44.85l-.22.38a2 2 0 0 0 .46 2.55l.82.66a2 2 0 0 1 0 3.12l-.82.66a2 2 0 0 0-.46 2.55l.22.38a2 2 0 0 0 2.44.85l.96-.4a2 2 0 0 1 2.69 1.57l.15 1.06A2 2 0 0 0 11.78 22h.44a2 2 0 0 0 2-1.72l.15-1.06a2 2 0 0 1 2.69-1.57l.96.4a2 2 0 0 0 2.44-.85l.22-.38a2 2 0 0 0-.46-2.55l-.82-.66a2 2 0 0 1 0-3.12l.82-.66a2 2 0 0 0 .46-2.55l-.22-.38a2 2 0 0 0-2.44-.85l-.96.4a2 2 0 0 1-2.69-1.57l-.15-1.06A2 2 0 0 0 12.22 2z" />
        </svg>
      </button>
      {open &&
        createPortal(
          <div
            className="device-settings-backdrop"
            onMouseDown={(e) => {
              if (e.target === e.currentTarget) close();
            }}
          >
            <section
              ref={dialogRef}
              className="device-settings-dialog"
              role="dialog"
              aria-modal="true"
              aria-label={t("deviceSettings.title")}
              data-test="device-settings-dialog"
            >
              <header className="device-settings-header">
                <div>
                  <h2>{t("deviceSettings.title")}</h2>
                  <p>{deviceName}</p>
                </div>
                <button
                  ref={closeButtonRef}
                  type="button"
                  onClick={close}
                  aria-label={t("deviceSettings.close")}
                >
                  ×
                </button>
              </header>
              {loading ? (
                <p role="status">{t("deviceSettings.loading")}</p>
              ) : capabilities ? (
                <div className="device-settings-bass">
                  <div className="device-settings-bass-heading">
                    <label htmlFor={`bass-${deviceId}`}>{t("deviceSettings.bass")}</label>
                    <output>{value}</output>
                  </div>
                  <input
                    id={`bass-${deviceId}`}
                    type="range"
                    min={capabilities.minimum}
                    max={capabilities.maximum}
                    step={1}
                    value={value}
                    aria-busy={saving}
                    onChange={(e) => {
                      changeValue(Number(e.currentTarget.value));
                      if (!pointerActiveRef.current) scheduleSave();
                    }}
                    onPointerDown={() => {
                      pointerActiveRef.current = true;
                      clearSaveTimer();
                    }}
                    onPointerUp={() => {
                      pointerActiveRef.current = false;
                      clearSaveTimer();
                      void save(valueRef.current);
                    }}
                    onPointerCancel={() => {
                      pointerActiveRef.current = false;
                      clearSaveTimer();
                      changeValue(confirmedRef.current);
                    }}
                    onKeyUp={(e) => {
                      if (
                        [
                          "ArrowLeft",
                          "ArrowRight",
                          "ArrowUp",
                          "ArrowDown",
                          "Home",
                          "End",
                          "PageUp",
                          "PageDown",
                        ].includes(e.key)
                      ) {
                        clearSaveTimer();
                        void save(Number(e.currentTarget.value));
                      }
                    }}
                    onBlur={() => {
                      clearSaveTimer();
                      if (!pointerActiveRef.current) void save(valueRef.current);
                    }}
                    data-test="bass-slider"
                  />
                  <div className="device-settings-bass-range">
                    <span>{capabilities.minimum}</span>
                    <span>{capabilities.maximum}</span>
                  </div>
                  <button
                    type="button"
                    className="device-settings-reset"
                    disabled={value === capabilities.default && confirmed === capabilities.default}
                    onClick={() => {
                      clearSaveTimer();
                      changeValue(capabilities.default);
                      void save(capabilities.default);
                    }}
                  >
                    {t("deviceSettings.reset")}
                  </button>
                </div>
              ) : !error ? (
                <p>{t("deviceSettings.noOptions")}</p>
              ) : null}
              {error && (
                <p className="device-settings-error" role="alert">
                  {error}
                </p>
              )}
            </section>
          </div>,
          document.body
        )}
    </>
  );
}
