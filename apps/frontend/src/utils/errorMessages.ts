/**
 * User-friendly error message mapping — REFACT-122
 *
 * Maps raw technical error messages and HTTP status text to
 * human-readable messages suitable for display in the UI.
 * Technical details are logged to console, never shown to users.
 */

import { i18next } from "../i18n";

/** Known error patterns mapped to i18n key resolver functions */
const ERROR_PATTERNS: Array<[RegExp, () => string]> = [
  // Network / connectivity
  [/failed to fetch|network\s*error|net::err/i, () => i18next.t("errors.networkFailed")],
  [/timeout|timed?\s*out|ETIMEDOUT/i, () => i18next.t("errors.timeout")],
  [/ECONNREFUSED/i, () => i18next.t("errors.connectionRefused")],

  // HTTP status-derived
  [/^HTTP\s*4(?:00|22)/i, () => i18next.t("errors.badRequest")],
  [/^HTTP\s*401/i, () => i18next.t("errors.unauthorized")],
  [/^HTTP\s*403/i, () => i18next.t("errors.forbidden")],
  [/^HTTP\s*404/i, () => i18next.t("errors.notFound")],
  [/^HTTP\s*409/i, () => i18next.t("errors.conflict")],
  [/^HTTP\s*5\d\d/i, () => i18next.t("errors.serverError")],

  // Presets
  [/failed to load presets/i, () => i18next.t("errors.presetsLoadFailed")],
  [/failed to sync presets/i, () => i18next.t("errors.presetsSyncFailed")],
  [/failed to save preset/i, () => i18next.t("errors.presetSaveFailed")],
  [/failed to clear preset/i, () => i18next.t("errors.presetClearFailed")],
  [/failed to play preset/i, () => i18next.t("errors.presetPlayFailed")],

  // Settings / IP
  [/already exists|duplicate/i, () => i18next.t("errors.alreadyExists")],
  [/invalid ip/i, () => i18next.t("errors.invalidIp")],

  // Device discovery
  [/no devices|keine geräte/i, () => i18next.t("errors.noDevices")],

  // SSH / wizard
  [/ssh.*failed|ssh.*error/i, () => i18next.t("errors.sshFailed")],
  [/port check failed/i, () => i18next.t("errors.portCheckFailed")],
  [/backup failed/i, () => i18next.t("errors.backupFailed")],
  [/config modification failed/i, () => i18next.t("errors.configFailed")],
  [/hosts modification failed/i, () => i18next.t("errors.hostsFailed")],

  // USB / file access
  [/fehler beim zugriff/i, () => i18next.t("errors.accessFailed")],
  [/fehler beim erstellen/i, () => i18next.t("errors.createFailed")],
];

/**
 * Convert any error into a user-friendly German message.
 *
 * @param error — The caught error (Error, string, or unknown)
 * @returns A non-technical, user-friendly message string
 */
export function toUserMessage(error: unknown): string {
  const raw = extractRawMessage(error);

  // Log technical detail for debugging
  if (import.meta.env.DEV) {
    console.debug("[toUserMessage] raw:", raw);
  }

  for (const [pattern, getMessage] of ERROR_PATTERNS) {
    if (pattern.test(raw)) {
      return getMessage();
    }
  }

  return i18next.t("errors.unknown");
}

/**
 * Extract raw message string from various error types.
 */
function extractRawMessage(error: unknown): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return String(error);
}
