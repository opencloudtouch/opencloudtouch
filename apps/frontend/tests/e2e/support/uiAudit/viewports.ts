/** Viewport matrix for the UI audit: base widths plus both sides of every CSS width breakpoint. */

const UNIT_PX: Record<string, number> = { px: 1, em: 16, rem: 16 };

/** All min-width / max-width thresholds found in CSS text, in px, sorted and unique. */
export function extractBreakpoints(css: string): number[] {
  const found = new Set<number>();
  for (const m of css.matchAll(/\(\s*(?:min|max)-width\s*:\s*([\d.]+)(px|em|rem)\s*\)/g)) {
    const [, value = "0", unit = "px"] = m;
    found.add(Math.round(parseFloat(value) * (UNIT_PX[unit] ?? 1)));
  }
  return [...found].sort((a, b) => a - b);
}

export interface MatrixOptions {
  min: number;
  max: number;
  base: number[];
}

/** Base widths plus threshold-1, threshold and threshold+1 for every breakpoint, within [min, max]. */
export function buildWidthMatrix(
  breakpoints: number[],
  { min, max, base }: MatrixOptions
): number[] {
  const widths = new Set<number>(base);
  for (const bp of breakpoints) for (const w of [bp - 1, bp, bp + 1]) widths.add(w);
  return [...widths].filter((w) => w >= min && w <= max).sort((a, b) => a - b);
}
