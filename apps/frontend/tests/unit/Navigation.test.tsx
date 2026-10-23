/**
 * Navigation Component Tests
 *
 * User Story: Als User navigiere ich zwischen App-Bereichen
 *
 * Focus: User can navigate to all app sections via navigation bar
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter, MemoryRouter } from "react-router";
import Navigation from "../../src/components/Navigation";

// tests/setup.ts stubs useSearchParams; this file needs the real one to test the ?device= handling
vi.mock("react-router", async () => await vi.importActual("react-router"));

describe("Navigation Component", () => {
  const renderNavigation = () => {
    return render(
      <BrowserRouter>
        <Navigation />
      </BrowserRouter>
    );
  };

  it("provides navigation links to all app sections", () => {
    renderNavigation();

    // Presets, Zones, Settings, and About are visible in Navigation
    const expectedLinks = [
      { text: "Presets", path: "/" },
      { text: "Zones", path: "/multiroom" },
      { text: "Settings", path: "/settings" },
      { text: "About", path: "/about" },
    ];

    expectedLinks.forEach(({ text, path }) => {
      const link = screen.getByText(text).closest("a");
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", path);
    });
  });
  it.each([
    ["/?device=AABB", "/?device=AABB"],
    ["/setup-wizard?deviceId=AABB", "/?device=AABB"], // the wizard uses ?deviceId=
    ["/setup-wizard", "/"],
  ])("keeps the selected device in the Presets link (%s)", (url, expectedHref) => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <Navigation />
      </MemoryRouter>,
    );
    expect(screen.getByText("Presets").closest("a")).toHaveAttribute("href", expectedHref);
  });
});
