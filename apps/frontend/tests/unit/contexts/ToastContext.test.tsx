/**
 * Tests for ToastContext — global toast notification provider.
 */
import { describe, it, expect, vi } from "vitest";
import { renderHook, render, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../../../src/contexts/ToastContext";

vi.mock("../../../src/components/Toast", () => ({
  default: ({ message, type }: { message: string; type: string }) => (
    <div data-testid="mock-toast" data-type={type}>
      {message}
    </div>
  ),
}));

describe("ToastContext", () => {
  it("renders the toast with the default type and duration when omitted", () => {
    let captured: {
      show: (message: string, type?: string, duration?: number) => void;
      hide: () => void;
    } | null = null;

    function Capture() {
      captured = useToast();
      return null;
    }

    const { getByTestId, queryByTestId } = render(
      <ToastProvider>
        <Capture />
      </ToastProvider>
    );

    expect(queryByTestId("mock-toast")).toBeNull();

    act(() => captured!.show("Hello"));

    expect(getByTestId("mock-toast")).toHaveTextContent("Hello");
    expect(getByTestId("mock-toast")).toHaveAttribute("data-type", "info");

    act(() => captured!.hide());

    expect(queryByTestId("mock-toast")).toBeNull();
  });

  it("throws when used outside a ToastProvider", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useToast())).toThrow(
      "useToast must be used within ToastProvider"
    );

    errorSpy.mockRestore();
  });
});
