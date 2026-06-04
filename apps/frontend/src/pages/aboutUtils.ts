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
  const currentLang = lang.split("-")[0]; // en-US → en

  const category = isMonthly ? "monthly" : "regular";
  const categoryPhrases = THANK_YOU_PHRASES[category];
  const phrases = categoryPhrases?.[currentLang] ?? categoryPhrases?.["en"] ?? [];

  if (phrases.length === 0) return "Thank you! ☕";
  return phrases[Math.floor(Math.random() * phrases.length)]; // NOSONAR — non-cryptographic use for UI tooltip randomization
}

export function getFontSize(supporter: Supporter, maxAmount: number): number {
  const totalSupport = supporter.amount + supporter.monthlyAmount;
  const ratio = totalSupport / maxAmount;
  const minSize = 12;
  const maxSize = 32;
  return Math.floor(minSize + (maxSize - minSize) * ratio);
}

export function generateGradientColor(index: number, total: number): string {
  const hue = (index / total) * 360;
  const saturation = 60 + (index % 3) * 10;
  const lightness = 55 + (index % 2) * 10;
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

export function cleanName(name: string): string {
  if (name.startsWith("https://github.com/")) {
    return "@" + name.replace("https://github.com/", "");
  }
  return name;
}
