/**
 * Tests for RestoreVerification component — post-reboot device poll
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import React from "react";
import RestoreVerification from "../../src/components/wizard/RestoreVerification";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

describe("RestoreVerification", () => {
  const defaultProps = {
    stepNumber: 4,
    deviceIp: "192.168.1.100",
    onVerified: vi.fn(),
    onPrevious: vi.fn(),
  };

  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve([]),
    });
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders countdown initially", () => {
    render(<RestoreVerification {...defaultProps} />);
    expect(screen.getByText(/Checking in/)).toBeInTheDocument();
  });

  it("renders title", () => {
    render(<RestoreVerification {...defaultProps} />);
    expect(screen.getByText("Waiting for Device")).toBeInTheDocument();
  });

  it("shows timeout message after countdown expires", async () => {
    render(<RestoreVerification {...defaultProps} />);
    // Advance 25 intervals of 5s = 125s (past 120s countdown)
    for (let i = 0; i < 25; i++) {
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });
    }
    expect(screen.getByText(/Device not detected after 120s/)).toBeInTheDocument();
  });

  it("shows online message when device is found", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ devices: [{ ip: "192.168.1.100" }] }),
    });
    render(<RestoreVerification {...defaultProps} />);
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText(/Device is back online/)).toBeInTheDocument();
  });

  it("provides manual confirm button after timeout", async () => {
    render(<RestoreVerification {...defaultProps} />);
    for (let i = 0; i < 25; i++) {
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });
    }
    const confirmBtn = screen.getByRole("button", { name: /Device is back/ });
    fireEvent.click(confirmBtn);
    expect(defaultProps.onVerified).toHaveBeenCalledOnce();
  });
});
