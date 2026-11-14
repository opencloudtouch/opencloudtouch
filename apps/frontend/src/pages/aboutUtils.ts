import { THANK_YOU_PHRASES } from "./thankYouPhrases";

export interface Supporter {
  name: string;
  type: "monthly" | "one-time";
  amount: number;
  monthlyAmount: number;
  firstSupportDate: string;
}

export interface UpdateInfo {
  available: boolean;
  latestVersion?: string;
  releaseUrl?: string;
}

/**
 * Parse a quoted CSV field starting at position i (after opening quote).
 * Returns the parsed value and the new position after the closing quote.
 */
function parseQuotedField(line: string, startPos: number): { value: string; nextPos: number } {
  let value = "";
  let i = startPos;
  const len = line.length;

  while (i < len) {
    if (line[i] === '"') {
      if (i + 1 < len && line[i + 1] === '"') {
        value += '"';
        i += 2;
      } else {
        i++; // skip closing quote
        break;
      }
    } else {
      value += line[i];
      i++;
    }
  }

  // Skip comma after closing quote
  if (i < len && line[i] === ",") i++;

  return { value, nextPos: i };
}

/**
 * Parse an unquoted CSV field starting at position i.
 * Returns the parsed value and the new position.
 */
function parseUnquotedField(line: string, startPos: number): { value: string; nextPos: number } {
  const commaIdx = line.indexOf(",", startPos);
  if (commaIdx === -1) {
    return { value: line.substring(startPos).trim(), nextPos: line.length };
  }
  return { value: line.substring(startPos, commaIdx).trim(), nextPos: commaIdx + 1 };
}

/**
 * RFC 4180-compliant CSV line parser.
 * Handles quoted fields (with commas, quotes inside), unquoted fields, and trims whitespace.
 */
export function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let i = 0;
  const len = line.length;
  let trailingComma = false;

  while (i < len) {
    if (line[i] === '"') {
      const result = parseQuotedField(line, i + 1);
      fields.push(result.value);
      i = result.nextPos;
      trailingComma = i <= len && line[i - 1] === ",";
    } else {
      const result = parseUnquotedField(line, i);
      fields.push(result.value);
      trailingComma =
        result.nextPos <= len && result.nextPos > i && line[result.nextPos - 1] === ",";
      i = result.nextPos;
    }
  }

  // Trailing comma means one more empty field
  if (trailingComma) {
    fields.push("");
  }

  // Empty line = single empty field
  if (fields.length === 0) {
    fields.push("");
  }

  return fields;
}

export function getRandomThankYou(isMonthly: boolean, lang: string): string {
  const currentLang = lang.split("-")[0] ?? "en"; // en-US → en

  const category = isMonthly ? "monthly" : "regular";
  const categoryPhrases = THANK_YOU_PHRASES[category];
  const phrases = categoryPhrases?.[currentLang] ?? categoryPhrases?.["en"] ?? [];

  if (phrases.length === 0) return "Thank you! ☕";
  return phrases[Math.floor(Math.random() * phrases.length)] ?? "Thank you! ☕"; // NOSONAR — non-cryptographic use for UI tooltip randomization
}

export function getFontSize(supporter: Supporter, maxAmount: number): number {
  const totalSupport = supporter.amount + supporter.monthlyAmount;
  const ratio = totalSupport / maxAmount;
  const minSize = 12;
  const maxSize = 32;
  return Math.floor(minSize + (maxSize - minSize) * ratio);
}

export type ThemeName = "dark" | "light";

/**
 * Name colours stay >= 4.8:1 on the card of the theme (4.5 is the requirement, 0.3 margin for rounding).
 * Dark: vivid, lightness is raised per hue (yellows and greens end up lighter than blues).
 * Light: calmer saturation, lightness is lowered per hue (yellow ends up olive).
 * CARD_LUMINANCE must match --surface-card: dark #242424, light #ffffff.
 */
function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [f(0), f(8), f(4)];
}

function luminance([r, g, b]: [number, number, number]): number {
  const c = (v: number) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b);
}

const CARD_LUMINANCE: Record<ThemeName, number> = {
  dark: luminance([36 / 255, 36 / 255, 36 / 255]),
  light: 1,
};
const MIN_RATIO = 4.8;
const contrast = (a: number, b: number) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

export function generateGradientColor(
  index: number,
  total: number,
  theme: ThemeName = "dark"
): string {
  const hue = (index / total) * 360;
  const card = CARD_LUMINANCE[theme];
  const readable = (s: number, l: number) =>
    contrast(luminance(hslToRgb(hue, s / 100, l / 100)), card) >= MIN_RATIO;
  if (theme === "dark") {
    const saturation = 85 + (index % 4) * 5;
    let lightness = 58 + (index % 2) * 4;
    while (lightness < 90 && !readable(saturation, lightness)) lightness += 1;
    return `hsl(${hue.toFixed(1)}, ${saturation}%, ${lightness}%)`;
  }
  const saturation = 70 + (index % 4) * 5;
  let lightness = 46 + (index % 2) * 4;
  while (lightness > 12 && !readable(saturation, lightness)) lightness -= 1;
  return `hsl(${hue.toFixed(1)}, ${saturation}%, ${lightness}%)`;
}

export function cleanName(name: string): string {
  if (name.startsWith("https://github.com/")) {
    return "@" + name.replace("https://github.com/", "");
  }

  const atIndex = name.indexOf("@");
  // Only strip if "@" is present and NOT the very first character
  // (leading "@" denotes a handle, e.g. "@Struppie", and stays untouched)
  if (atIndex > 0) {
    return name.slice(0, atIndex).trim();
  }

  return name;
}
