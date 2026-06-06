/**
 * Tests for backup duration formatting in Step4Backup.
 *
 * Verifies that duration is shown as "X Min. Y Sek." instead of raw seconds.
 */

import { describe, test, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

// Mock i18n — return key with interpolated values
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      if (key === "setup.wizard.step4.durationMinSec" && opts) {
        return `${opts.min} Min. ${opts.sec} Sek.`;
      }
      if (key === "setup.wizard.step4.durationSec" && opts) {
        return `${opts.sec} Sek.`;
      }
      return key;
    },
    i18n: { language: "de" },
  }),
}));

// Mock wizard API — will be controlled per test
const mockCreateBackup = vi.fn();
vi.mock("../../src/api/wizard", () => ({
  createBackup: (...args: unknown[]) => mockCreateBackup(...args),
}));

vi.mock("./WizardStep", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import Step4Backup from "../../src/components/wizard/Step4Backup";

describe("Step4Backup - Duration Formatting", () => {
  test("renders duration as 'X Min. Y Sek.' for values >= 60 seconds", async () => {
    // 154 seconds = 2 min 34 sec
    mockCreateBackup.mockResolvedValue({
      success: true,
      total_size_mb: 69.5,
      total_duration_seconds: 154,
      volumes: [
        {
          volume: "RootFS",
          size_mb: 58.2,
          duration_seconds: 134,
          path: "/backup/rootfs.img.gz",
        },
      ],
    });

    render(
      <Step4Backup
        deviceId="C4F312D0B5A1"
        deviceIp="192.168.1.50"
        deviceName="Test Device"
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        onBackupComplete={vi.fn()}
      />
    );

    // Click create backup button (text has emoji prefix)
    const user = userEvent.setup();
    await user.click(screen.getByText(/btnCreate/));

    // Wait for backup result to render
    const summaryText = await screen.findByText(/2 Min\. 34 Sek\./);
    expect(summaryText).toBeTruthy();

    // Volume should show "2 Min. 14 Sek." (134s)
    const volumeText = await screen.findByText(/2 Min\. 14 Sek\./);
    expect(volumeText).toBeTruthy();
  });

  test("renders duration as 'X Sek.' for values < 60 seconds", async () => {
    mockCreateBackup.mockResolvedValue({
      success: true,
      total_size_mb: 0.01,
      total_duration_seconds: 12,
      volumes: [
        {
          volume: "Persistent",
          size_mb: 0.01,
          duration_seconds: 12,
          path: "/backup/persistent.img.gz",
        },
      ],
    });

    render(
      <Step4Backup
        deviceId="C4F312D0B5A1"
        deviceIp="192.168.1.50"
        deviceName="Test Device"
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        onBackupComplete={vi.fn()}
      />
    );

    const user2 = userEvent.setup();
    await user2.click(screen.getByText(/btnCreate/));

    // Both volume and summary show "12 Sek." — findAll because it appears twice
    const matches = await screen.findAllByText(/12 Sek\./);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  test("does NOT render raw seconds like '154.0s'", async () => {
    mockCreateBackup.mockResolvedValue({
      success: true,
      total_size_mb: 69.5,
      total_duration_seconds: 154.3,
      volumes: [
        {
          volume: "RootFS",
          size_mb: 58.2,
          duration_seconds: 134.7,
          path: "/backup/rootfs.img.gz",
        },
      ],
    });

    render(
      <Step4Backup
        deviceId="C4F312D0B5A1"
        deviceIp="192.168.1.50"
        deviceName="Test Device"
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        onBackupComplete={vi.fn()}
      />
    );

    const user3 = userEvent.setup();
    await user3.click(screen.getByText(/btnCreate/));

    // Wait for success to render — multiple elements may match
    const formatted = await screen.findAllByText(/Sek\./);
    expect(formatted.length).toBeGreaterThanOrEqual(1);

    // Must NOT contain raw seconds format
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/154\.3s/);
    expect(body).not.toMatch(/134\.7s/);
    expect(body).not.toMatch(/\d+\.\d+s$/);
  });
});
