import { useRef, type KeyboardEvent, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./SourceSwitch.css";

export type DeviceSource = "presets" | "bluetooth" | "aux";

const SOURCES: { id: DeviceSource; labelKey: string; icon: () => ReactElement }[] = [
  { id: "presets", labelKey: "device.src.presets", icon: () => Icon.Radio(18) },
  { id: "bluetooth", labelKey: "player.source.bluetooth", icon: () => Icon.Bluetooth(18) },
  { id: "aux", labelKey: "player.source.aux", icon: () => Icon.Headphones(18) },
];

interface SourceSwitchProps {
  /** The source the device plays now; null when it plays something that cannot be chosen here (Spotify, AirPlay, ...). */
  current: DeviceSource | null;
  /** The source a switch is running for. */
  switching: DeviceSource | null;
  /** The source whose last switch failed: its key is marked, tapping it tries again. */
  failed?: DeviceSource | null;
  /** Standby, zone member or a switch in progress: the buttons stay in place but do nothing. */
  disabled: boolean;
  /** id of a visually hidden element that explains why the buttons are disabled. */
  describedBy?: string;
  onSelect: (source: DeviceSource) => void;
}

/**
 * Three small round buttons in the header of the now-playing block: Presets, Bluetooth, AUX.
 * One tab stop (the pressed one), arrow keys move the focus, Enter/Space switches.
 */
export default function SourceSwitch({
  current,
  switching,
  failed = null,
  disabled,
  describedBy,
  onSelect,
}: Readonly<SourceSwitchProps>) {
  const { t } = useTranslation();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const tabStop = current ?? "presets";

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = SOURCES.length - 1;
    let next: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      next = index === last ? 0 : index + 1;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      next = index === 0 ? last : index - 1;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = last;
    }
    if (next === null) return;
    event.preventDefault();
    refs.current[next]?.focus();
  };

  return (
    <div className="si-b" role="group" aria-label={t("device.sourceChoose")}>
      {SOURCES.map((source, index) => {
        const busy = switching === source.id;
        const pressed = current === source.id && !busy;
        const label = t(source.labelKey);
        const isFailed = failed === source.id && !busy;
        const name = isFailed ? t("device.sourceFailedKey", { source: label }) : label;
        return (
          <button
            key={source.id}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            className={isFailed ? "si-bb si-bb--fail" : "si-bb"}
            data-testid={`source-${source.id}`}
            aria-pressed={pressed}
            aria-busy={busy || undefined}
            aria-disabled={disabled || undefined}
            aria-describedby={describedBy}
            aria-label={name}
            title={name}
            tabIndex={tabStop === source.id ? 0 : -1}
            onKeyDown={(event) => onKeyDown(event, index)}
            onClick={() => {
              if (!disabled && !pressed) onSelect(source.id);
            }}
          >
            <span className="si-bb-in">
              {busy ? <span className="ui-spin">{Icon.Loader(18)}</span> : source.icon()}
            </span>
            {isFailed && (
              <span className="si-bb-x" aria-hidden="true">
                {Icon.X(10)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
