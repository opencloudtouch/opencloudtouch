/**
 * Licenses Page Tests
 *
 * User Story: Als User möchte ich Open-Source Lizenzinformationen einsehen
 *
 * Focus: Page renders all required license sections (legal compliance)
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import Licenses from "../../src/pages/Licenses";

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
    expect(screen.getByText(/About/i)).toBeInTheDocument();
  });
});
