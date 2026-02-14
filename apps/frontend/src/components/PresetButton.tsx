import "./PresetButton.css";

export interface Preset {
  station_name: string;
  // Add other preset fields as needed
}

interface PresetButtonProps {
  number: number;
  preset?: Preset | null;
  onAssign: () => void;
  onClear: () => void;
  onPlay: () => void;
}

export default function PresetButton({
  number,
  preset,
  onAssign,
  onClear,
  onPlay,
}: PresetButtonProps) {
  return (
    <div className="preset-button" data-testid={`preset-${number}`}>
      {preset ? (
        <>
          <button className="preset-play" onClick={onPlay} data-testid={`preset-play-${number}`}>
            <span className="preset-number">{number}</span>
            <span className="preset-name">{preset.station_name}</span>
          </button>
          <button
            className="preset-clear"
            onClick={onClear}
            aria-label="Clear preset"
            data-testid={`preset-clear-${number}`}
          >
            ✕
          </button>
        </>
      ) : (
        <button className="preset-empty" onClick={onAssign} data-testid={`preset-empty-${number}`}>
          <span className="preset-number">{number}</span>
          <span className="preset-placeholder">Preset zuweisen</span>
        </button>
      )}
    </div>
  );
}
