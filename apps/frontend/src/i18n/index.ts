import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import de from "./locales/de.json";
import fr from "./locales/fr.json";
import it from "./locales/it.json";
import es from "./locales/es.json";
import nl from "./locales/nl.json";
import ptBR from "./locales/pt-BR.json";
import ja from "./locales/ja.json";
import pl from "./locales/pl.json";
import sv from "./locales/sv.json";

const STORAGE_KEY = "oct-lang";

/**
 * All locales recognized for auto-detection (includes regional variants).
 * de-AT and de-CH map to the German (de) translation bundle.
 */
export const SUPPORTED_LOCALES = [
  "en",
  "de",
  "de-AT",
  "de-CH",
  "fr",
  "it",
  "es",
  "nl",
  "pt-BR",
  "ja",
  "pl",
  "sv",
] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

/**
 * Locales that are selectable by the user in the UI (have their own translation file).
 * Regional variants (de-AT, de-CH) are NOT included — they are auto-detected from
 * navigator.language and resolved to the "de" bundle.
 */
export const UI_LOCALES = ["en", "de", "fr", "it", "es", "nl", "pt-BR", "ja", "pl", "sv"] as const;
export type UILocale = (typeof UI_LOCALES)[number];

export interface LocaleConfig {
  code: UILocale;
  flag: string; // ISO 3166-1 alpha-2 country code (lowercase) for flag-icons
  nativeName: string;
  shortCode: string;
}

export const LOCALE_CONFIGS: Record<UILocale, LocaleConfig> = {
  en: { code: "en", flag: "gb", nativeName: "English", shortCode: "EN" },
  de: { code: "de", flag: "de", nativeName: "Deutsch", shortCode: "DE" },
  fr: { code: "fr", flag: "fr", nativeName: "Français", shortCode: "FR" },
  it: { code: "it", flag: "it", nativeName: "Italiano", shortCode: "IT" },
  es: { code: "es", flag: "es", nativeName: "Español", shortCode: "ES" },
  nl: { code: "nl", flag: "nl", nativeName: "Nederlands", shortCode: "NL" },
  "pt-BR": { code: "pt-BR", flag: "br", nativeName: "Português (BR)", shortCode: "PT" },
  ja: { code: "ja", flag: "jp", nativeName: "日本語", shortCode: "JA" },
  pl: { code: "pl", flag: "pl", nativeName: "Polski", shortCode: "PL" },
  sv: { code: "sv", flag: "se", nativeName: "Svenska", shortCode: "SV" },
};

/** Maps regional browser locales to the closest UI locale */
const LOCALE_FALLBACK: Record<string, UILocale> = {
  "de-AT": "de",
  "de-CH": "de",
  "fr-CH": "fr",
  "it-CH": "it",
};

/** Resolve any SupportedLocale (incl. regional variants) to a UILocale */
function toUILocale(locale: string): UILocale {
  if (UI_LOCALES.includes(locale as UILocale)) return locale as UILocale;
  if (LOCALE_FALLBACK[locale]) return LOCALE_FALLBACK[locale];
  const prefix = locale.split("-")[0];
  return UI_LOCALES.includes(prefix as UILocale) ? (prefix as UILocale) : "en";
}

export function detectLocale(): UILocale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    // Only use stored value if it's a recognized locale (guards against corrupted/old data)
    if (stored && SUPPORTED_LOCALES.includes(stored as SupportedLocale)) {
      return toUILocale(stored);
    }
  } catch {
    // localStorage unavailable (private mode) — fall through to browser detection
  }
  // Check full locale first (e.g. "de-AT"), then prefix (e.g. "de")
  const full = navigator.language;
  if (SUPPORTED_LOCALES.includes(full as SupportedLocale)) return toUILocale(full);
  const prefix = navigator.language.split("-")[0];
  return UI_LOCALES.includes(prefix as UILocale) ? (prefix as UILocale) : "en";
}

void i18next.use(initReactI18next).init({
  lng: detectLocale(),
  fallbackLng: "en",
  resources: {
    en: { translation: en },
    de: { translation: de },
    fr: { translation: fr },
    it: { translation: it },
    es: { translation: es },
    nl: { translation: nl },
    "pt-BR": { translation: ptBR },
    ja: { translation: ja },
    pl: { translation: pl },
    sv: { translation: sv },
  },
  interpolation: { escapeValue: false },
});

export function changeLanguage(locale: UILocale): void {
  void i18next.changeLanguage(locale);
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // localStorage unavailable — preference not persisted, silent fail
  }
}

export { i18next };
