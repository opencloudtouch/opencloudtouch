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
 * RFC 4180-compliant CSV line parser.
 * Handles quoted fields (with commas, quotes inside), unquoted fields, and trims whitespace.
 */
export function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let i = 0;
  const len = line.length;

  while (i <= len) {
    if (i === len) {
      fields.push("");
      break;
    }

    if (line[i] === '"') {
      // Quoted field
      let value = "";
      i++; // skip opening quote
      while (i < len) {
        if (line[i] === '"') {
          if (i + 1 < len && line[i + 1] === '"') {
            // Escaped quote
            value += '"';
            i += 2;
          } else {
            // Closing quote
            i++; // skip closing quote
            break;
          }
        } else {
          value += line[i];
          i++;
        }
      }
      fields.push(value);
      // Skip comma after closing quote
      if (i < len && line[i] === ",") i++;
    } else {
      // Unquoted field
      const commaIdx = line.indexOf(",", i);
      if (commaIdx === -1) {
        fields.push(line.substring(i).trim());
        break;
      } else {
        fields.push(line.substring(i, commaIdx).trim());
        i = commaIdx + 1;
      }
    }
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
