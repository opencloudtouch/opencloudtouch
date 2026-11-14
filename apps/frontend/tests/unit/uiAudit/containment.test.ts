import { describe, it, expect, beforeEach } from "vitest";
import { collectContainmentIssues } from "../../e2e/support/uiAudit/containment";

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

const place = (el: Element, rect: DOMRect) => {
  el.getBoundingClientRect = () => rect;
  el.getClientRects = () => [rect] as unknown as DOMRectList;
};
const sizes = (el: Element, scrollWidth: number, clientWidth: number) => {
  Object.defineProperty(el, "scrollWidth", { value: scrollWidth, configurable: true });
  Object.defineProperty(el, "clientWidth", { value: clientWidth, configurable: true });
};

const run = () => collectContainmentIssues(window);
const get = (id: string) => document.getElementById(id)!;

describe("collectContainmentIssues", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("finds nothing when the label sits inside its link", () => {
    document.body.innerHTML = `<a id="link" href="/x"><span id="label">Settings</span></a>`;
    place(get("link"), box(100, 0, 90, 52));
    place(get("label"), box(110, 20, 70, 14));
    expect(run()).toEqual([]);
  });

  it("reports a label that pokes out of its link on the right", () => {
    document.body.innerHTML = `<a id="link" href="/x"><span id="label">Einstellungen</span></a>`;
    place(get("link"), box(100, 0, 60, 52));
    place(get("label"), box(104, 20, 70, 14));
    const issues = run();
    expect(issues).toHaveLength(1);
    expect(issues[0]?.kind).toBe("text-outside-container");
    expect(issues[0]?.selector).toContain("Einstellungen");
    expect(issues[0]?.other).toContain("a");
    expect(issues[0]?.detail).toBe("right edge 14px outside");
  });

  it("reports the left side as well", () => {
    document.body.innerHTML = `<button id="b"><span id="t">Long label</span></button>`;
    place(get("b"), box(100, 0, 60, 44));
    place(get("t"), box(90, 10, 50, 14));
    expect(run()[0]?.detail).toBe("left edge 10px outside");
  });

  it("tolerates one pixel", () => {
    document.body.innerHTML = `<a id="link" href="/x"><span id="label">Ok</span></a>`;
    place(get("link"), box(100, 0, 60, 52));
    place(get("label"), box(101, 20, 60, 14));
    expect(run()).toEqual([]);
  });

  it("reports text that overflows its own box while overflow is visible", () => {
    document.body.innerHTML = `<button id="b">Einstellungen</button>`;
    place(get("b"), box(0, 0, 60, 44));
    sizes(get("b"), 90, 60);
    const issues = run();
    expect(issues).toHaveLength(1);
    expect(issues[0]?.kind).toBe("text-overflows-own-box");
    expect(issues[0]?.detail).toBe("content 90px wide in a 60px box");
  });

  it("does not flag an ellipsis or a scroll container", () => {
    document.body.innerHTML = `<button id="a" style="overflow: hidden; text-overflow: ellipsis">Long</button><div id="s" style="overflow: auto">Scrolls</div>`;
    place(get("a"), box(0, 0, 60, 44));
    place(get("s"), box(0, 50, 60, 44));
    sizes(get("a"), 90, 60);
    sizes(get("s"), 90, 60);
    expect(run()).toEqual([]);
  });

  it("ignores hidden elements", () => {
    document.body.innerHTML = `<a id="link" href="/x"><span id="label" style="display: none">Einstellungen</span></a>`;
    place(get("link"), box(100, 0, 60, 52));
    place(get("label"), box(104, 20, 70, 14));
    expect(run()).toEqual([]);
  });
});
