/**
 * Regression test (final browser audit F2): component CSS must use design tokens, not hard-coded colours.
 */
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const read = (rel: string) => readFileSync(resolve(__dirname, "../../src", rel), "utf-8");

describe("design tokens in component CSS", () => {
  it("VolumeSlider uses no hard-coded hex colours (F2)", () => {
    const css = read("components/VolumeSlider.css").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it("VolumeSlider.tsx sets no hard-coded colours inline (F2)", () => {
    const tsx = read("components/VolumeSlider.tsx").replace(/\/\/.*$/gm, "");
    expect(tsx.match(/"#[0-9a-fA-F]{3,8}"/g) ?? []).toEqual([]);
  });

  it("Licenses rows keep a 44px touch target on phones (F3)", () => {
    const css = read("pages/Licenses.css");
    expect(css).toMatch(/@media \(max-width: 599px\)[\s\S]*\.lic-name::after[\s\S]*inset: 0/);
    expect(css).toMatch(/\.lic-link[\s\S]*min-height: var\(--touch-target-min\)/);
  });

  it("the wizard banner is the same box as .wz-status and uses tokens (found by the colour and spacing measurement)", () => {
    const base = read("components/wizard/wizard-base.css");
    const banner = base.slice(base.indexOf(".wizard-warning {"), base.indexOf(".wizard-warning-text"));
    expect(banner).toMatch(/padding: 14px var\(--space-md\)/);
    expect(banner).toMatch(/border-radius: var\(--border-radius-md\)/);
    expect(banner).toMatch(/color: var\(--warning-color\)/);
    expect(banner).not.toMatch(/#ffc107/i);
    const step8 = read("components/wizard/Step8Verification.css");
    expect(step8).not.toMatch(/33, 150, 243|#64b5f6/i); // Material blue is not part of the palette
  });

  it("vertical rhythm: Zones and the wizard use the same 24px gaps and title offset as the other pages", () => {
    expect(read("pages/MultiRoom.css")).toMatch(/@media \(min-width: 769px\)[\s\S]*?\.mr \{[^}]*gap: var\(--space-lg\)/);
    expect(read("components/wizard/wizard-base.css")).toMatch(
      /@media \(min-width: 769px\)[\s\S]*?\.setup-wizard-page \{[^}]*padding-top: var\(--space-lg\)/
    );
  });

  it("every focused element gets the light-blue focus ring token, not the old #0066cc accent (found by the state measurement)", () => {
    expect(read("index.css")).toMatch(/\*:focus-visible \{[^}]*outline: 2px solid var\(--focus-ring/);
  });

  it("wizard inputs share the focus border and use the danger token for invalid values", () => {
    const base = read("components/wizard/wizard-base.css");
    expect(base).toMatch(/\.hosts-input:focus,\s*\.ntp-input:focus \{[^}]*border-color: var\(--primary-color\)/);
    expect(base).not.toMatch(/#f44336/i);
    expect(read("components/wizard/Step5ConfigModification.css")).not.toMatch(/#f44336/i);
  });

  it("the 404 title uses the page title size token", () => {
    expect(read("pages/NotFound.css")).toMatch(/\.nf-title \{[^}]*font-size: var\(--fs-h1\)/);
  });

  it("the menu has the same side padding as the pages from 769px", () => {
    expect(read("components/Navigation.css")).toMatch(
      /@media \(min-width: 769px\)[\s\S]*\.nav-inner[\s\S]*padding-inline: var\(--space-lg\)/
    );
  });
});

describe("font sizes come from the token scale", () => {
  it("no component CSS uses a literal px size that has a token (12, 13, 14, 15, 16, 17, 18, 20, 24, 26)", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const { join, relative } = await import("node:path");
    const root = resolve(__dirname, "../../src");
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) walk(full);
        else if (name.endsWith(".css")) files.push(full);
      }
    };
    walk(root);
    const offenders = files
      .filter((f) => /font-size:\s*(12|13|14|15|16|17|18|20|24|26)px/.test(readFileSync(f, "utf-8")))
      .map((f) => relative(root, f));
    expect(offenders, "use var(--fs-xs|small|md|body|lg|h3|xl|h2|2xl|h1)").toEqual([]);
  });
});

describe("every font-size token that is used is defined", () => {
  it("each var(--fs-*) in a stylesheet has a definition in ui-base.css", () => {
    const defined = new Set([...read("ui-base.css").matchAll(/(--fs-[a-z0-9]+)\s*:\s*\d+px/g)].map((m) => m[1]));
    const used = new Set<string>();
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) walk(full);
        else if (name.endsWith(".css")) for (const m of readFileSync(full, "utf-8").matchAll(/var\((--fs-[a-z0-9]+)/g)) used.add(m[1]);
      }
    };
    walk(resolve(__dirname, "../../src"));
    expect([...used].filter((token) => !defined.has(token))).toEqual([]);
  });
});
