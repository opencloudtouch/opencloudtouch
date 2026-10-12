/**
 * Tests for the 404 NotFound page
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import NotFound from "../../src/pages/NotFound";

// tests/setup.ts mocks react-router's useNavigate with `() => vi.fn()`, which
// hands out a fresh, unassertable spy on every call. Override it locally with
// a stable mock so we can assert what it was called with (precedent:
// EmptyState.test.tsx does the same per-file override).
const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("NotFound page", () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it("renders the 404 code", () => {
    render(<NotFound />);
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("clicking the back button navigates to the home route", () => {
    render(<NotFound />);
    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });
});
