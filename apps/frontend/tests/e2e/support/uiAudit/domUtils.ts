/** Small DOM helpers shared by the in-page audit collectors. */

export function describeElement(el: Element): string {
  const cls =
    typeof el.className === "string" && el.className.trim()
      ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".")
      : "";
  const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 24);
  return `${el.tagName.toLowerCase()}${cls}${text ? ` "${text}"` : ""}`;
}

/** True when the element itself (not only a descendant) holds visible text. */
export const hasOwnText = (el: Element): boolean =>
  Array.from(el.childNodes).some((n) => n.nodeType === 3 && (n.textContent ?? "").trim() !== "");

/** Rendered: no display:none on the element or an ancestor, not visibility:hidden, and a real box. */
export function isRendered(el: Element, win: Window, requireLayout = true): boolean {
  if (win.getComputedStyle(el).visibility === "hidden") return false;
  for (let n: Element | null = el; n; n = n.parentElement) {
    if (win.getComputedStyle(n).display === "none") return false;
  }
  if (!requireLayout) return true;
  const rects = el.getClientRects();
  // a 1px box is visually hidden text for screen readers
  const first = rects[0];
  return first !== undefined && !(first.width <= 1 && first.height <= 1);
}
