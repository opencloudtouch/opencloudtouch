import { useRef, useEffect } from "react";
import "./VolumeSlider.css";

interface VolumeSliderProps {
  volume: number;
  onVolumeChange: (volume: number) => void;
  muted: boolean;
  onMuteToggle: () => void;
}

const VOL_ICON =
  "M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z";
const MUTE_ICON =
  "M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27l4.73 4.73H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z";

const ACCENT_COLOR = "#5dade2";
const MUTED_COLOR = "rgba(255, 255, 255, 0.35)";

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
    <div className="volume-slider">
      <button
        className={`volume-mute${muted ? " muted" : ""}`}
        onClick={onMuteToggle}
        aria-label={muted ? "Unmute" : "Mute"}
      >
        <svg viewBox="0 0 24 24" width="22" height="22">
          <path fill="currentColor" d={muted || volume === 0 ? MUTE_ICON : VOL_ICON} />
        </svg>
      </button>
      <div
        ref={trackRef}
        className={`volume-track${muted ? " muted" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        role="slider"
        aria-valuenow={volume}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Volume"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowDown")
            onVolumeChange(Math.max(0, volume - 5));
          if (e.key === "ArrowRight" || e.key === "ArrowUp")
            onVolumeChange(Math.min(100, volume + 5));
        }}
      >
        <div className="volume-track-bg" />
        <div ref={fillRef} className="volume-track-fill" />
        <div ref={thumbRef} className="volume-thumb" />
      </div>
    </div>
  );
}
