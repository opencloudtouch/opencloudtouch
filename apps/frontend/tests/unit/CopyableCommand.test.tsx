import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import CopyableCommand from "../../src/components/wizard/CopyableCommand";

describe("CopyableCommand", () => {
  const originalClipboard = navigator.clipboard;
  const originalIsSecureContext = window.isSecureContext;
  const originalExecCommand = document.execCommand;

  afterEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: originalClipboard,
      configurable: true,
    });
    Object.defineProperty(window, "isSecureContext", {
      value: originalIsSecureContext,
      configurable: true,
    });
    document.execCommand = originalExecCommand;
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("renders the command text and the default (uncopied) button state", () => {
    render(<CopyableCommand command="ssh user@host" />);

    expect(screen.getByText("ssh user@host")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Befehl kopieren" });
    expect(button).toHaveTextContent("⎘");
    expect(button.className).not.toContain("copied");
  });

  it("copies via navigator.clipboard.writeText when in a secure context with the API present, then resets after 2s", async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });

    render(<CopyableCommand command="ssh user@host" />);
    const button = screen.getByRole("button", { name: "Befehl kopieren" });

    fireEvent.click(button);
    // Flush the writeText() promise's .then() microtask under fake timers.
    await act(() => vi.advanceTimersByTimeAsync(0));

    expect(writeText).toHaveBeenCalledWith("ssh user@host");
    expect(button).toHaveTextContent("✓");
    expect(button.className).toContain("copied");

    await act(() => vi.advanceTimersByTimeAsync(2000));

    expect(button).toHaveTextContent("⎘");
    expect(button.className).not.toContain("copied");
  });

  it("falls back to document.execCommand when the Clipboard API is absent, and cleans up the helper textarea", async () => {
    vi.useFakeTimers();
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
    const execCommand = vi.fn().mockReturnValue(true);
    document.execCommand = execCommand;

    render(<CopyableCommand command="ssh user@host" />);
    const button = screen.getByRole("button", { name: "Befehl kopieren" });

    fireEvent.click(button);

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(button).toHaveTextContent("✓");
    expect(button.className).toContain("copied");
    // The finally block must have removed the temporary textarea from the DOM.
    expect(document.querySelector("textarea")).toBeNull();

    await act(() => vi.advanceTimersByTimeAsync(2000));

    expect(button).toHaveTextContent("⎘");
    expect(button.className).not.toContain("copied");
  });

  it("also falls back to document.execCommand when navigator.clipboard is present but the context isn't secure", () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    Object.defineProperty(window, "isSecureContext", { value: false, configurable: true });
    const execCommand = vi.fn().mockReturnValue(true);
    document.execCommand = execCommand;

    render(<CopyableCommand command="ssh user@host" />);
    const button = screen.getByRole("button", { name: "Befehl kopieren" });

    fireEvent.click(button);

    // isSecureContext=false short-circuits the clipboard-API branch entirely.
    expect(writeText).not.toHaveBeenCalled();
    expect(execCommand).toHaveBeenCalledWith("copy");
  });
});
