import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = (file: string) => readFileSync(resolve(__dirname, "../../src", file), "utf-8");

describe("forced colors and narrow screens", () => {
  it("styles the active chip with system colors in forced-colors mode", () => {
    const base = css("ui-base.css");
    const block = base.slice(base.indexOf("@media (forced-colors: active)"));
    expect(block).toMatch(/\.ui-chip\[aria-pressed="true"\]\s*\{[^}]*Highlight/);
    // the check mark is painted with currentColor, which forced colors turn into a white box
    expect(block).toMatch(
      /\.ui-chip\[aria-pressed="true"\]::before\s*\{[^}]*background:\s*HighlightText/
    );
  });

  it("lets the folder hint wrap instead of cutting it off", () => {
    expect(css("components/dlna/DlnaBrowser.css")).toMatch(
      /\.dl-sub--wrap\s*\{[^}]*white-space:\s*normal/
    );
  });
});
