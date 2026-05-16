/**
 * Tests for RestoreCompletion component — summary screen
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import RestoreCompletion from "../../src/components/wizard/RestoreCompletion";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

describe("RestoreCompletion", () => {
  const completedSteps = [
    { name: "config", status: "completed", message: "Config files restored", error: null, duration_seconds: 2.1 },
    { name: "presets", status: "completed", message: "Presets cleared", error: null, duration_seconds: 1.0 },
    { name: "hosts", status: "skipped", message: "No OCT block found", error: null, duration_seconds: 0 },
  ];

  it("renders title", () => {
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="clean"
        steps={completedSteps}
        onFinish={vi.fn()}
      />,
    );
    expect(screen.getByText("Restore Complete")).toBeInTheDocument();
  });

  it("shows clean restore summary for clean type", () => {
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="clean"
        steps={completedSteps}
        onFinish={vi.fn()}
      />,
    );
    expect(screen.getByText("Clean Restore Summary")).toBeInTheDocument();
  });

  it("shows backup restore summary for backup type", () => {
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="backup"
        steps={completedSteps}
        onFinish={vi.fn()}
      />,
    );
    expect(screen.getByText("Backup Restore Summary")).toBeInTheDocument();
  });

  it("lists completed steps", () => {
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="clean"
        steps={completedSteps}
        onFinish={vi.fn()}
      />,
    );
    expect(screen.getByText("Config files restored")).toBeInTheDocument();
    expect(screen.getByText("Presets cleared")).toBeInTheDocument();
  });

  it("lists skipped steps separately", () => {
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="clean"
        steps={completedSteps}
        onFinish={vi.fn()}
      />,
    );
    expect(screen.getByText("No OCT block found")).toBeInTheDocument();
  });

  it("shows failed steps with error details", () => {
    const stepsWithFailure = [
      ...completedSteps,
      { name: "remote_services", status: "failed", message: "Could not remove", error: "Permission denied", duration_seconds: 0.5 },
    ];
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="clean"
        steps={stepsWithFailure}
        onFinish={vi.fn()}
      />,
    );
    expect(screen.getByText(/Permission denied/)).toBeInTheDocument();
  });

  it("calls onFinish when Done button is clicked", () => {
    const onFinish = vi.fn();
    render(
      <RestoreCompletion
        stepNumber={5}
        restoreType="clean"
        steps={completedSteps}
        onFinish={onFinish}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /done/i }));
    expect(onFinish).toHaveBeenCalledOnce();
  });
});
