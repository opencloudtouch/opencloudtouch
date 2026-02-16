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

  it("renders all navigation links", () => {
    renderNavigation();

    expect(screen.getByText("Presets")).toBeInTheDocument();
    expect(screen.getByText("Control")).toBeInTheDocument();
    expect(screen.getByText("Zones")).toBeInTheDocument();
    expect(screen.getByText("Firmware")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders navigation links with correct paths", () => {
    renderNavigation();

    const presetsLink = screen.getByText("Presets").closest("a");
    const controlLink = screen.getByText("Control").closest("a");
    const zonesLink = screen.getByText("Zones").closest("a");
    const firmwareLink = screen.getByText("Firmware").closest("a");
    const settingsLink = screen.getByText("Settings").closest("a");

    expect(presetsLink).toHaveAttribute("href", "/");
    expect(controlLink).toHaveAttribute("href", "/local");
    expect(zonesLink).toHaveAttribute("href", "/multiroom");
    expect(firmwareLink).toHaveAttribute("href", "/firmware");
    expect(settingsLink).toHaveAttribute("href", "/settings");
  });

  it("renders all navigation icons", () => {
    renderNavigation();

    // Check for icon emojis
    expect(screen.getByText("📻")).toBeInTheDocument();
    expect(screen.getByText("🎵")).toBeInTheDocument();
    expect(screen.getByText("🔊")).toBeInTheDocument();
    expect(screen.getByText("⚙️")).toBeInTheDocument();
    expect(screen.getByText("⚡")).toBeInTheDocument();
  });

  it("applies correct CSS classes", () => {
    renderNavigation();

    const nav = document.querySelector("nav");
    const navContainer = document.querySelector(".nav-container");

    expect(nav).toHaveClass("nav");
    expect(navContainer).toBeInTheDocument();

    const navLinks = document.querySelectorAll(".nav-link");
    expect(navLinks).toHaveLength(5);
  });

  it("renders nav labels within nav-label spans", () => {
    renderNavigation();

    const navLabels = document.querySelectorAll(".nav-label");
    expect(navLabels).toHaveLength(5);

    const labelTexts = Array.from(navLabels).map((label) => label.textContent);
    expect(labelTexts).toEqual(["Presets", "Control", "Zones", "Firmware", "Settings"]);
  });

  it("renders nav icons within nav-icon spans", () => {
    renderNavigation();

    const navIcons = document.querySelectorAll(".nav-icon");
    expect(navIcons).toHaveLength(5);

    const iconTexts = Array.from(navIcons).map((icon) => icon.textContent);
    expect(iconTexts).toEqual(["📻", "🎵", "🔊", "⚙️", "⚡"]);
  });
});
