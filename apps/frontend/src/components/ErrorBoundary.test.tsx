/**
 * Tests for ErrorBoundary component
 *
 * Tests error catching, fallback rendering, and reset functionality.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { ErrorBoundary } from "./ErrorBoundary";

// Component that throws an error
const ThrowError = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error("Test error");
  }
  return <div>No error</div>;
};

describe("ErrorBoundary", () => {
  // Suppress console.error for these tests since we expect errors
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("renders children when there is no error", () => {
    render(
      <ErrorBoundary>
        <div>Test content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText("Test content")).toBeInTheDocument();
  });

  it("renders default fallback UI when child component throws", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText(/An unexpected error occurred/i)).toBeInTheDocument();
  });

  it("displays error details in expandable section", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    const details = screen.getByText("Error details");
    expect(details).toBeInTheDocument();

    // Error message should be in the document (check for summary element, not text duplicates)
    const summary = screen.getByRole("group"); //<details> renders as role=group
    expect(summary).toBeInTheDocument();
  });

  it("calls console.error when error is caught", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(consoleErrorSpy).toHaveBeenCalled();
    // React will call console.error multiple times, check any call contains our message
    const errorCalls = consoleErrorSpy.mock.calls.flat();
    expect(
      errorCalls.some(
        (call: unknown) =>
          typeof call === "string" && call.includes("ErrorBoundary caught an error")
      )
    ).toBe(true);
  });

  it("renders custom fallback when provided", () => {
    const customFallback = (error: Error) => <div>Custom error: {error.message}</div>;

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText("Custom error: Test error")).toBeInTheDocument();
    expect(screen.queryByText(/Something went wrong/i)).not.toBeInTheDocument();
  });

  it("provides reset function to custom fallback", async () => {
    let resetCalled = false;

    const customFallback = (_error: Error, reset: () => void) => {
      return (
        <div>
          Error occurred
          <button
            onClick={() => {
              resetCalled = true;
              reset();
            }}
          >
            Reset
          </button>
        </div>
      );
    };

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText("Error occurred")).toBeInTheDocument();

    // Click reset button
    const resetButton = screen.getByText("Reset");
    await userEvent.click(resetButton);

    // Verify reset was called
    expect(resetCalled).toBe(true);
  });

  it("reloads page when reload button is clicked", async () => {
    // Mock window.location.reload
    const reloadMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload: reloadMock },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole("button", { name: /Reload page/i });
    await userEvent.click(reloadButton);

    expect(reloadMock).toHaveBeenCalledOnce();
  });

  it("catches errors from deeply nested components", () => {
    const DeepChild = () => {
      throw new Error("Deep error");
    };

    render(
      <ErrorBoundary>
        <div>
          <div>
            <div>
              <DeepChild />
            </div>
          </div>
        </div>
      </ErrorBoundary>
    );

    // Error boundary shows fallback
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    // Error details section exists (use getAllByText since error appears in two places)
    const errorElements = screen.getAllByText("Error: Deep error", { exact: false });
    expect(errorElements.length).toBeGreaterThan(0);
  });
});
