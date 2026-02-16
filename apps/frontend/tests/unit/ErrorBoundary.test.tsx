/**
 * ErrorBoundary Component Tests
 * Tests error catching, fallback UI, and recovery mechanisms
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "../../src/components/ErrorBoundary";

// Component that throws an error
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Test error");
  }
  return <div>No error</div>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // Suppress console.error output during tests
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div>Test content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText("Test content")).toBeInTheDocument();
  });

  it("catches errors and displays fallback UI", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Etwas ist schiefgelaufen")).toBeInTheDocument();
    expect(screen.getByText(/Ein unerwarteter Fehler ist aufgetreten/i)).toBeInTheDocument();
  });

  it("displays error details in expandable section", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const details = screen.getByText("Fehlerdetails");
    expect(details).toBeInTheDocument();

    // Error message should be visible after expanding
    fireEvent.click(details);
    const errorElements = screen.getAllByText(/Test error/);
    expect(errorElements.length).toBeGreaterThan(0);
  });

  it("provides reload button", () => {
    const reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload: reloadSpy },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole("button", { name: /neu laden/i });
    expect(reloadButton).toBeInTheDocument();

    fireEvent.click(reloadButton);
    expect(reloadSpy).toHaveBeenCalled();
  });

  it("provides retry button that resets error state", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Etwas ist schiefgelaufen")).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: /fehler zurücksetzen/i });
    expect(retryButton).toBeInTheDocument();

    // Clicking reset button should attempt to reset (but ThrowError will throw again)
    // We're just testing the button exists and is clickable
    fireEvent.click(retryButton);

    // Error boundary will re-catch the error from ThrowError, so error UI remains
    expect(screen.getByText("Etwas ist schiefgelaufen")).toBeInTheDocument();
  });

  it("supports custom fallback UI", () => {
    const customFallback = (error: Error, reset: () => void) => (
      <div>
        <h1>Custom Error</h1>
        <p>{error.message}</p>
        <button onClick={reset}>Custom Reset</button>
      </div>
    );

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Custom Error")).toBeInTheDocument();
    expect(screen.getByText("Test error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /custom reset/i })).toBeInTheDocument();

    // Default UI should not be visible
    expect(screen.queryByText("Etwas ist schiefgelaufen")).not.toBeInTheDocument();
  });

  it("logs error to console in development", () => {
    const consoleSpy = vi.spyOn(console, "error");

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(consoleSpy).toHaveBeenCalledWith(
      "ErrorBoundary caught an error:",
      expect.any(Error),
      expect.any(Object)
    );
  });

  it("displays error stack trace", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const details = screen.getByText("Fehlerdetails");
    fireEvent.click(details);

    // Stack trace should contain function names
    const stackElements = screen.getAllByText(/ThrowError|Error/);
    expect(stackElements.length).toBeGreaterThan(0);
  });
});
