/** In-page contrast measurement: runs inside the application window (Cypress) or jsdom (unit tests). */
import { evaluateContrast, parseCssColor, type Rgba } from "./contrast";
import { describeElement, hasOwnText } from "./domUtils";

export interface ContrastIssue {
  kind: "contrast" | "contrast-unverified";
  selector: string;
  detail: string;
}

export interface ContrastOptions {
  /** Skip elements without a rendered box. Off in jsdom, which has no layout. */
  requireLayout?: boolean;
}

const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "TEMPLATE"]);
const WHITE: Rgba = { r: 255, g: 255, b: 255, a: 1 };

const fontWeight = (value: string) => {
  if (value === "bold") return 700;
  if (value === "normal" || !value) return 400;
  return parseInt(value, 10) || 400;
};

export function collectContrastIssues(win: Window, options: ContrastOptions = {}): ContrastIssue[] {
  const { requireLayout = true } = options;
  const doc = win.document;
  const issues: ContrastIssue[] = [];
  const pageBg = parseCssColor(win.getComputedStyle(doc.documentElement).backgroundColor);
  const page = pageBg && pageBg.a === 1 ? pageBg : WHITE;

  for (const el of Array.from(doc.body.querySelectorAll("*"))) {
    if (SKIP_TAGS.has(el.tagName.toUpperCase()) || !hasOwnText(el)) continue;
    if (el.closest("svg, [inert], :disabled, fieldset:disabled")) continue;

    const style = win.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") continue;
    if (requireLayout) {
      const rects = el.getClientRects();
      const first = rects[0];
      if (!first) continue;
      // visually hidden text for screen readers (1px box) is not read by sighted users
      if (first.width <= 1 && first.height <= 1) continue;
    }

    // Walk outwards: backgrounds, opacity, and anything that makes the result unmeasurable.
    const layers: Rgba[] = [];
    let opacity = 1;
    let hidden = false;
    let unverified: string | null = null;
    let opaqueFound = false;
    for (let n: Element | null = el; n; n = n.parentElement) {
      const s = win.getComputedStyle(n);
      if (s.display === "none") hidden = true;
      opacity *= s.opacity === "" ? 1 : parseFloat(s.opacity);
      if (!opaqueFound) {
        if (s.backgroundImage && s.backgroundImage !== "none") {
          unverified ??= "background image or gradient behind the text";
        }
        const bg = parseCssColor(s.backgroundColor);
        if (bg && bg.a > 0) {
          layers.push(bg);
          if (bg.a === 1) opaqueFound = true;
        }
      }
    }
    if (hidden || opacity === 0) continue;

    const fill = style.getPropertyValue("-webkit-text-fill-color");
    const fillColor = fill ? parseCssColor(fill) : null;
    if (fillColor && fillColor.a === 0) unverified ??= "text fill is transparent (gradient text)";

    const color = parseCssColor(style.color);
    if (!color) unverified ??= `cannot resolve text colour "${style.color}"`;

    if (unverified || !color) {
      issues.push({
        kind: "contrast-unverified",
        selector: describeElement(el),
        detail: unverified ?? "",
      });
      continue;
    }

    const result = evaluateContrast({
      color,
      backgrounds: layers,
      pageBackground: page,
      fontSizePx: parseFloat(style.fontSize) || 16,
      fontWeight: fontWeight(style.fontWeight),
      opacity,
    });
    if (!result.pass) {
      const rgb = (c: Rgba) => `rgb(${c.r}, ${c.g}, ${c.b})`;
      issues.push({
        kind: "contrast",
        selector: describeElement(el),
        detail: `${result.ratio.toFixed(2)}:1 < ${result.required}:1 (${rgb(result.foreground)} on ${rgb(result.background)})`,
      });
    }
  }
  return issues;
}
