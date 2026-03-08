/**
 * User-friendly error message mapping — REFACT-122
 *
 * Maps raw technical error messages and HTTP status text to
 * human-readable German messages suitable for display in the UI.
 * Technical details are logged to console, never shown to users.
 */

/** Known error patterns mapped to user-friendly messages */
const ERROR_PATTERNS: Array<[RegExp, string]> = [
  // Network / connectivity
  [
    /failed to fetch|network\s*error|net::err/i,
    "Verbindung zum Server fehlgeschlagen. Bitte prüfen Sie Ihre Netzwerkverbindung.",
  ],
  [
    /timeout|timed?\s*out|ETIMEDOUT/i,
    "Die Anfrage hat zu lange gedauert. Bitte versuchen Sie es erneut.",
  ],
  [/ECONNREFUSED/i, "Der Server ist nicht erreichbar. Bitte starten Sie den Server neu."],

  // HTTP status-derived
  [/^HTTP\s*4(?:00|22)/i, "Ungültige Anfrage. Bitte überprüfen Sie Ihre Eingaben."],
  [/^HTTP\s*401/i, "Nicht autorisiert. Bitte melden Sie sich erneut an."],
  [/^HTTP\s*403/i, "Zugriff verweigert."],
  [/^HTTP\s*404/i, "Die angefragte Ressource wurde nicht gefunden."],
  [/^HTTP\s*409/i, "Konflikt — die Aktion konnte nicht ausgeführt werden."],
  [/^HTTP\s*5\d\d/i, "Serverfehler. Bitte versuchen Sie es später erneut."],

  // Presets
  [
    /failed to load presets/i,
    "Presets konnten nicht geladen werden. Bitte versuchen Sie es erneut.",
  ],
  [
    /failed to sync presets/i,
    "Presets konnten nicht synchronisiert werden. Bitte versuchen Sie es erneut.",
  ],
  [
    /failed to save preset/i,
    "Preset konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.",
  ],
  [
    /failed to clear preset/i,
    "Preset konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.",
  ],
  [
    /failed to play preset/i,
    "Preset konnte nicht abgespielt werden. Bitte versuchen Sie es erneut.",
  ],

  // Settings / IP
  [/already exists|duplicate/i, "Dieser Eintrag existiert bereits."],
  [/invalid ip/i, "Ungültige IP-Adresse."],

  // Device discovery
  [
    /no devices|keine geräte/i,
    "Keine Geräte gefunden. Bitte prüfen Sie, ob die Geräte eingeschaltet sind.",
  ],

  // SSH / wizard
  [
    /ssh.*failed|ssh.*error/i,
    "SSH-Verbindung fehlgeschlagen. Bitte prüfen Sie die Verbindungseinstellungen.",
  ],
  [
    /port check failed/i,
    "Port-Prüfung fehlgeschlagen. Bitte prüfen Sie die Netzwerkkonfiguration.",
  ],
  [/backup failed/i, "Backup fehlgeschlagen. Bitte versuchen Sie es erneut."],
  [/config modification failed/i, "Konfiguration konnte nicht geändert werden."],
  [/hosts modification failed/i, "Hosts-Datei konnte nicht geändert werden."],

  // USB / file access
  [/fehler beim zugriff/i, "Zugriff fehlgeschlagen. Bitte prüfen Sie die Berechtigungen."],
  [/fehler beim erstellen/i, "Datei konnte nicht erstellt werden."],
];

/** Fallback message when no pattern matches */
const FALLBACK_MESSAGE = "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es erneut.";

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

  for (const [pattern, friendly] of ERROR_PATTERNS) {
    if (pattern.test(raw)) {
      return friendly;
    }
  }

  return FALLBACK_MESSAGE;
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
