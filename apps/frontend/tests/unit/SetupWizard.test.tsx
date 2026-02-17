import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SetupWizard from "../../src/components/SetupWizard";
import * as setupApi from "../../src/api/setup";

// Mock the setup API
vi.mock("../../src/api/setup", () => ({
  getModelInstructions: vi.fn(),
  checkConnectivity: vi.fn(),
  startSetup: vi.fn(),
  getSetupStatus: vi.fn(),
  STEP_LABELS: {
    usb_insert: "USB-Stick einstecken",
    device_reboot: "Gerät neustarten",
    ssh_connect: "SSH verbinden",
    ssh_persist: "SSH dauerhaft aktivieren",
    config_backup: "Konfiguration sichern",
    config_modify: "Konfiguration ändern",
    verify: "Verifizieren",
    complete: "Abgeschlossen",
  },
  calculateProgress: vi.fn().mockReturnValue(50),
}));

describe("SetupWizard Component", () => {
  const mockOnComplete = vi.fn();
  const mockOnCancel = vi.fn();
  const defaultProps = {
    deviceId: "DEVICE123",
    deviceName: "Living Room Speaker",
    model: "SoundTouch 30",
    ip: "192.168.1.100",
    onComplete: mockOnComplete,
    onCancel: mockOnCancel,
  };

  const mockInstructions: setupApi.ModelInstructions = {
    model_name: "SoundTouch 30",
    display_name: "Bose SoundTouch 30 Series III",
    usb_port_type: "micro-usb",
    usb_port_location: "Rückseite, beschriftet 'SETUP'",
    adapter_needed: true,
    adapter_recommendation: "USB-A auf Micro-USB OTG Adapter (~3€)",
    notes: ["Gerät muss eingeschaltet sein", "WLAN muss verbunden sein"],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (setupApi.getModelInstructions as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockInstructions
    );
    (setupApi.checkConnectivity as ReturnType<typeof vi.fn>).mockResolvedValue({
      ip: "192.168.1.100",
      ssh_available: true,
      telnet_available: false,
      ready_for_setup: true,
    });
    (setupApi.startSetup as ReturnType<typeof vi.fn>).mockResolvedValue({ success: true });
    (setupApi.getSetupStatus as ReturnType<typeof vi.fn>).mockResolvedValue(null);
  });

  describe("Intro Step", () => {
    it("renders intro step by default", async () => {
      render(<SetupWizard {...defaultProps} />);

      // Wait for async instructions to load
      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      expect(screen.getByText("Gerät einrichten")).toBeInTheDocument();
      expect(screen.getByText("Living Room Speaker")).toBeInTheDocument();
    });

    it("displays device information", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      expect(screen.getByText("192.168.1.100")).toBeInTheDocument();
    });

    it("shows what will be done", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      expect(screen.getByText("Was wird gemacht?")).toBeInTheDocument();
      expect(screen.getByText(/SSH-Zugang zum Gerät herstellen/)).toBeInTheDocument();
    });

    it("has cancel button that calls onCancel", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      const cancelButton = screen.getByRole("button", { name: /abbrechen/i });
      fireEvent.click(cancelButton);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it("has setup start button that advances to USB step", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      const startButton = screen.getByRole("button", { name: /setup starten/i });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });
    });
  });

  describe("USB Step", () => {
    it("shows USB port location instructions", async () => {
      render(<SetupWizard {...defaultProps} />);

      // Wait for instructions to load then navigate
      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText(/USB-Port Position/)).toBeInTheDocument();
        expect(screen.getByText(/Rückseite, beschriftet/)).toBeInTheDocument();
      });
    });

    it("shows adapter recommendation when needed", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText(/Adapter benötigt/)).toBeInTheDocument();
        expect(screen.getByText(/USB-A auf Micro-USB OTG Adapter/)).toBeInTheDocument();
      });
    });

    it("shows model-specific notes", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText(/Hinweise/)).toBeInTheDocument();
        expect(screen.getByText(/Gerät muss eingeschaltet sein/)).toBeInTheDocument();
        expect(screen.getByText(/WLAN muss verbunden sein/)).toBeInTheDocument();
      });
    });

    it("hides adapter section when not needed", async () => {
      const noAdapterInstructions = { ...mockInstructions, adapter_needed: false };
      (setupApi.getModelInstructions as ReturnType<typeof vi.fn>).mockResolvedValue(
        noAdapterInstructions
      );

      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      expect(screen.queryByText(/Adapter benötigt/)).not.toBeInTheDocument();
    });
  });

  describe("Connectivity Check", () => {
    it("shows error when SSH is not available", async () => {
      (setupApi.checkConnectivity as ReturnType<typeof vi.fn>).mockResolvedValue({
        ip: "192.168.1.100",
        ssh_available: false,
        telnet_available: false,
        ready_for_setup: false,
      });

      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      // Navigate to USB step
      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      // Click connectivity check button
      const checkButton = screen.getByRole("button", { name: /verbindung prüfen/i });
      fireEvent.click(checkButton);

      await waitFor(() => {
        expect(screen.getByText(/SSH nicht verfügbar/)).toBeInTheDocument();
      });
    });

    it("handles connectivity check API error", async () => {
      (setupApi.checkConnectivity as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error("Network error")
      );

      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      const checkButton = screen.getByRole("button", { name: /verbindung prüfen/i });
      fireEvent.click(checkButton);

      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
      });
    });

    it("advances to check step when SSH is available", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      const checkButton = screen.getByRole("button", { name: /verbindung prüfen/i });
      fireEvent.click(checkButton);

      await waitFor(() => {
        expect(screen.getByText("Bereit zum Konfigurieren")).toBeInTheDocument();
      });
    });
  });

  describe("Setup Running", () => {
    it("starts setup and shows running step", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      // Navigate through steps
      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      const checkButton = screen.getByRole("button", { name: /verbindung prüfen/i });
      fireEvent.click(checkButton);

      await waitFor(() => {
        expect(screen.getByText("Bereit zum Konfigurieren")).toBeInTheDocument();
      });

      const startSetupButton = screen.getByRole("button", { name: /konfiguration starten/i });
      fireEvent.click(startSetupButton);

      await waitFor(() => {
        expect(setupApi.startSetup).toHaveBeenCalledWith("DEVICE123", "192.168.1.100", "SoundTouch 30");
      });
    });

    it("handles setup start error by staying on check step", async () => {
      (setupApi.startSetup as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error("Setup failed to start")
      );

      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      const checkButton = screen.getByRole("button", { name: /verbindung prüfen/i });
      fireEvent.click(checkButton);

      await waitFor(() => {
        expect(screen.getByText("Bereit zum Konfigurieren")).toBeInTheDocument();
      });

      const startSetupButton = screen.getByRole("button", { name: /konfiguration starten/i });
      fireEvent.click(startSetupButton);

      // On error, component should stay on check step (not advance to running)
      await waitFor(() => {
        expect(setupApi.startSetup).toHaveBeenCalled();
      });

      // Still displays check step content, not running
      expect(screen.getByText("Bereit zum Konfigurieren")).toBeInTheDocument();
      expect(screen.queryByText("Konfiguration läuft...")).not.toBeInTheDocument();
    });
  });

  describe("Instructions Loading", () => {
    it("uses default instructions on API error", async () => {
      // Suppress expected console error from component
      const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      (setupApi.getModelInstructions as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error("API error")
      );

      render(<SetupWizard {...defaultProps} />);

      // Navigate to USB step - should still work with default instructions
      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalled();
      });

      fireEvent.click(screen.getByRole("button", { name: /setup starten/i }));

      // Should still render with default instructions
      await waitFor(() => {
        expect(screen.getByText("USB-Stick vorbereiten")).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it("loads model instructions on mount", async () => {
      render(<SetupWizard {...defaultProps} />);

      await waitFor(() => {
        expect(setupApi.getModelInstructions).toHaveBeenCalledWith("SoundTouch 30");
      });
    });
  });
});
