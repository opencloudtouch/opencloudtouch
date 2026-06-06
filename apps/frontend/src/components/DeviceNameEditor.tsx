import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { renameDevice } from "../api/devices";
import "./DeviceNameEditor.css";

interface DeviceNameEditorProps {
  readonly deviceId: string;
  readonly name: string;
  readonly onRenamed?: (newName: string) => void;
}

export default function DeviceNameEditor({ deviceId, name, onRenamed }: Readonly<DeviceNameEditorProps>) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
      <div className="device-name-editor" data-test="device-name-editor">
        <input
          ref={inputRef}
          className="device-name-input"
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          maxLength={30}
          disabled={saving}
          aria-label={t("deviceRename.inputLabel")}
          data-test="device-name-input"
        />
        {error && (
          <span className="device-name-error" data-test="device-name-error">
            {error}
          </span>
        )}
      </div>
    );
  }

  const fontSizePx = Math.max(16, Math.round((24 * 10) / Math.max(name.length, 10)));

  return (
    <button
      type="button"
      className="device-name device-name-editable"
      style={{ fontSize: `${fontSizePx}px` }}
      onClick={startEditing}
      title={t("deviceRename.clickToEdit")}
      data-test="device-name"
      aria-label={`${name} — ${t("deviceRename.clickToEdit")}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") startEditing();
      }}
    >
      <span className="device-name-text">{name}</span>
      <span className="device-name-edit-icon" aria-hidden="true">
        ✏️
      </span>
    </button>
  );
}
