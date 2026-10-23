import { useState, useRef, useEffect, useLayoutEffect, KeyboardEvent } from "react";
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
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [fontSizePx, setFontSizePx] = useState(24);

  useLayoutEffect(() => {
    const el = buttonRef.current;
    if (!el) return;

    // The button shrinks to its content, so the space it may use is the width of its heading.
    const host = el.parentElement ?? el;
    const compute = () => {
      const containerWidth = host.clientWidth;
      if (!containerWidth) return;

      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const elStyle = getComputedStyle(el);
      const fontWeight = elStyle.fontWeight || "600";
      const fontFamily = elStyle.fontFamily || "system-ui, -apple-system, sans-serif";
      const gapWidth = parseFloat(elStyle.gap) || 0;
      // Text and icon sit inside the button's horizontal padding
      const paddingX =
        (parseFloat(elStyle.paddingLeft) || 0) + (parseFloat(elStyle.paddingRight) || 0);

      for (let size = 24; size >= 17; size--) {
        ctx.font = `${fontWeight} ${size}px ${fontFamily}`;
        const textWidth = ctx.measureText(name).width;
        // The pencil is an SVG of exactly 0.65em (was an emoji glyph measured via canvas)
        const iconWidth = size * 0.65;
        const safetyBuffer = 2; // 1px subpixel rounding tolerance
        if (textWidth + iconWidth + gapWidth + paddingX + safetyBuffer <= containerWidth) {
          setFontSizePx(size);
          return;
        }
      }
      setFontSizePx(17);
    };

    compute();
    const observer = new ResizeObserver(compute);
    observer.observe(host);
    return () => observer.disconnect();
  }, [name]);

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

  return (
    <h2 className="dne-heading">
      <button
        ref={buttonRef}
        type="button"
        className="dne-btn"
        style={{ fontSize: `${fontSizePx}px` }}
        onClick={startEditing}
        title={t("deviceRename.clickToEdit")}
        data-test="device-name"
        aria-label={`${name} — ${t("deviceRename.clickToEdit")}`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") startEditing();
        }}
      >
        <span className="dne-text">{name}</span>
        <span className="dne-icon" aria-hidden="true">
          {Icon.Pencil(Math.round(fontSizePx * 0.65))}
        </span>
      </button>
    </h2>
  );
}
