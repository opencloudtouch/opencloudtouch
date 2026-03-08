/**
 * Tests for SetupWizard V2 (pages/SetupWizard.tsx)
 *
 * V2 wizard: device array input, mode selection (guided/manual), step navigation.
 * Sub-components are mocked to keep tests focused on wizard orchestration.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import SetupWizard from "../../../src/pages/SetupWizard";
import type { Device } from "../../../src/api/devices";

// Mock framer-motion to avoid animation issues in jsdom
vi.mock("framer-motion", () => ({
  motion: {
    /* eslint-disable @typescript-eslint/no-unused-vars */
    div: ({
      children,
      initial,
      animate,
      exit,
      transition,
      ...props
    }: Record<string, unknown>) => <div {...props}>{children as React.ReactNode}</div>,
    /* eslint-enable @typescript-eslint/no-unused-vars */
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock wizard sub-components
vi.mock("../../../src/components/wizard/DeviceInfoHeader", () => ({
  default: ({ device }: { device: { name: string } }) => (
    <div data-testid="device-info-header">{device.name}</div>
  ),
}));

vi.mock("../../../src/components/wizard/ModeSelector", () => ({
  default: ({ onModeSelect }: { onModeSelect: (mode: "guided" | "manual") => void }) => (
    <div data-testid="mode-selector">
      <button onClick={() => onModeSelect("guided")}>Guided</button>
      <button onClick={() => onModeSelect("manual")}>Manual</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/ProgressTracker", () => ({
  default: ({ currentStep }: { currentStep: number }) => (
    <div data-testid="progress-tracker">Step {currentStep}</div>
  ),
}));

vi.mock("../../../src/components/wizard/guided/USBDetection", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="usb-detection">
      <button onClick={onNext}>USB weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/guided/SSHValidation", () => ({
  default: ({ onNext }: { onNext: (makePermanent: boolean) => void }) => (
    <div data-testid="ssh-validation">
      <button onClick={() => onNext(false)}>SSH weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/guided/BackupProgress", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="backup-progress">
      <button onClick={onNext}>Backup weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step2USBPreparation", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="step2-usb-preparation">
      <button onClick={onNext}>USB Prep weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step3PowerCycle", () => ({
  default: ({ onSSHDecision }: { onSSHDecision: (make: boolean) => void }) => (
    <div data-testid="step3-power-cycle">
      <button onClick={() => onSSHDecision(false)}>Power weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step4Backup", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="step4-backup">
      <button onClick={onNext}>Step4 weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step5ConfigModification", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="step5-config">
      <button onClick={onNext}>Config weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step6HostsModification", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="step6-hosts">
      <button onClick={onNext}>Hosts weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step7Verification", () => ({
  default: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="step7-verify">
      <button onClick={onNext}>Verify weiter</button>
    </div>
  ),
}));

vi.mock("../../../src/components/wizard/Step8Completion", () => ({
  default: ({ onFinish }: { onFinish: () => void }) => (
    <div data-testid="step8-completion">
      <button onClick={onFinish}>Fertig</button>
    </div>
  ),
}));

vi.mock("../../../src/api/wizard", () => ({
  enablePermanentSsh: vi.fn().mockResolvedValue({}),
}));

// ─── Test fixtures ────────────────────────────────────────────────────────────

const mockDevice: Device = {
  device_id: "ST30-001",
  name: "Living Room",
  model: "SoundTouch 30",
  ip: "192.168.1.100",
  capabilities: { airplay: false },
};

const mockDevices: Device[] = [mockDevice];

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("SetupWizard V2 (pages/SetupWizard)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Empty State ─────────────────────────────────────────────────────────────

  describe("Empty State", () => {
    it("shows empty state message when no devices provided", () => {
      render(<SetupWizard devices={[]} />);
      expect(screen.getByText("Keine Geräte gefunden")).toBeInTheDocument();
    });

    it("shows back-to-home button in empty state", () => {
      render(<SetupWizard devices={[]} />);
      expect(
        screen.getByRole("button", { name: /zurück zur startseite/i })
      ).toBeInTheDocument();
    });

    it("does not render ModeSelector in empty state", () => {
      render(<SetupWizard devices={[]} />);
      expect(screen.queryByTestId("mode-selector")).not.toBeInTheDocument();
    });
  });

  // ── Mode Selection ──────────────────────────────────────────────────────────

  describe("Mode Selection", () => {
    it("renders ModeSelector when devices are available", () => {
      render(<SetupWizard devices={mockDevices} />);
      expect(screen.getByTestId("mode-selector")).toBeInTheDocument();
    });

    it("does not show PHASE 1 DEMO banner in production/test mode", () => {
      render(<SetupWizard devices={mockDevices} />);
      // Banner is gated behind import.meta.env.DEV — not shown in test/production builds
      expect(screen.queryByText(/PHASE 1 DEMO/)).not.toBeInTheDocument();
    });

    it("does not show ProgressTracker in mode-select state", () => {
      render(<SetupWizard devices={mockDevices} />);
      expect(screen.queryByTestId("progress-tracker")).not.toBeInTheDocument();
    });
  });

  // ── Guided Mode ─────────────────────────────────────────────────────────────

  describe("Guided Mode", () => {
    it("shows ProgressTracker and USB step after guided mode selected", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /guided/i }));
      await waitFor(() => {
        expect(screen.getByTestId("progress-tracker")).toBeInTheDocument();
        expect(screen.getByTestId("usb-detection")).toBeInTheDocument();
      });
    });

    it("ProgressTracker starts at step 1 in guided mode", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /guided/i }));
      await waitFor(() => {
        expect(screen.getByText("Step 1")).toBeInTheDocument();
      });
    });

    it("advances from USB to SSH step", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /guided/i }));
      await waitFor(() => expect(screen.getByTestId("usb-detection")).toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: /usb weiter/i }));
      await waitFor(() => {
        expect(screen.getByTestId("ssh-validation")).toBeInTheDocument();
      });
    });

    it("advances from SSH to Backup step", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /guided/i }));
      await waitFor(() => expect(screen.getByTestId("usb-detection")).toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: /usb weiter/i }));
      await waitFor(() => expect(screen.getByTestId("ssh-validation")).toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: /ssh weiter/i }));
      await waitFor(() => {
        expect(screen.getByTestId("backup-progress")).toBeInTheDocument();
      });
    });

    it("shows DeviceInfoHeader during guided mode", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /guided/i }));
      await waitFor(() => {
        expect(screen.getByTestId("device-info-header")).toBeInTheDocument();
        expect(screen.getByText("Living Room")).toBeInTheDocument();
      });
    });
  });

  // ── Manual Mode ─────────────────────────────────────────────────────────────

  describe("Manual Mode", () => {
    it("shows ProgressTracker and USB Preparation step after manual mode selected", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /manual/i }));
      await waitFor(() => {
        expect(screen.getByTestId("progress-tracker")).toBeInTheDocument();
        expect(screen.getByTestId("step2-usb-preparation")).toBeInTheDocument();
      });
    });

    it("advances from USB Preparation to Power Cycle step", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /manual/i }));
      await waitFor(() =>
        expect(screen.getByTestId("step2-usb-preparation")).toBeInTheDocument()
      );
      fireEvent.click(screen.getByRole("button", { name: /usb prep weiter/i }));
      await waitFor(() => {
        expect(screen.getByTestId("step3-power-cycle")).toBeInTheDocument();
      });
    });

    it("advances from Power Cycle to Backup step", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /manual/i }));
      await waitFor(() =>
        expect(screen.getByTestId("step2-usb-preparation")).toBeInTheDocument()
      );
      fireEvent.click(screen.getByRole("button", { name: /usb prep weiter/i }));
      await waitFor(() => expect(screen.getByTestId("step3-power-cycle")).toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: /power weiter/i }));
      await waitFor(() => {
        expect(screen.getByTestId("step4-backup")).toBeInTheDocument();
      });
    });

    it("shows DeviceInfoHeader during manual mode", async () => {
      render(<SetupWizard devices={mockDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /manual/i }));
      await waitFor(() => {
        expect(screen.getByTestId("device-info-header")).toBeInTheDocument();
        expect(screen.getByText("Living Room")).toBeInTheDocument();
      });
    });
  });

  // ── Device Auto-Selection ───────────────────────────────────────────────────

  describe("Device Auto-Selection", () => {
    it("auto-selects first device when URL has no deviceId parameter", async () => {
      const multipleDevices: Device[] = [
        { ...mockDevice, device_id: "ST30-001", name: "Living Room" },
        { ...mockDevice, device_id: "ST30-002", name: "Bedroom" },
      ];
      render(<SetupWizard devices={multipleDevices} />);
      fireEvent.click(screen.getByRole("button", { name: /guided/i }));
      await waitFor(() => {
        expect(screen.getByTestId("device-info-header")).toBeInTheDocument();
        expect(screen.getByText("Living Room")).toBeInTheDocument();
      });
    });
  });
});
