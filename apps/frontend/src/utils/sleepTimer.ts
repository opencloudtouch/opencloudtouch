/**
 * Pure helpers of the sleep timer: option lists, validation, remembered defaults,
 * server-clock countdown and the derived phase.
 */

import type { EndAction } from "../api/sleepTimer";

export const DURATION_PRESETS = [15, 30, 45, 60, 90, 120] as const;
export const FADE_OPTIONS = [0, 10, 30, 60] as const;
export const MIN_DURATION = 1;
export const MAX_DURATION = 720;
export const DEFAULT_DURATION = 30;
export const DEFAULT_FADE = 30;
export const DEFAULT_END_ACTION: EndAction = "stop";
export const STORAGE_KEY = "oct.sleepTimer.defaults";

export interface SleepTimerDefaults {
  duration: number;
  fade: number;
  endAction: EndAction;
}

/** Whole minutes from MIN_DURATION to MAX_DURATION, otherwise null. */
export function parseDuration(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const value = Number(trimmed);
  return value >= MIN_DURATION && value <= MAX_DURATION ? value : null;
}

/** A fade must not be longer than the timer. */
export function isFadeAllowed(fadeSeconds: number, durationMinutes: number): boolean {
  return fadeSeconds <= durationMinutes * 60;
}

/** The longest offered fade that still fits into the duration (0 always fits). */
export function clampFade(fadeSeconds: number, durationMinutes: number): number {
  if (isFadeAllowed(fadeSeconds, durationMinutes)) return fadeSeconds;
  const fitting = FADE_OPTIONS.filter((option) => isFadeAllowed(option, durationMinutes));
  return fitting.length > 0 ? Math.max(...fitting) : 0;
}

function isEndAction(value: unknown): value is EndAction {
  return value === "stop" || value === "standby";
}

/** Remembered form values; invalid or unreadable storage gives the defaults. */
export function loadDefaults(): SleepTimerDefaults {
  const fallback: SleepTimerDefaults = {
    duration: DEFAULT_DURATION,
    fade: DEFAULT_FADE,
    endAction: DEFAULT_END_ACTION,
  };
  try {
    const raw = globalThis.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const stored = JSON.parse(raw) as Record<string, unknown>;
    const duration =
      typeof stored.duration === "number" && parseDuration(String(stored.duration)) !== null
        ? stored.duration
        : fallback.duration;
    const fade =
      typeof stored.fade === "number" && (FADE_OPTIONS as readonly number[]).includes(stored.fade)
        ? stored.fade
        : fallback.fade;
    return {
      duration,
      fade: clampFade(fade, duration),
      endAction: isEndAction(stored.endAction) ? stored.endAction : fallback.endAction,
    };
  } catch {
    return fallback;
  }
}

export function saveDefaults(defaults: SleepTimerDefaults): void {
  try {
    globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults));
  } catch {
    // storage may be blocked (private window): the timer works without it
  }
}

/** Milliseconds between the server's clock and this device's clock, at receipt. */
export function clockOffsetMs(serverTime: string, receivedAtMs: number): number {
  return Date.parse(serverTime) - receivedAtMs;
}

/** Milliseconds until `endsAt`, measured on the server's clock. */
export function remainingMs(endsAt: string, offsetMs: number, nowMs: number): number {
  return Date.parse(endsAt) - (nowMs + offsetMs);
}

/** `m:ss` below one hour, `h:mm:ss` otherwise; never negative. */
export function formatCountdown(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const ss = String(seconds).padStart(2, "0");
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${ss}`;
  return `${minutes}:${ss}`;
}

export type Phase = "running" | "fading" | "ending";

/** Phase derived locally; the server `state` is only used until the first tick. */
export function derivePhase(
  endsAt: string,
  fadeSeconds: number,
  offsetMs: number,
  nowMs: number
): Phase {
  const remaining = remainingMs(endsAt, offsetMs, nowMs);
  if (remaining <= 0) return "ending";
  if (fadeSeconds > 0 && remaining <= fadeSeconds * 1000) return "fading";
  return "running";
}
