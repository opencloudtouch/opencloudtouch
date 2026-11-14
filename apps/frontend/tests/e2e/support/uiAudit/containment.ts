/**
 * In-page containment check: text that pokes out of the control it belongs to (a nav label past the
 * edge of its link) or overflows its own box. The generic layout audit does not see this, because
 * the text is still inside the viewport and overlaps nothing.
 */
import { describeElement, hasOwnText, isRendered } from "./domUtils";

export interface ContainmentIssue {
  kind: "text-outside-container" | "text-overflows-own-box";
  selector: string;
  other?: string;
  detail: string;
}

const TOLERANCE_PX = 1;
/** jsdom leaves overflow-x empty; fall back to the shorthand. Empty means visible. */
const clips = (style: CSSStyleDeclaration) => {
  const value = style.overflowX || style.overflow;
  return value !== "" && value !== "visible";
};
const CONTROL = "a, button, [role='button'], [role='tab'], [role='option']";

export function collectContainmentIssues(win: Window): ContainmentIssue[] {
  const issues: ContainmentIssue[] = [];
  for (const el of Array.from(win.document.body.querySelectorAll("*"))) {
    if (!hasOwnText(el) || !isRendered(el, win)) continue;
    const style = win.getComputedStyle(el);

    // 1. content wider than the element's own box, with nothing clipping or scrolling it
    if (
      !clips(style) &&
      style.display !== "inline" &&
      el.clientWidth > 0 &&
      el.scrollWidth > el.clientWidth + TOLERANCE_PX
    ) {
      issues.push({
        kind: "text-overflows-own-box",
        selector: describeElement(el),
        detail: `content ${el.scrollWidth}px wide in a ${el.clientWidth}px box`,
      });
    }

    // 2. text box beyond the box of its link or button, unless something in between clips it
    const control = el.parentElement?.closest(CONTROL);
    if (!control) continue;
    let clipped = false;
    for (let n: Element | null = el; n; n = n.parentElement) {
      if (clips(win.getComputedStyle(n))) clipped = true;
      if (n === control) break;
    }
    if (clipped) continue;
    const text = el.getBoundingClientRect();
    const frame = control.getBoundingClientRect();
    const right = Math.round(text.right - frame.right);
    const left = Math.round(frame.left - text.left);
    if (right > TOLERANCE_PX || left > TOLERANCE_PX) {
      issues.push({
        kind: "text-outside-container",
        selector: describeElement(el),
        other: describeElement(control),
        detail:
          right > TOLERANCE_PX ? `right edge ${right}px outside` : `left edge ${left}px outside`,
      });
    }
  }
  return issues;
}
