import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { readFileSync } from "fs";
import { resolve } from "path";
import ThemedLogo from "../../src/components/ThemedLogo";

describe("ThemedLogo", () => {
  it("renders one image for each theme with the same size and alt text", () => {
    const { container } = render(<ThemedLogo className="x-logo" size={96} alt="OpenCloudTouch" />);
    const imgs = container.querySelectorAll("img");
    expect(imgs).toHaveLength(2);
    const forDark = container.querySelector(".themed-logo--for-dark") as HTMLImageElement;
    const forLight = container.querySelector(".themed-logo--for-light") as HTMLImageElement;
    expect(forDark.getAttribute("src")).toContain("oct-logo-dark");
    expect(forLight.getAttribute("src")).toContain("oct-logo-light");
    for (const img of [forDark, forLight]) {
      expect(img).toHaveClass("x-logo");
      expect(img).toHaveAttribute("width", "96");
      expect(img).toHaveAttribute("height", "96");
      expect(img).toHaveAttribute("alt", "OpenCloudTouch");
      expect(img).toHaveAttribute("loading", "lazy");
    }
  });

  it("supports a decorative logo with an empty alt text", () => {
    const { container } = render(<ThemedLogo size={96} alt="" />);
    container.querySelectorAll("img").forEach((img) => expect(img).toHaveAttribute("alt", ""));
  });

  it("hides the logo of the other theme in CSS", () => {
    const css = readFileSync(resolve(__dirname, "../../src/components/ThemedLogo.css"), "utf-8");
    expect(css).toMatch(/\[data-theme="light"\]\s+\.themed-logo--for-dark\s*\{\s*display:\s*none/);
    expect(css).toMatch(
      /:root:not\(\[data-theme="light"\]\)\s+\.themed-logo--for-light\s*\{\s*display:\s*none/
    );
  });
});
