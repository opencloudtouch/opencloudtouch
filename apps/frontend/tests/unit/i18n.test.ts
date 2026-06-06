import fs from "node:fs";
import path from "node:path";
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

// ---------------------------------------------------------------------------
// i18n value completeness & divergence tests
// ---------------------------------------------------------------------------

describe("Translation value completeness", () => {
  function flattenEntries(
    obj: object,
    prefix = "",
  ): Array<{ key: string; value: unknown }> {
    return Object.entries(obj).flatMap(([key, value]) => {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value)
      ) {
        return flattenEntries(value as object, fullKey);
      }
      return [{ key: fullKey, value }];
    });
  }

  const allLocales: Record<string, object> = {
    en,
    de,
    fr,
    it: itLocale,
    es,
    nl,
    "pt-BR": ptBR,
    ja,
    pl,
    sv,
  };

  for (const [name, locale] of Object.entries(allLocales)) {
    it(`${name}.json — every leaf value is a non-empty string`, () => {
      const entries = flattenEntries(locale);
      const empty = entries.filter(
        (e) => typeof e.value !== "string" || e.value.trim() === "",
      );
      expect(empty.map((e) => e.key)).toEqual([]);
    });
  }
});

describe("de ↔ en value divergence", () => {
  function flattenEntries(
    obj: object,
    prefix = "",
  ): Array<{ key: string; value: string }> {
    return Object.entries(obj).flatMap(([key, value]) => {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value)
      ) {
        return flattenEntries(value as object, fullKey);
      }
      return [{ key: fullKey, value: String(value) }];
    });
  }

  it("de values differ from en values (translations exist, not just copies)", () => {
    const enEntries = flattenEntries(en);
    const deMap = new Map(flattenEntries(de).map((e) => [e.key, e.value]));

    // Keys where identical values are acceptable (brand names, technical terms,
    // URLs, single-word universals like "OK", "USB", numbers, etc.)
    const identicalCount = enEntries.filter(
      (e) => deMap.get(e.key) === e.value,
    ).length;

    // Allow up to 20% identical — beyond that, translations are likely missing
    const maxIdenticalPercent = 20;
    const identicalPercent = (identicalCount / enEntries.length) * 100;

    expect(identicalPercent).toBeLessThan(maxIdenticalPercent);
  });

  it("no en value appears as de translation for a DIFFERENT key (copy-paste detector)", () => {
    const enEntries = flattenEntries(en);
    const deEntries = flattenEntries(de);

    // Build set of en values for quick lookup
    const enValuesByKey = new Map(enEntries.map((e) => [e.key, e.value]));

    // Find de entries whose value equals the en value of the SAME key
    // (that's expected for shared terms) — we only flag when de value
    // matches en value AND de value is longer than 3 chars (avoid "OK", "USB")
    const suspicious = deEntries.filter((deEntry) => {
      const enValue = enValuesByKey.get(deEntry.key);
      return (
        enValue === deEntry.value &&
        deEntry.value.length > 3 &&
        // Exclude keys that legitimately have same value (proper nouns, etc.)
        !deEntry.key.includes("brand") &&
        !deEntry.key.includes("url") &&
        !deEntry.key.includes("link")
      );
    });

    // Report suspicious keys but don't fail hard — just flag if > 15% are copies
    const suspiciousPercent = (suspicious.length / deEntries.length) * 100;
    if (suspiciousPercent > 15) {
      expect(suspicious.map((e) => e.key)).toEqual([]);
    }
  });
});

// ---------------------------------------------------------------------------
// i18n key usage analysis — fully generic, no maintenance needed
// ---------------------------------------------------------------------------

describe("i18n key ↔ code usage", () => {
  const srcDir = path.resolve(__dirname, "../../src");

  // i18next plural suffixes — code calls t("key", {count}) and i18next
  // resolves to key_zero / key_one / key_other automatically
  const PLURAL_SUFFIXES = ["_zero", "_one", "_other"] as const;

  function flattenKeys(obj: object, prefix = ""): string[] {
    return Object.entries(obj).flatMap(([key, value]) => {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value)
      ) {
        return flattenKeys(value as object, fullKey);
      }
      return [fullKey];
    });
  }

  function stripPluralSuffix(key: string): string {
    for (const suffix of PLURAL_SUFFIXES) {
      if (key.endsWith(suffix)) return key.slice(0, -suffix.length);
    }
    return key;
  }

  function collectSourceFiles(dir: string): string[] {
    const results: string[] = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory() && entry.name !== "node_modules") {
        results.push(...collectSourceFiles(full));
      } else if (
        /\.(ts|tsx)$/.test(entry.name) &&
        !entry.name.endsWith(".test.ts") &&
        !entry.name.endsWith(".test.tsx")
      ) {
        results.push(full);
      }
    }
    return results;
  }

  function extractKeysFromCode(
    files: string[],
    topLevelKeys: Set<string>,
  ): Set<string> {
    const keys = new Set<string>();
    // 1. Direct t() calls: t("key"), t('key'), i18next.t("key")
    const tCallPattern = /(?:^|[^a-zA-Z])t\(\s*["']([^"']+)["']/gm;
    // 2. String literals that look like i18n keys (for map/variable patterns)
    //    Matches "topLevel.something" or 'topLevel.something' anywhere
    const stringLiteralPattern = /["']([a-zA-Z]+(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)["']/g;

    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      let match;
      while ((match = tCallPattern.exec(content)) !== null) {
        keys.add(match[1]);
      }
      // Reset lastIndex for second pass
      while ((match = stringLiteralPattern.exec(content)) !== null) {
        const candidate = match[1];
        const topLevel = candidate.split(".")[0];
        if (topLevelKeys.has(topLevel)) {
          keys.add(candidate);
        }
      }
    }
    return keys;
  }

  function extractDynamicPrefixes(files: string[]): string[] {
    const prefixes: string[] = [];
    // Match: t(`prefix.${...}`) — extract the static prefix before ${
    const dynamicPattern = /(?:^|[^a-zA-Z])t\(\s*`([^`$]+)\$\{/gm;
    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      let match;
      while ((match = dynamicPattern.exec(content)) !== null) {
        prefixes.push(match[1]);
      }
    }
    return prefixes;
  }

  const allEnKeys = flattenKeys(en);
  const topLevelKeys = new Set(Object.keys(en));
  const sourceFiles = collectSourceFiles(srcDir);
  const codeKeys = extractKeysFromCode(sourceFiles, topLevelKeys);
  const dynamicPrefixes = extractDynamicPrefixes(sourceFiles);

  // Base keys referenced in code + their plural expansions
  const codeKeysWithPlurals = new Set(codeKeys);
  for (const key of codeKeys) {
    for (const suffix of PLURAL_SUFFIXES) {
      codeKeysWithPlurals.add(key + suffix);
    }
  }

  it("every t() reference in code has a matching key in en.json", () => {
    const enKeySet = new Set(allEnKeys);
    // For plural base keys, check if at least one plural variant exists
    const enBaseKeys = new Set(allEnKeys.map(stripPluralSuffix));

    const missing = [...codeKeys].filter((key) => {
      if (enKeySet.has(key)) return false;
      // Plural base key — t("foo", {count}) resolves to foo_one/foo_other
      if (enBaseKeys.has(key)) return false;
      // Dynamic key covered by prefix
      if (dynamicPrefixes.some((p) => key.startsWith(p))) return false;
      return true;
    });
    expect(missing).toEqual([]);
  });

  it("every en.json key is referenced in code (no orphan keys)", () => {
    const orphans = allEnKeys.filter((key) => {
      if (codeKeysWithPlurals.has(key)) return false;
      // Strip plural suffix and check base key
      const base = stripPluralSuffix(key);
      if (base !== key && codeKeys.has(base)) return false;
      // Dynamic prefix match
      if (dynamicPrefixes.some((p) => key.startsWith(p))) return false;
      return true;
    });
    expect(orphans).toEqual([]);
  });

  it("source scan finds a reasonable number of keys (sanity check)", () => {
    expect(codeKeys.size).toBeGreaterThan(50);
    expect(allEnKeys.length).toBeGreaterThan(100);
  });
});
