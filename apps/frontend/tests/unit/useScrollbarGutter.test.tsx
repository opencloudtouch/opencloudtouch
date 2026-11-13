/**
 * Regression tests (final browser audit F9, F10).
 */
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { measureScrollbarWidth, useScrollbarGutter } from "../../src/hooks/useScrollbarGutter";
import LanguageSelector from "../../src/components/LanguageSelector";
import { UI_LOCALES } from "../../src/i18n";

function Probe() {
  useScrollbarGutter();
  return null;
}

function addMain(offsetWidth: number, clientWidth: number) {
  const main = document.createElement("main");
  main.className = "app-main";
  Object.defineProperty(main, "offsetWidth", { value: offsetWidth, configurable: true });
  Object.defineProperty(main, "clientWidth", { value: clientWidth, configurable: true });
  document.body.appendChild(main);
  return main;
}

afterEach(() => {
  cleanup();
  document.querySelectorAll(".app-main").forEach((el) => el.remove());
});

describe("scrollbar gutter of the header (F9)", () => {
  it("measures the scrollbar width of the page area", () => {
    addMain(1280, 1265);
    expect(measureScrollbarWidth()).toBe(15);
  });

  it("is 0 without a page area or with overlay scrollbars", () => {
    expect(measureScrollbarWidth()).toBe(0);
    addMain(1280, 1280);
    expect(measureScrollbarWidth()).toBe(0);
  });

  it("publishes --scrollbar-w for the header and removes it on unmount", () => {
    addMain(1280, 1265);
    const { unmount } = render(<Probe />);
    expect(document.documentElement.style.getPropertyValue("--scrollbar-w")).toBe("15px");
    unmount();
    expect(document.documentElement.style.getPropertyValue("--scrollbar-w")).toBe("");
  });

  it("the header uses the variable as right padding", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const css = readFileSync(resolve(__dirname, "../../src/app-shell.css"), "utf-8");
    expect(css).toMatch(/\.app-header \{[^}]*padding-right: var\(--scrollbar-w, 0px\)/);
  });
});

describe("flag images are loaded up front (F10)", () => {
  it("renders a flag for every UI language outside the dropdown", () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageSelector />
      </MemoryRouter>
    );
    const preload = container.querySelector(".lang-flag-preload");
    expect(preload).not.toBeNull();
    expect(preload!.querySelectorAll(".fi")).toHaveLength(UI_LOCALES.length);
    expect(preload).toHaveAttribute("aria-hidden", "true");
  });
});
