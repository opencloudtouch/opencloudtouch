/**
 * Navigation Component Tests
 *
 * User Story: Als User navigiere ich zwischen App-Bereichen
 *
 * Focus: User can navigate to all app sections via navigation bar
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import Navigation from "../../src/components/Navigation";

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
});
