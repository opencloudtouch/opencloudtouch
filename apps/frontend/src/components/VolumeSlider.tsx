import { useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./VolumeSlider.css";

interface VolumeSliderProps {
  volume: number;
  onVolumeChange: (volume: number) => void;
  muted: boolean;
  onMuteToggle: () => void;
}

const ACCENT_COLOR = "#5dade2";
const MUTED_COLOR = "#8c8c8c"; // was rgba(255,255,255,.35): too faint against the track (UI contrast 3:1)

function calcValueFromClientX(trackEl: HTMLDivElement, clientX: number): number {
  const { left, width } = trackEl.getBoundingClientRect();
  return Math.round(Math.max(0, Math.min(100, ((clientX - left) / width) * 100)));
}

export default function VolumeSlider({
  volume,
  onVolumeChange,
  muted,
  onMuteToggle,
}: Readonly<VolumeSliderProps>) {
  const { t } = useTranslation();
  const trackRef = useRef<HTMLDivElement>(null);
  const fillRef = useRef<HTMLDivElement>(null);
  const thumbRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const lastClientXRef = useRef<number>(0);
  const isDraggingRef = useRef(false);
  const onVolumeChangeRef = useRef(onVolumeChange);
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSentRef = useRef<number>(0);
  onVolumeChangeRef.current = onVolumeChange;

  // Sync prop → DOM only when NOT dragging.
  // During drag, refs control the visual position exclusively.
  useEffect(() => {
    if (isDraggingRef.current) return;
    const pct = `${volume}%`;
    if (fillRef.current) {
      fillRef.current.style.width = pct;
      fillRef.current.style.backgroundColor = muted ? MUTED_COLOR : ACCENT_COLOR;
    }
    if (thumbRef.current) thumbRef.current.style.left = pct;
  }, [volume, muted]);

  const calcValue = (clientX: number): number => {
    if (!trackRef.current) return volume;
    return calcValueFromClientX(trackRef.current, clientX);
  };

  const applyValueDOM = (val: number) => {
    const pct = `${val}%`;
    if (fillRef.current) fillRef.current.style.width = pct;
    if (thumbRef.current) thumbRef.current.style.left = pct;
  };

  const THROTTLE_MS = 150;

  const sendThrottled = (val: number) => {
    const now = Date.now();
    if (now - lastSentRef.current >= THROTTLE_MS) {
      lastSentRef.current = now;
      onVolumeChangeRef.current(val);
    } else if (!throttleTimerRef.current) {
      throttleTimerRef.current = setTimeout(() => {
        throttleTimerRef.current = null;
        lastSentRef.current = Date.now();
        if (isDraggingRef.current) {
          onVolumeChangeRef.current(calcValue(lastClientXRef.current));
        }
      }, THROTTLE_MS);
    }
  };

  const scheduleFrame = () => {
    if (rafRef.current !== null) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      if (!isDraggingRef.current) return;
      const val = calcValue(lastClientXRef.current);
      applyValueDOM(val);
      sendThrottled(val);
      scheduleFrame();
    });
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation(); // prevent card swipe (Framer Motion drag) on mobile
    isDraggingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    lastClientXRef.current = e.clientX;
    applyValueDOM(calcValue(e.clientX));
    scheduleFrame();
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    lastClientXRef.current = e.clientX;
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (throttleTimerRef.current) {
      clearTimeout(throttleTimerRef.current);
      throttleTimerRef.current = null;
    }
    const finalVal = calcValue(e.clientX);
    applyValueDOM(finalVal);
    onVolumeChangeRef.current(finalVal);
  };

  return (
    <div className="vs">
      <button
        className={`vs-mute${muted ? " muted" : ""}`}
        onClick={onMuteToggle}
        aria-label={muted ? t("player.muteOn") : t("player.muteOff")}
        aria-pressed={muted}
      >
        {muted || volume === 0 ? Icon.VolumeX(24) : Icon.Volume2(24)}
      </button>
      <div
        ref={trackRef}
        className={`vs-track${muted ? " muted" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        role="slider"
        aria-valuenow={volume}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t("a11y.volume")}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
            e.preventDefault();
            onVolumeChange(Math.max(0, volume - 5));
          }
          if (e.key === "ArrowRight" || e.key === "ArrowUp") {
            e.preventDefault();
            onVolumeChange(Math.min(100, volume + 5));
          }
          // Stage 5 (additive): Home/End
          if (e.key === "Home") {
            e.preventDefault();
            onVolumeChange(0);
          }
          if (e.key === "End") {
            e.preventDefault();
            onVolumeChange(100);
          }
        }}
      >
        <div className="vs-track-bg" />
        <div ref={fillRef} className="vs-track-fill" />
        <div ref={thumbRef} className="vs-thumb" />
      </div>
      <span className="vs-value" aria-hidden="true">
        {muted ? "–" : volume}
      </span>
    </div>
  );
}
