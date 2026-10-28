import {
  useState,
  useRef,
  useEffect,
  useLayoutEffect,
  KeyboardEvent,
  type CSSProperties,
} from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { renameDevice } from "../api/devices";
import { Icon } from "./Icon";
import "./DeviceNameEditor.css";

interface DeviceNameEditorProps {
  readonly deviceId: string;
  readonly name: string;
  readonly onRenamed?: (newName: string) => void;
}

export default function DeviceNameEditor({
  deviceId,
  name,
  onRenamed,
}: Readonly<DeviceNameEditorProps>) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  const [overflowPx, setOverflowPx] = useState(0);

  // The name is centred at a fixed size; only a name that does not fit scrolls (marquee as in NowPlaying), it is never shrunk or wrapped.
  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const text = textRef.current;
    if (!wrap || !text) return;

    const measure = () => {
      const extra = text.scrollWidth - wrap.clientWidth;
      setOverflowPx(extra > 1 ? Math.ceil(extra) : 0);
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [name, editing]);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const startEditing = () => {
    setEditValue(name);
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    if (saving) return;
    setEditing(false);
    setEditValue(name);
    setError(null);
  };

  const save = async () => {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === name) {
      cancel();
      return;
    }
    if (trimmed.length > 30) {
      setError(t("deviceRename.tooLong"));
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const result = await renameDevice(deviceId, trimmed);
      setEditing(false);
      onRenamed?.(result.name);
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    } catch {
      setError(t("deviceRename.failed"));
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      save();
    } else if (e.key === "Escape") {
      cancel();
    }
  };

  const handleBlur = () => {
    if (saving) return;
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== name) {
      save();
    } else {
      cancel();
    }
  };

  if (editing) {
    return (
      <div className="dne" data-test="device-name-editor">
        <h2 className="dne-heading">
          <span className="dne-field">
            <input
              ref={inputRef}
              className="ui-input dne-input"
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleBlur}
              maxLength={30}
              disabled={saving}
              aria-label={t("deviceRename.inputLabel")}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "device-name-error" : undefined}
              aria-busy={saving}
              data-test="device-name-input"
            />
            {saving && (
              <span className="dne-saving ui-spin" aria-hidden="true">
                {Icon.Loader(18)}
              </span>
            )}
          </span>
        </h2>
        {error && (
          <span
            id="device-name-error"
            className="ui-field-error dne-error"
            role="alert"
            data-test="device-name-error"
          >
            {Icon.CircleX(16)}
            <span>{error}</span>
          </span>
        )}
      </div>
    );
  }

  const scrolling = overflowPx > 0;

  return (
    <h2 className="dne-heading">
      <button
        type="button"
        className="dne-btn"
        onClick={startEditing}
        title={t("deviceRename.clickToEdit")}
        data-test="device-name"
        aria-label={`${name} — ${t("deviceRename.clickToEdit")}`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") startEditing();
        }}
      >
        <span ref={wrapRef} className="dne-text-wrap">
          <span
            ref={textRef}
            className={`dne-text${scrolling ? " dne-text--scrolling" : ""}`}
            style={
              scrolling
                ? ({
                    "--marquee-distance": `-${overflowPx}px`,
                    animationDuration: `${Math.max(6, overflowPx / 10)}s`,
                  } as CSSProperties)
                : undefined
            }
          >
            {name}
          </span>
        </span>
        <span className="dne-icon" aria-hidden="true">
          {Icon.Pencil(16)}
        </span>
      </button>
    </h2>
  );
}
