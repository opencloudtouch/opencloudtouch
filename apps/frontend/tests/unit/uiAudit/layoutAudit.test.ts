import { describe, it, expect, beforeEach } from "vitest";
import { collectLayoutIssues } from "../../e2e/support/layoutAudit";

// jsdom has no layout: every box and the viewport are stubbed explicitly.
const box = (left: number, top: number, width: number, height: number) =>
  ({
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
    toJSON: () => ({}),
  }) as DOMRect;

function place(el: Element, rect: DOMRect) {
  el.getBoundingClientRect = () => rect;
}

function setViewport(width: number, scrollWidth = width) {
  Object.defineProperty(document.documentElement, "clientWidth", {
    value: width,
    configurable: true,
  });
  Object.defineProperty(document.documentElement, "scrollWidth", {
    value: scrollWidth,
    configurable: true,
  });
}

describe("collectLayoutIssues", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    setViewport(320);
  });

  it("finds nothing in a tidy layout", () => {
    document.body.innerHTML = `<button id="a">One</button><button id="b">Two</button>`;
    place(document.getElementById("a")!, box(10, 10, 100, 44));
    place(document.getElementById("b")!, box(120, 10, 100, 44));
    expect(collectLayoutIssues(window)).toEqual([]);
  });

  it("reports a page that is wider than the viewport", () => {
    setViewport(320, 400);
    const issues = collectLayoutIssues(window);
    expect(issues.map((i) => i.kind)).toContain("page-overflow");
  });

  it("reports an element that pokes out of the right edge", () => {
    document.body.innerHTML = `<p id="label">Einstellungen</p>`;
    place(document.getElementById("label")!, box(250, 10, 80, 20));
    const issues = collectLayoutIssues(window);
    expect(issues).toHaveLength(1);
    expect(issues[0]?.kind).toBe("edge-overflow");
    expect(issues[0]?.selector).toContain("Einstellungen");
  });

  it("tolerates a 2px rounding difference", () => {
    document.body.innerHTML = `<button id="a">One</button>`;
    place(document.getElementById("a")!, box(240, 10, 81, 44));
    expect(collectLayoutIssues(window)).toEqual([]);
  });

  it("reports two buttons that overlap", () => {
    document.body.innerHTML = `<button id="a">One</button><button id="b">Two</button>`;
    place(document.getElementById("a")!, box(10, 10, 100, 44));
    place(document.getElementById("b")!, box(60, 10, 100, 44));
    const issues = collectLayoutIssues(window);
    expect(issues).toHaveLength(1);
    expect(issues[0]?.kind).toBe("overlap");
    expect(issues[0]?.detail).toBe("intersection 50x44px");
  });

  it("ignores hidden elements", () => {
    document.body.innerHTML = `<button id="a">One</button><button id="b" style="display: none">Two</button>`;
    place(document.getElementById("a")!, box(10, 10, 100, 44));
    place(document.getElementById("b")!, box(60, 10, 100, 44));
    expect(collectLayoutIssues(window)).toEqual([]);
  });
});
