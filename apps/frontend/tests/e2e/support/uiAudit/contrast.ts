/** Pure colour maths for the UI audit: parsing, compositing and WCAG 2.1 contrast. */

export interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

function parseAlpha(token: string | undefined): number | null {
  if (token === undefined) return 1;
  const value = token.endsWith("%") ? parseFloat(token) / 100 : parseFloat(token);
  return Number.isFinite(value) ? clamp01(value) : null;
}

/** Resolves the colour strings getComputedStyle() returns (plus hex, for convenience); null if unknown. */
export function parseCssColor(input: string): Rgba | null {
  const text = input.trim().toLowerCase();
  if (!text) return null;
  if (text === "transparent") return { r: 0, g: 0, b: 0, a: 0 };

  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/.exec(text);
  if (hex) {
    let digits = hex[1] ?? "";
    if (digits.length === 3) digits = [...digits].map((c) => c + c).join("");
    const byte = (i: number) => parseInt(digits.slice(i, i + 2), 16);
    return { r: byte(0), g: byte(2), b: byte(4), a: digits.length === 8 ? byte(6) / 255 : 1 };
  }

  const rgb = /^rgba?\(\s*([^)]+)\)$/.exec(text);
  if (rgb) {
    const parts = (rgb[1] ?? "").split(/[\s,/]+/).filter(Boolean);
    if (parts.length < 3 || parts.length > 4 || parts.slice(0, 3).some((p) => p.endsWith("%"))) {
      return null;
    }
    const [r = NaN, g = NaN, b = NaN] = parts.slice(0, 3).map(Number);
    const a = parseAlpha(parts[3]);
    if (![r, g, b].every(Number.isFinite) || a === null) return null;
    return { r, g, b, a };
  }

  const srgb = /^color\(\s*srgb\s+([^)]+)\)$/.exec(text);
  if (srgb) {
    const parts = (srgb[1] ?? "").split(/[\s/]+/).filter(Boolean);
    if (parts.length < 3 || parts.length > 4) return null;
    const [r = NaN, g = NaN, b = NaN] = parts
      .slice(0, 3)
      .map((p) => Math.round(clamp01(parseFloat(p)) * 255));
    const a = parseAlpha(parts[3]);
    if (![r, g, b].every(Number.isFinite) || a === null) return null;
    return { r, g, b, a };
  }
  return null;
}

/** `top` drawn over an opaque `bottom`; the result is opaque. */
export function compositeOver(top: Rgba, bottom: Rgba): Rgba {
  const mix = (t: number, b: number) => Math.round(t * top.a + b * (1 - top.a));
  return { r: mix(top.r, bottom.r), g: mix(top.g, bottom.g), b: mix(top.b, bottom.b), a: 1 };
}

export function relativeLuminance({ r, g, b }: Rgba): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrastRatio(a: Rgba, b: Rgba): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** WCAG 1.4.3: large text (24px, or 18.66px and bold) needs 3:1, everything else 4.5:1. */
export function requiredRatio(fontSizePx: number, fontWeight: number): number {
  const large = fontSizePx >= 24 || (fontSizePx >= 18.66 && fontWeight >= 700);
  return large ? 3 : 4.5;
}

/** Collapses background layers (innermost first) into one opaque colour over the page colour. */
export function flattenLayers(layers: Rgba[], pageBackground: Rgba): Rgba {
  return layers.reduceRight((below, layer) => compositeOver(layer, below), pageBackground);
}

export interface ContrastInput {
  color: Rgba;
  /** Background layers from the text element outwards. */
  backgrounds: Rgba[];
  pageBackground: Rgba;
  fontSizePx: number;
  fontWeight: number;
  /** Product of the element's and its ancestors' opacity. */
  opacity?: number;
}

export interface ContrastResult {
  ratio: number;
  required: number;
  pass: boolean;
  foreground: Rgba;
  background: Rgba;
}

export function evaluateContrast(input: ContrastInput): ContrastResult {
  const background = flattenLayers(input.backgrounds, input.pageBackground);
  const alpha = input.color.a * (input.opacity ?? 1);
  const foreground = compositeOver({ ...input.color, a: alpha }, background);
  const ratio = contrastRatio(foreground, background);
  const required = requiredRatio(input.fontSizePx, input.fontWeight);
  return { ratio, required, pass: ratio >= required, foreground, background };
}
