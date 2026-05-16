/**
 * Tests for RestoreChoice component — Clean/Backup restore selection
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import RestoreChoice from "../../src/components/wizard/RestoreChoice";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    button: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
      const { whileHover, whileTap, ...rest } = props as Record<string, unknown>;
      void whileHover;
      void whileTap;
      return <button {...(rest as React.ButtonHTMLAttributes<HTMLButtonElement>)}>{children}</button>;
    },
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

describe("RestoreChoice", () => {
  const defaultProps = {
    stepNumber: 1,
    onCleanRestore: vi.fn(),
    onBackupRestore: vi.fn(),
    onPrevious: vi.fn(),
  };

  it("renders both restore type options", () => {
    render(<RestoreChoice {...defaultProps} />);
    expect(screen.getByText("Clean Restore")).toBeInTheDocument();
    expect(screen.getByText("Restore from Backup")).toBeInTheDocument();
  });

  it("renders title and description", () => {
    render(<RestoreChoice {...defaultProps} />);
    expect(screen.getByText("Choose Restore Type")).toBeInTheDocument();
    expect(screen.getByText("Select how you want to restore the device.")).toBeInTheDocument();
  });

  it("calls onCleanRestore when clean option is clicked", () => {
    const onClean = vi.fn();
    render(<RestoreChoice {...defaultProps} onCleanRestore={onClean} />);
    fireEvent.click(screen.getByText("Clean Restore"));
    expect(onClean).toHaveBeenCalledOnce();
  });

  it("calls onBackupRestore when backup option is clicked", () => {
    const onBackup = vi.fn();
    render(<RestoreChoice {...defaultProps} onBackupRestore={onBackup} />);
    fireEvent.click(screen.getByText("Restore from Backup"));
    expect(onBackup).toHaveBeenCalledOnce();
  });

  it("shows descriptions for each option", () => {
    render(<RestoreChoice {...defaultProps} />);
    expect(screen.getByText("Remove all OCT modifications. No backup needed.")).toBeInTheDocument();
    expect(screen.getByText("Restore original config files from USB backup.")).toBeInTheDocument();
  });
});
