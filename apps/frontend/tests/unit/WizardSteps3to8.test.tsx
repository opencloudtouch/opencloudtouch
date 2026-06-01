/**
 * Smoke tests for wizard Steps 3–8 — i18n rendering coverage
 *
 * These tests verify that each step renders without crashing and
 * covers the useTranslation / t() calls added in the i18n migration.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import React from "react";

// Mock the wizard API to prevent async state updates during render
vi.mock("../../src/api/wizard", () => ({
  checkPorts: vi.fn().mockResolvedValue({ success: true, has_ssh: true, message: "SSH access enabled" }),
  detectStrategy: vi.fn().mockResolvedValue({ strategy: "hosts", details: "" }),
  modifyConfig: vi.fn().mockResolvedValue({}),
  getServerInfo: vi.fn().mockResolvedValue({ server_url: "http://192.168.1.50:7777", server_ip: "192.168.1.50", default_port: 7777 }),
  verifyRedirect: vi.fn().mockResolvedValue({ success: true }),
  rebootDevice: vi.fn().mockResolvedValue({}),
  createBackup: vi.fn().mockResolvedValue({ path: "/backup/file.bak" }),
  modifyHosts: vi.fn().mockResolvedValue({}),
  validateHostname: vi.fn().mockResolvedValue({ resolvable: true, resolved_ip: "192.168.1.50", matches_expected: true, error: null }),
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
// Step 3 — handleCheckPorts (port check button logic)
// ------------------------------------------------------------------
describe("Step3PowerCycle — handleCheckPorts", () => {
  it("shows success state when SSH is available", async () => {
    const { checkPorts } = await import("../../src/api/wizard");
    (checkPorts as ReturnType<typeof vi.fn>).mockResolvedValue({
      success: true,
      has_ssh: true,
      message: "SSH access enabled",
    });

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

    const checkBtn = screen.getByRole("button", { name: /Check now/i });
    await act(async () => {
      checkBtn.click();
    });

    expect(checkPorts).toHaveBeenCalledWith({ device_ip: "192.168.1.1", timeout: 10 });
    expect(screen.getByText(/SSH available/i)).toBeInTheDocument();
  });

  it("shows error when SSH is not available", async () => {
    const { checkPorts } = await import("../../src/api/wizard");
    (checkPorts as ReturnType<typeof vi.fn>).mockResolvedValue({
      success: false,
      has_ssh: false,
      message: "SSH not accessible",
    });

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

    const checkBtn = screen.getByRole("button", { name: /Check now/i });
    await act(async () => {
      checkBtn.click();
    });

    expect(screen.getByText(/SSH ist nicht verfügbar/i)).toBeInTheDocument();
  });

  it("shows error message on API failure", async () => {
    const { checkPorts } = await import("../../src/api/wizard");
    (checkPorts as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("Network timeout")
    );

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

    const checkBtn = screen.getByRole("button", { name: /Check now/i });
    await act(async () => {
      checkBtn.click();
    });

    expect(screen.getByText(/Network timeout/i)).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------
// Step 3 — calcRiskLevel (SSH persistence risk assessment via UI)
// ------------------------------------------------------------------
describe("Step3PowerCycle — calcRiskLevel", () => {
  async function renderWithSSHAvailable() {
    const { checkPorts } = await import("../../src/api/wizard");
    (checkPorts as ReturnType<typeof vi.fn>).mockResolvedValue({
      success: true,
      has_ssh: true,
      message: "SSH access enabled",
    });

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

    // Trigger port check to show risk assessment
    const checkBtn = screen.getByRole("button", { name: /Check now/i });
    await act(async () => {
      checkBtn.click();
    });
  }

  it("shows low risk when all answers are safe", async () => {
    await renderWithSSHAvailable();

    // Answer Q1=Yes, Q2=Yes, Q3=No → low risk (score=0)
    const yesButtons = screen.getAllByRole("button", { name: /Yes/i });
    const noButtons = screen.getAllByRole("button", { name: /No$/i });

    await act(async () => { yesButtons[0]!.click(); }); // Q1: yes
    await act(async () => { yesButtons[1]!.click(); }); // Q2: yes
    await act(async () => { noButtons[2]!.click(); }); // Q3: no

    expect(screen.getByText(/Low/i)).toBeInTheDocument();
  });

  it("shows high risk when unknown is selected", async () => {
    await renderWithSSHAvailable();

    // Answer all 3 with Q1=unknown → always high risk
    const unknownButtons = screen.getAllByRole("button", { name: /don't know/i });
    const yesButtons = screen.getAllByRole("button", { name: /Yes/i });
    const noButtons = screen.getAllByRole("button", { name: /No$/i });

    await act(async () => { unknownButtons[0]!.click(); }); // Q1: unknown
    await act(async () => { yesButtons[1]!.click(); }); // Q2: yes
    await act(async () => { noButtons[2]!.click(); }); // Q3: no

    expect(screen.getByText(/High/i)).toBeInTheDocument();
  });

  it("shows medium risk with one risky answer", async () => {
    await renderWithSSHAvailable();

    // Answer Q1=Yes, Q2=Yes, Q3=Yes (updates planned = +1 score → medium)
    const yesButtons = screen.getAllByRole("button", { name: /Yes/i });

    await act(async () => { yesButtons[0]!.click(); }); // Q1: yes
    await act(async () => { yesButtons[1]!.click(); }); // Q2: yes
    await act(async () => { yesButtons[2]!.click(); }); // Q3: yes

    expect(screen.getByText(/Medium/i)).toBeInTheDocument();
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

  it("disables next button while backup is in progress", async () => {
    // createBackup that never resolves — simulates in-progress backup
    const { createBackup } = await import("../../src/api/wizard");
    (createBackup as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

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

    const nextBtn = screen.getByRole("button", { name: /next/i });
    expect(nextBtn).not.toBeDisabled();

    // Click "create backup"
    const backupBtn = screen.getByRole("button", { name: /create backup/i });
    await act(async () => {
      backupBtn.click();
    });

    expect(nextBtn).toBeDisabled();
  });

  it("re-enables next button after backup completes", async () => {
    const { createBackup } = await import("../../src/api/wizard");
    (createBackup as ReturnType<typeof vi.fn>).mockResolvedValue({
      success: true,
      message: "OK",
      volumes: [],
      total_size_mb: 1.0,
      total_duration_seconds: 2.0,
    });

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

    const backupBtn = screen.getByRole("button", { name: /create backup/i });
    await act(async () => {
      backupBtn.click();
    });

    const nextBtn = screen.getByRole("button", { name: /next/i });
    expect(nextBtn).not.toBeDisabled();
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

  it("calls onHostsModified with result and trimmed custom IP", async () => {
    const mockResult = { success: true, message: "OK" };
    const { modifyHosts } = await import("../../src/api/wizard");
    (modifyHosts as ReturnType<typeof vi.fn>).mockResolvedValue(mockResult);

    const onHostsModified = vi.fn();
    const { default: Step6 } = await import(
      "../../src/components/wizard/Step6HostsModification"
    );

    render(
      <Step6
        deviceId="device-1"
        deviceIp="192.168.1.1"
        deviceName="SoundTouch 10"
        octIp="  10.0.0.5  "
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        onHostsModified={onHostsModified}
      />
    );

    // Click the modify-hosts button
    const modifyBtn = screen.getByRole("button", { name: /🌐/i });
    await act(async () => {
      modifyBtn.click();
    });

    await waitFor(() => {
      expect(onHostsModified).toHaveBeenCalledWith(mockResult, "10.0.0.5");
    });
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
