/**
 * Licenses Page Tests
 *
 * User Story: Als User möchte ich Open-Source Lizenzinformationen einsehen
 *
 * Focus: Page renders all required license sections (legal compliance)
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import Licenses from "../../src/pages/Licenses";

// tests/setup.ts mocks useSearchParams with empty params; this suite needs to set them
const search = vi.hoisted(() => ({ value: "" }));
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useSearchParams: () => [new URLSearchParams(search.value), vi.fn()] };
});

describe("Licenses Page", () => {
  it("displays all required license information for legal compliance", () => {
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );

    // Page title
    expect(screen.getByText(/Open-Source Licenses/i)).toBeInTheDocument();

    // Frontend dependencies must be listed
    expect(screen.getByText("React", { exact: true })).toBeInTheDocument();
    expect(screen.getByText(/Framer Motion/i)).toBeInTheDocument();

    // Backend dependencies must be listed
    expect(screen.getByText(/FastAPI/i)).toBeInTheDocument();

    // Legal compliance sections
    expect(screen.getByText(/License Compliance/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /About/i })).toBeInTheDocument();
    // the back link to the About page
    expect(screen.getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
  });

  it("keeps the selected device in the back link to About", () => {
    search.value = "device=AABB";
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );
    expect(screen.getByRole("link", { name: "About" })).toHaveAttribute(
      "href",
      "/about?device=AABB"
    );
    search.value = "";
  });
});
