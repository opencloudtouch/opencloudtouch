/**
 * Smoke tests for wizard Steps 3–8 — i18n rendering coverage
 *
 * These tests verify that each step renders without crashing and
 * covers the useTranslation / t() calls added in the i18n migration.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React from "react";

// Mock the wizard API to prevent async state updates during render
vi.mock("../../src/api/wizard", () => ({
  detectStrategy: vi.fn().mockResolvedValue({ strategy: "hosts", details: "" }),
  modifyConfig: vi.fn().mockResolvedValue({}),
  getServerInfo: vi.fn().mockResolvedValue({}),
  verifyRedirect: vi.fn().mockResolvedValue({ success: true }),
  rebootDevice: vi.fn().mockResolvedValue({}),
  createBackup: vi.fn().mockResolvedValue({ path: "/backup/file.bak" }),
  modifyHosts: vi.fn().mockResolvedValue({}),
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    span: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <span {...props}>{children}</span>
    ),
    ul: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <ul {...props}>{children}</ul>
    ),
    p: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <p {...props}>{children}</p>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

// ------------------------------------------------------------------
// Step 3 — Power Cycle
// ------------------------------------------------------------------
describe("Step3PowerCycle — render", () => {
  it("renders without crashing with required props", async () => {
    const { default: Step3 } = await import(
      "../../src/components/wizard/Step3PowerCycle"
    );
    render(
      <Step3
        deviceIp="192.168.1.1"
        deviceName="SoundTouch 10"
        onSSHDecision={vi.fn()}
        onPrevious={vi.fn()}
      />
    );
    expect(document.body).toBeInTheDocument();
  });

  it("renders a button for SSH decision", async () => {
    const { default: Step3 } = await import(
      "../../src/components/wizard/Step3PowerCycle"
    );
    render(
      <Step3
        deviceIp="192.168.1.1"
        deviceName="My Speaker"
        onSSHDecision={vi.fn()}
        onPrevious={vi.fn()}
      />
    );
    // At least one button must be rendered (previous, SSH decision)
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });
});

// ------------------------------------------------------------------
// Step 4 — Backup
// ------------------------------------------------------------------
describe("Step4Backup — render", () => {
  it("renders without crashing with required props", async () => {
    const { default: Step4 } = await import(
      "../../src/components/wizard/Step4Backup"
    );
    render(
      <Step4
        deviceId="device-1"
        deviceIp="192.168.1.1"
        deviceName="SoundTouch 10"
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        onBackupComplete={vi.fn()}
      />
    );
    expect(document.body).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------
// Step 5 — Config Modification
// ------------------------------------------------------------------
describe("Step5ConfigModification — render", () => {
  it("renders without crashing with required props", async () => {
    const { default: Step5 } = await import(
      "../../src/components/wizard/Step5ConfigModification"
    );
    await act(async () => {
      render(
        <Step5
          deviceId="device-1"
          deviceIp="192.168.1.1"
          deviceName="SoundTouch 10"
          octUrl="http://192.168.1.100:8080"
          onNext={vi.fn()}
          onPrevious={vi.fn()}
          onConfigModified={vi.fn()}
        />
      );
    });
    expect(document.body).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------
// Step 6 — Hosts Modification
// ------------------------------------------------------------------
describe("Step6HostsModification — render", () => {
  it("renders without crashing with required props", async () => {
    const { default: Step6 } = await import(
      "../../src/components/wizard/Step6HostsModification"
    );
    render(
      <Step6
        deviceId="device-1"
        deviceIp="192.168.1.1"
        deviceName="SoundTouch 10"
        octIp="192.168.1.100"
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        onHostsModified={vi.fn()}
      />
    );
    expect(document.body).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------
// Step 7 — Verification
// ------------------------------------------------------------------
describe("Step7Verification — render", () => {
  it("renders without crashing with required props", async () => {
    const { default: Step7 } = await import(
      "../../src/components/wizard/Step7Verification"
    );
    await act(async () => {
      render(
        <Step7
          deviceIp="192.168.1.1"
          deviceName="SoundTouch 10"
          octIp="192.168.1.100"
          onNext={vi.fn()}
          onPrevious={vi.fn()}
        />
      );
    });
    expect(document.body).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------
// Step 8 — Completion
// ------------------------------------------------------------------
describe("Step8Completion — render", () => {
  it("renders without crashing when backupPath is provided", async () => {
    const { default: Step8 } = await import(
      "../../src/components/wizard/Step8Completion"
    );
    render(
      <Step8
        deviceName="SoundTouch 10"
        backupPath="/backup/remote_services.bak"
        onFinish={vi.fn()}
      />
    );
    expect(document.body).toBeInTheDocument();
  });

  it("renders without crashing when backupPath is null", async () => {
    const { default: Step8 } = await import(
      "../../src/components/wizard/Step8Completion"
    );
    render(
      <Step8
        deviceName="SoundTouch 10"
        backupPath={null}
        onFinish={vi.fn()}
      />
    );
    expect(document.body).toBeInTheDocument();
  });
});
