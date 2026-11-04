/**
 * Step4Backup: a failed backup must be repeatable, and the success hint must appear only once.
 *
 * Regression: when createBackup() resolved with success=false (or rejected after the first call set
 * backupData), the "create backup" button was hidden and the user could not try again.
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "de" },
  }),
}));

const mockCreateBackup = vi.fn();
vi.mock("../../src/api/wizard", () => ({
  createBackup: (...args: unknown[]) => mockCreateBackup(...args),
}));

vi.mock("../../src/components/wizard/WizardStep", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import Step4Backup from "../../src/components/wizard/Step4Backup";

function renderStep() {
  return render(
    <Step4Backup
      deviceId="C4F312D0B5A1"
      deviceIp="192.168.1.50"
      deviceName="Test Device"
      onNext={vi.fn()}
      onPrevious={vi.fn()}
      onBackupComplete={vi.fn()}
    />
  );
}

describe("Step4Backup - retry and success hint", () => {
  beforeEach(() => {
    mockCreateBackup.mockReset();
  });

  test("keeps the create button as 'retry' after a failed backup and succeeds on the second try", async () => {
    mockCreateBackup
      .mockResolvedValueOnce({ success: false, message: "Command timeout after 180.0s", volumes: [] })
      .mockResolvedValueOnce({
        success: true,
        total_size_mb: 1,
        total_duration_seconds: 5,
        volumes: [{ volume: "nv", size_mb: 1, duration_seconds: 5, path: "/usb/nv.tgz" }],
      });
    const user = userEvent.setup();
    const { container } = renderStep();

    await user.click(screen.getByText(/btnCreate/));
    await waitFor(() => expect(screen.getByText("Command timeout after 180.0s")).toBeInTheDocument());

    // The button is still there, now labelled as a retry, and the risk warning is shown.
    const retry = container.querySelector<HTMLButtonElement>("button.backup-create-btn");
    expect(retry).not.toBeNull();
    expect(retry?.textContent).toContain("common.retry");
    expect(screen.getByText("setup.wizard.step4.nextWarning")).toBeInTheDocument();

    await user.click(retry as HTMLButtonElement);
    await waitFor(() => expect(container.querySelector(".backup-success")).not.toBeNull());

    expect(mockCreateBackup).toHaveBeenCalledTimes(2);
    // After success the old error and the retry button are gone.
    expect(container.querySelector(".backup-error")).toBeNull();
    expect(container.querySelector(".backup-next-warning")).toBeNull();
    expect(container.querySelector("button.backup-create-btn")).toBeNull();
  });

  test("shows the success hint text only once", async () => {
    mockCreateBackup.mockResolvedValue({
      success: true,
      total_size_mb: 1,
      total_duration_seconds: 5,
      volumes: [{ volume: "nv", size_mb: 1, duration_seconds: 5, path: "/usb/nv.tgz" }],
    });
    const user = userEvent.setup();
    renderStep();

    await user.click(screen.getByText(/btnCreate/));
    await waitFor(() => expect(screen.getAllByText("setup.wizard.step4.successHint")).toHaveLength(1));
  });
});
