import { describe, it, expect, beforeEach } from "vitest";
import { collectContrastIssues } from "../../e2e/support/uiAudit/contrastDom";

// jsdom has no layout, so the collector is told not to require a rendered box.
const run = () => collectContrastIssues(window, { requireLayout: false });

describe("collectContrastIssues", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    document.body.style.backgroundColor = "rgb(255, 255, 255)";
    document.body.style.color = "rgb(0, 0, 0)";
  });

  it("reports nothing for readable text", () => {
    document.body.innerHTML = `<p style="color: rgb(20, 23, 28)">Hello</p>`;
    expect(run()).toEqual([]);
  });

  it("reports pale text on white with the measured ratio", () => {
    document.body.innerHTML = `<p class="pale" style="color: rgb(200, 200, 200)">Hello</p>`;
    const issues = run();
    expect(issues).toHaveLength(1);
    expect(issues[0]?.kind).toBe("contrast");
    expect(issues[0]?.selector).toContain("p.pale");
    expect(issues[0]?.detail).toMatch(/1\.\d+:1 < 4\.5:1/);
  });

  it("uses the nearest opaque ancestor background", () => {
    document.body.innerHTML = `<div style="background-color: rgb(0, 0, 0)"><p style="color: rgb(255, 255, 255)">Hi</p></div>`;
    expect(run()).toEqual([]);
    document.body.innerHTML = `<div style="background-color: rgb(0, 0, 0)"><p style="color: rgb(20, 20, 20)">Hi</p></div>`;
    expect(run()).toHaveLength(1);
  });

  it("composites a translucent background over what is behind it", () => {
    document.body.innerHTML = `<div style="background-color: rgba(0, 0, 0, 0.9)"><p style="color: rgb(255, 255, 255)">Hi</p></div>`;
    expect(run()).toEqual([]);
  });

  it("accepts the lower threshold for large text", () => {
    document.body.innerHTML = `<p style="color: rgb(140, 140, 140); font-size: 24px">Big</p>`;
    expect(run()).toEqual([]);
    document.body.innerHTML = `<p style="color: rgb(140, 140, 140); font-size: 16px">Small</p>`;
    expect(run()).toHaveLength(1);
  });

  it("applies element opacity", () => {
    document.body.innerHTML = `<p style="color: rgb(0, 0, 0); opacity: 0.3">Faded</p>`;
    expect(run()).toHaveLength(1);
  });

  it("skips hidden elements and elements without their own text", () => {
    document.body.innerHTML = `
      <p style="color: rgb(220, 220, 220); display: none">Hidden</p>
      <p style="color: rgb(220, 220, 220); visibility: hidden">Hidden</p>
      <div style="color: rgb(220, 220, 220)"><span></span></div>
      <p style="color: rgb(220, 220, 220)">   </p>`;
    expect(run()).toEqual([]);
  });

  it("marks text it cannot measure instead of guessing", () => {
    document.body.innerHTML = `<div style="background-image: linear-gradient(red, blue)"><p style="color: rgb(0, 0, 0)">On gradient</p></div>`;
    const issues = run();
    expect(issues).toHaveLength(1);
    expect(issues[0]?.kind).toBe("contrast-unverified");
    document.body.innerHTML = `<p style="color: rgb(0, 0, 0); -webkit-text-fill-color: transparent">Clipped</p>`;
    expect(run()[0]?.kind).toBe("contrast-unverified");
  });

  it("skips disabled controls, as WCAG does", () => {
    document.body.innerHTML = `<button disabled style="color: rgb(210, 210, 210)">Off</button>`;
    expect(run()).toEqual([]);
  });
});
