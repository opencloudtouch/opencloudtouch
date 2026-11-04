/**
 * Pure helpers of the stream recovery settings form (minutes <-> seconds,
 * validation, dirty check, play-time split).
 */

export const MIN_MINUTES = 1;
export const MAX_MINUTES = 1440;
export const MIN_ATTEMPTS = 1;
export const MAX_ATTEMPTS = 10;

const INTEGER = /^\d+$/;

/** Parsed integer inside [min, max], or null for anything else (empty, decimals, text). */
function parseIntegerInRange(text: string, min: number, max: number): number | null {
  const trimmed = text.trim();
  if (!INTEGER.test(trimmed)) return null;
  const value = Number(trimmed);
  return value >= min && value <= max ? value : null;
}

export function parseMinutes(text: string): number | null {
  return parseIntegerInRange(text, MIN_MINUTES, MAX_MINUTES);
}

export function parseAttempts(text: string): number | null {
  return parseIntegerInRange(text, MIN_ATTEMPTS, MAX_ATTEMPTS);
}

export function secondsToMinutes(seconds: number): number {
  return Math.round(seconds / 60);
}

export function minutesToSeconds(minutes: number): number {
  return minutes * 60;
}

export interface StreamRecoveryForm {
  enabled: boolean;
  minutes: string;
  attempts: string;
}

function sameNumber(a: string, b: string, parse: (text: string) => number | null): boolean {
  const parsedA = parse(a);
  const parsedB = parse(b);
  return parsedA !== null && parsedB !== null ? parsedA === parsedB : a.trim() === b.trim();
}

/** True when the form differs from the stored baseline (numbers compared by value). */
export function isDirty(form: StreamRecoveryForm, baseline: StreamRecoveryForm): boolean {
  return (
    form.enabled !== baseline.enabled ||
    !sameNumber(form.minutes, baseline.minutes, parseMinutes) ||
    !sameNumber(form.attempts, baseline.attempts, parseAttempts)
  );
}

/** Whole hours and the remaining minutes of a play time. */
export function splitPlayTime(seconds: number): { hours: number; minutes: number } {
  const totalMinutes = Math.floor(seconds / 60);
  return { hours: Math.floor(totalMinutes / 60), minutes: totalMinutes % 60 };
}
