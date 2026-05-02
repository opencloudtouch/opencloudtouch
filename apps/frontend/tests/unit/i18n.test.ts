import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  detectLocale,
  changeLanguage,
  SUPPORTED_LOCALES,
  UI_LOCALES,
  LOCALE_CONFIGS,
} from "../../src/i18n";
import en from "../../src/i18n/locales/en.json";
import de from "../../src/i18n/locales/de.json";
import fr from "../../src/i18n/locales/fr.json";
import itLocale from "../../src/i18n/locales/it.json";
import es from "../../src/i18n/locales/es.json";
import nl from "../../src/i18n/locales/nl.json";
import ptBR from "../../src/i18n/locales/pt-BR.json";
import ja from "../../src/i18n/locales/ja.json";
import pl from "../../src/i18n/locales/pl.json";
import sv from "../../src/i18n/locales/sv.json";

describe("detectLocale", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.spyOn(navigator, "language", "get").mockReturnValue("en-US");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns stored locale from localStorage", () => {
    localStorage.setItem("oct-lang", "de");
    expect(detectLocale()).toBe("de");
  });

  it("returns 'en' when localStorage has 'en'", () => {
    localStorage.setItem("oct-lang", "en");
    expect(detectLocale()).toBe("en");
  });

  it("ignores unsupported locale in localStorage", () => {
    localStorage.setItem("oct-lang", "zh");
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-DE");
    expect(detectLocale()).toBe("de");
  });

  it("falls back to navigator.language prefix", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-DE");
    expect(detectLocale()).toBe("de");
  });

  it("falls back to 'en' for unsupported browser language", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("ko-KR");
    expect(detectLocale()).toBe("en");
  });

  it("returns 'de' for Austrian browser locale (resolves to UI locale)", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-AT");
    expect(detectLocale()).toBe("de");
  });

  it("returns 'de' for Swiss German browser locale (resolves to UI locale)", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-CH");
    expect(detectLocale()).toBe("de");
  });

  it("returns 'fr' for French browser locale", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("fr-FR");
    expect(detectLocale()).toBe("fr");
  });

  it("returns 'fr' for Swiss French browser locale (prefix match)", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("fr-CH");
    expect(detectLocale()).toBe("fr");
  });

  it("returns 'it' for Italian browser locale", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("it-IT");
    expect(detectLocale()).toBe("it");
  });

  it("returns 'it' for Swiss Italian browser locale (prefix match)", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("it-CH");
    expect(detectLocale()).toBe("it");
  });

  it("falls back to 'en' when localStorage is empty and language unsupported", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("zh-CN");
    expect(detectLocale()).toBe("en");
  });
});

describe("SUPPORTED_LOCALES", () => {
  it("contains all detection locales incl. regional variants", () => {
    expect(SUPPORTED_LOCALES).toContain("en");
    expect(SUPPORTED_LOCALES).toContain("de");
    expect(SUPPORTED_LOCALES).toContain("de-AT");
    expect(SUPPORTED_LOCALES).toContain("de-CH");
    expect(SUPPORTED_LOCALES).toContain("fr");
    expect(SUPPORTED_LOCALES).toContain("it");
  });
});

describe("UI_LOCALES", () => {
  it("contains only selectable UI locales (no regional variants)", () => {
    expect(UI_LOCALES).toContain("en");
    expect(UI_LOCALES).toContain("de");
    expect(UI_LOCALES).toContain("fr");
    expect(UI_LOCALES).toContain("it");
    expect(UI_LOCALES).not.toContain("de-AT");
    expect(UI_LOCALES).not.toContain("de-CH");
  });
});

describe("LOCALE_CONFIGS", () => {
  it("has config for each UI locale (no regional variants)", () => {
    for (const locale of UI_LOCALES) {
      expect(LOCALE_CONFIGS[locale]).toBeDefined();
      expect(LOCALE_CONFIGS[locale].code).toBe(locale);
      expect(LOCALE_CONFIGS[locale].flag).toBeTruthy();
      expect(LOCALE_CONFIGS[locale].nativeName).toBeTruthy();
      expect(LOCALE_CONFIGS[locale].shortCode).toBeTruthy();
    }
  });
});

describe("changeLanguage", () => {
  it("stores the locale in localStorage", () => {
    changeLanguage("de");
    expect(localStorage.getItem("oct-lang")).toBe("de");
    changeLanguage("fr");
    expect(localStorage.getItem("oct-lang")).toBe("fr");
    changeLanguage("en");
    expect(localStorage.getItem("oct-lang")).toBe("en");
  });
});

describe("Translation key parity", () => {
  function flattenKeys(obj: object, prefix = ""): string[] {
    return Object.entries(obj).flatMap(([key, value]) => {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (value !== null && typeof value === "object" && !Array.isArray(value)) {
        return flattenKeys(value as object, fullKey);
      }
      return [fullKey];
    });
  }

  const enKeys = () => flattenKeys(en);

  it("de.json has all keys from en.json", () => {
    const deKeys = new Set(flattenKeys(de));
    expect(enKeys().filter((k) => !deKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from de.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(de).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("fr.json has all keys from en.json", () => {
    const frKeys = new Set(flattenKeys(fr));
    expect(enKeys().filter((k) => !frKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from fr.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(fr).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("it.json has all keys from en.json", () => {
    const itKeys = new Set(flattenKeys(itLocale));
    expect(enKeys().filter((k) => !itKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from it.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(itLocale).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("es.json has all keys from en.json", () => {
    const esKeys = new Set(flattenKeys(es));
    expect(enKeys().filter((k) => !esKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from es.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(es).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("nl.json has all keys from en.json", () => {
    const nlKeys = new Set(flattenKeys(nl));
    expect(enKeys().filter((k) => !nlKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from nl.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(nl).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("pt-BR.json has all keys from en.json", () => {
    const ptKeys = new Set(flattenKeys(ptBR));
    expect(enKeys().filter((k) => !ptKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from pt-BR.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(ptBR).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("ja.json has all keys from en.json", () => {
    const jaKeys = new Set(flattenKeys(ja));
    expect(enKeys().filter((k) => !jaKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from ja.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(ja).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("pl.json has all keys from en.json", () => {
    const plKeys = new Set(flattenKeys(pl));
    expect(enKeys().filter((k) => !plKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from pl.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(pl).filter((k) => !enSet.has(k))).toEqual([]);
  });

  it("sv.json has all keys from en.json", () => {
    const svKeys = new Set(flattenKeys(sv));
    expect(enKeys().filter((k) => !svKeys.has(k))).toEqual([]);
  });

  it("en.json has all keys from sv.json", () => {
    const enSet = new Set(enKeys());
    expect(flattenKeys(sv).filter((k) => !enSet.has(k))).toEqual([]);
  });
});

describe("detectLocale — localStorage unavailable (catch branch)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back to browser language when localStorage.getItem throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("localStorage unavailable");
    });
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-DE");
    expect(detectLocale()).toBe("de");
  });

  it("falls back to 'en' when localStorage throws and browser language unsupported", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("localStorage unavailable");
    });
    vi.spyOn(navigator, "language", "get").mockReturnValue("zh-CN");
    expect(detectLocale()).toBe("en");
  });
});

describe("changeLanguage — localStorage unavailable (catch branch)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not throw when localStorage.setItem throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("localStorage unavailable");
    });
    expect(() => changeLanguage("fr")).not.toThrow();
  });
});
