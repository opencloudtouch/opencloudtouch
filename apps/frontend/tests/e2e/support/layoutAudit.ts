/**
 * Layout audit helper: detects responsive-layout defects in the live DOM.
 *
 * Reported issue kinds:
 *  - page-overflow:    document is wider than the viewport (horizontal scrollbar)
 *  - edge-overflow:    an element extends beyond the right/left viewport edge
 *  - overlap:          two visible UI elements (buttons, labels, inputs, text) intersect
 *  - text-clipped:     an element hides overflowing content (overflow hidden/clip) without ellipsis
 */

export interface LayoutIssue {
  kind: "page-overflow" | "edge-overflow" | "overlap" | "text-clipped" | "unwanted-scroll";
  selector: string;
  other?: string;
  detail: string;
}

const UI_SELECTOR =
  "button, a, label, input, select, textarea, h1, h2, h3, h4, h5, h6, p, li, img, svg, [role=button], [role=tab]";

const TOLERANCE_PX = 2;

const NO_SCROLL_SELECTOR = ".progress-steps, .progress-tracker, .wizard-step, .device-info-header";

function describe(el: Element): string {
  const id = el.id ? `#${el.id}` : "";
  const cls =
    typeof el.className === "string" && el.className.trim()
      ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".")
      : "";
  const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 24);
  const own = `${el.tagName.toLowerCase()}${id}${cls}${text ? ` "${text}"` : ""}`;
  // Icons carry no text; name their parent so the report is actionable.
  if (el.tagName.toLowerCase() === "svg" && el.parentElement) {
    return `${own} in ${describe(el.parentElement).split(' "')[0]}`;
  }
  return own;
}

function isVisible(el: Element, win: Window): DOMRect | null {
  const style = win.getComputedStyle(el);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    parseFloat(style.opacity) === 0
  ) {
    return null;
  }
  // The card that is fading out during a device switch is inert and hidden from assistive technology: not part of the UI.
  if (el.closest("[inert]")) return null;
  // Content of a closed <details> (except its <summary>) is not rendered.
  const details = el.closest("details:not([open])");
  if (details && !el.closest("summary")) return null;
  const rect = el.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return null;
  // Visually hidden text for screen readers (1x1px, clipped) is intentional, not a layout defect.
  if (rect.width <= 1 && rect.height <= 1) return null;
  return rect;
}

/**
 * Resolves once the positions of headings/buttons/links have not changed for ~10 frames, i.e. route
 * and slide-in animations (framer-motion) are finished. Looping animations (spinners, the pulsing
 * logo, progress rings) are excluded. Gives up after `timeoutMs` so a never-settling page still
 * gets audited instead of hanging the test.
 */
export function waitForStableLayout(win: Window, timeoutMs = 4000): Promise<void> {
  const doc = win.document;
  const signature = (): string =>
    Array.from(doc.querySelectorAll("h1, h2, h3, button, a, input, select"))
      .filter((el) => !el.closest(".empty-state-icon, .spinner, .spinner-small, .spinner-large"))
      .map((el) => {
        const r = el.getBoundingClientRect();
        return `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)}`;
      })
      .join("|");

  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;
    let last = "";
    let stableFrames = 0;
    const tick = () => {
      const now = signature();
      stableFrames = now === last ? stableFrames + 1 : 0;
      last = now;
      if (stableFrames >= 10 || Date.now() > deadline) {
        resolve();
      } else {
        win.requestAnimationFrame(tick);
      }
    };
    tick();
  });
}

/** Runs inside the application window; returns all detected issues. */
export function collectLayoutIssues(win: Window): LayoutIssue[] {
  const doc = win.document;
  const issues: LayoutIssue[] = [];
  const vw = doc.documentElement.clientWidth;

  if (doc.documentElement.scrollWidth > vw + TOLERANCE_PX) {
    issues.push({
      kind: "page-overflow",
      selector: "document",
      detail: `scrollWidth ${doc.documentElement.scrollWidth} > viewport ${vw}`,
    });
  }

  const all = Array.from(doc.querySelectorAll(UI_SELECTOR));
  // Containers that must fit their content: a scrollbar here (e.g. a tracker with 8 steps) is a defect,
  // even though the content inside is "reachable" by scrolling.
  for (const el of Array.from(doc.querySelectorAll(NO_SCROLL_SELECTOR))) {
    if (!isVisible(el, win)) continue;
    // Only a scrollable container (auto/scroll) shows a scrollbar; overflowing `visible` content is caught
    // by the edge-overflow check, and transient transform animations must not count.
    if (!/(auto|scroll)/.test(win.getComputedStyle(el).overflowX)) continue;
    if (el.scrollWidth > el.clientWidth + TOLERANCE_PX) {
      issues.push({
        kind: "unwanted-scroll",
        selector: describe(el),
        detail: `scrollWidth ${el.scrollWidth} > clientWidth ${el.clientWidth}`,
      });
    }
  }

  type Box = { left: number; right: number; top: number; bottom: number };

  /** The part of `rect` that is actually painted: intersected with every clipping ancestor. */
  const clippedBox = (el: Element, rect: DOMRect): Box | null => {
    let box: Box = { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
    for (let p = el.parentElement; p && p !== doc.body; p = p.parentElement) {
      const s = win.getComputedStyle(p);
      if (s.overflowX === "visible" && s.overflowY === "visible") continue;
      const pr = p.getBoundingClientRect();
      box = {
        left: Math.max(box.left, pr.left),
        right: Math.min(box.right, pr.right),
        top: Math.max(box.top, pr.top),
        bottom: Math.min(box.bottom, pr.bottom),
      };
      if (box.right <= box.left || box.bottom <= box.top) return null;
    }
    return box;
  };

  const visible: { el: Element; rect: DOMRect; box: Box | null }[] = [];
  for (const el of all) {
    const rect = isVisible(el, win);
    if (rect) visible.push({ el, rect, box: clippedBox(el, rect) });
  }

  // Elements positioned off-screen by an ancestor scroller (carousels etc.) are not defects.
  const inScroller = (el: Element): boolean => {
    for (let p = el.parentElement; p && p !== doc.body; p = p.parentElement) {
      const s = win.getComputedStyle(p);
      if (/(auto|scroll)/.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1) {
        return true;
      }
    }
    return false;
  };

  const isPinned = (el: Element): boolean => {
    for (let p: Element | null = el; p && p !== doc.body; p = p.parentElement) {
      const position = win.getComputedStyle(p).position;
      if (position === "fixed" || position === "sticky") return true;
    }
    return false;
  };

  for (const { el, rect } of visible) {
    if (rect.right > vw + TOLERANCE_PX || rect.left < -TOLERANCE_PX) {
      if (!inScroller(el)) {
        issues.push({
          kind: "edge-overflow",
          selector: describe(el),
          detail: `left ${Math.round(rect.left)}, right ${Math.round(rect.right)} (viewport ${vw})`,
        });
      }
    }

    const s = win.getComputedStyle(el);
    const clips = /(hidden|clip)/.test(s.overflowX) && el.scrollWidth > el.clientWidth + 1;
    // Form fields scroll their own text; <svg> has no text flow.
    const isField = /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName);
    if (clips && !isField && s.textOverflow !== "ellipsis" && el.tagName.toLowerCase() !== "svg") {
      issues.push({
        kind: "text-clipped",
        selector: describe(el),
        detail: `scrollWidth ${el.scrollWidth} > clientWidth ${el.clientWidth}`,
      });
    }
  }

  // Overlap: only compare elements that are not nested in each other.
  const leaves = visible.filter(
    ({ el }) => !visible.some((o) => o.el !== el && el.contains(o.el)),
  );
  for (let i = 0; i < leaves.length; i++) {
    for (let j = i + 1; j < leaves.length; j++) {
      const a = leaves[i];
      const b = leaves[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      // A pinned (fixed/sticky) bar such as the navigation overlays scrolled content by design.
      if (isPinned(a.el) !== isPinned(b.el)) continue;
      // An icon drawn over an image (e.g. the play button over the cover art) is intentional.
      const tags = [a.el.tagName.toLowerCase(), b.el.tagName.toLowerCase()].sort();
      if (tags[0] === "img" && tags[1] === "svg") continue;
      // A decorative icon (aria-hidden) drawn inside a form field, e.g. the chevron of a custom select, is intentional.
      const field = /^(input|select|textarea)$/.test(a.el.tagName.toLowerCase()) ? a.el : /^(input|select|textarea)$/.test(b.el.tagName.toLowerCase()) ? b.el : null;
      const icon = field === a.el ? b.el : a.el;
      if (field && icon.tagName.toLowerCase() === "svg" && icon.closest('[aria-hidden="true"]')) continue;
      // Parts hidden by a scrolling/clipping ancestor (e.g. content scrolled under the nav) do not count.
      if (!a.box || !b.box) continue;
      const w = Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
      const h = Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
      if (w > TOLERANCE_PX && h > TOLERANCE_PX) {
        issues.push({
          kind: "overlap",
          selector: describe(a.el),
          other: describe(b.el),
          detail: `intersection ${Math.round(w)}x${Math.round(h)}px`,
        });
      }
    }
  }

  return issues;
}

/**
 * Retries until no finite CSS/JS animation has been running for a quiet period, so axe measures
 * contrast on settled colours. The quiet period covers animations that start right after render.
 */
export function waitForSettledAnimations(quietMs = 300) {
  let lastBusy = Date.now();
  cy.window().should((win) => {
    const busy = win.document
      .getAnimations()
      .some((a) => a.playState !== "finished" && a.effect?.getComputedTiming().iterations !== Infinity);
    if (busy) lastBusy = Date.now();
    expect(Date.now() - lastBusy, "ms since the last running animation").to.be.at.least(quietMs);
  });
}
