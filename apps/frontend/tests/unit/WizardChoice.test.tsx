/**
 * Tests for WizardChoice component — Setup/Restore entry screen
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import WizardChoice from "../../src/components/wizard/WizardChoice";

vi.mock("framer-motion", () => ({
  motion: {
    button: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
      const { whileHover, whileTap, ...rest } = props as Record<string, unknown>;
      void whileHover;
      void whileTap;
      return <button {...(rest as React.ButtonHTMLAttributes<HTMLButtonElement>)}>{children}</button>;
    },
  },
}));

describe("WizardChoice", () => {
  const defaultProps = {
    onSelectSetup: vi.fn(),
    onSelectRestore: vi.fn(),
  };

  it("renders both choice cards", () => {
    render(<WizardChoice {...defaultProps} />);
    expect(screen.getByText("Setup Wizard")).toBeInTheDocument();
    expect(screen.getByText("Restore Wizard")).toBeInTheDocument();
  });

  it("renders title", () => {
    render(<WizardChoice {...defaultProps} />);
    expect(screen.getByText("What would you like to do?")).toBeInTheDocument();
  });

  it("calls onSelectSetup when setup card is clicked", () => {
    const onSetup = vi.fn();
    render(<WizardChoice onSelectSetup={onSetup} onSelectRestore={vi.fn()} />);
    fireEvent.click(screen.getByText("Setup Wizard"));
    expect(onSetup).toHaveBeenCalledOnce();
  });

  it("calls onSelectRestore when restore card is clicked", () => {
    const onRestore = vi.fn();
    render(<WizardChoice onSelectSetup={vi.fn()} onSelectRestore={onRestore} />);
    fireEvent.click(screen.getByText("Restore Wizard"));
    expect(onRestore).toHaveBeenCalledOnce();
  });

  it("renders descriptions for both options", () => {
    render(<WizardChoice {...defaultProps} />);
    expect(screen.getByText("Configure device for OpenCloudTouch")).toBeInTheDocument();
    expect(screen.getByText("Undo all OCT changes and restore factory state")).toBeInTheDocument();
  });
});
