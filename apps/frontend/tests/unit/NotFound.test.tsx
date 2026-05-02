/**
 * Tests for the 404 NotFound page
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import NotFound from "../../src/pages/NotFound";

describe("NotFound page", () => {
  it("renders the 404 code", () => {
    render(<NotFound />);
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("renders navigation button", () => {
    render(<NotFound />);
    const button = screen.getByRole("button");
    expect(button).toBeInTheDocument();
  });

  it("clicking the back button does not throw", () => {
    render(<NotFound />);
    const button = screen.getByRole("button");
    fireEvent.click(button);
    // useNavigate is mocked globally in setup.ts; click must not throw
    expect(button).toBeInTheDocument();
  });
});
