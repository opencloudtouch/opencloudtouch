/**
 * Tests for Firmware.tsx
 *
 * User Story: "Als User möchte ich Firmware-Status meiner Geräte sehen"
 *
 * Focus: Functional tests for firmware management UI
 * - Display device firmware information
 * - Firmware status detection (up-to-date vs. update-available)
 * - Multi-device overview
 * - Upload UI (currently disabled)
 * - Warning messages for experimental features
 * - Edge cases: no devices, unknown firmware versions
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Firmware from "../../src/pages/Firmware";

describe("Firmware Page", () => {
  const mockDevices = [
    {
      device_id: "AABBCC123456",
      name: "Living Room",
      model: "SoundTouch 30",
      firmware: "1.0.12.0",
      ip_address: "192.168.1.101",
    },
    {
      device_id: "DDEEFF789012",
      name: "Küche",
      model: "SoundTouch 10",
      firmware: "1.0.8.0", // Older version
      ip_address: "192.168.1.102",
    },
    {
      device_id: "GGHHII345678",
      name: "Bad",
      model: "SoundTouch 300",
      firmware: "1.0.15.0",
      ip_address: "192.168.1.103",
    },
  ];

  describe("Device Firmware Display", () => {
    it("should show current device firmware information", () => {
      render(<Firmware devices={mockDevices} />);

      // Current device section
      expect(screen.getByText("Current Device")).toBeInTheDocument();
      expect(screen.getAllByText("Living Room")[0]).toBeInTheDocument(); // Also in "All Devices"
      expect(screen.getAllByText("SoundTouch 30")[0]).toBeInTheDocument();
      expect(screen.getAllByText("1.0.12")[0]).toBeInTheDocument(); // Parsed version
    });

    it("should display firmware status badge for current device", () => {
      render(<Firmware devices={mockDevices} />);

      // Current device has firmware 1.0.12 → up-to-date
      const statusBadge = screen.getByText(/✓ Up to date/);
      expect(statusBadge).toBeInTheDocument();
      expect(statusBadge).toHaveClass("up-to-date");
    });

    it("should show all devices in overview list", () => {
      render(<Firmware devices={mockDevices} />);

      // All devices section
      expect(screen.getByText("All Devices")).toBeInTheDocument();
      expect(screen.getAllByText("Living Room").length).toBeGreaterThanOrEqual(2); // Current + All
      expect(screen.getByText("Küche")).toBeInTheDocument();
      expect(screen.getByText("Bad")).toBeInTheDocument();
    });

    it("should display firmware version for each device in list", () => {
      render(<Firmware devices={mockDevices} />);

      // Parsed versions should be shown
      const versions = screen.getAllByText(/1\.0\.\d+/);
      expect(versions.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe("Firmware Status Detection", () => {
    it("should mark devices with old firmware as update-available", () => {
      render(<Firmware devices={mockDevices} />);

      // Küche has firmware 1.0.8 → update-available (< 1.0.12)
      // Find all status icons
      const warningIcons = screen.getAllByText("⚠️");
      expect(warningIcons.length).toBeGreaterThanOrEqual(1);
    });

    it("should mark devices with current firmware as up-to-date", () => {
      render(<Firmware devices={mockDevices} />);

      // Living Room (1.0.12) and Bad (1.0.15) should be up-to-date
      const checkIcons = screen.getAllByText("✓");
      expect(checkIcons.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("Upload UI (Disabled)", () => {
    it("should show upload section with disabled state", () => {
      render(<Firmware devices={mockDevices} />);

      expect(screen.getByText("Upload Firmware")).toBeInTheDocument();
      expect(screen.getByText(/Firmware upload is currently not available/)).toBeInTheDocument();

      const uploadButton = screen.getByRole("button", { name: /Select firmware/i });
      expect(uploadButton).toBeDisabled();
    });

    it("should display warning about experimental feature", () => {
      render(<Firmware devices={mockDevices} />);

      expect(screen.getByText("Experimental Feature")).toBeInTheDocument();
      expect(screen.getByText(/Firmware updates are experimental/)).toBeInTheDocument();
      expect(screen.getByText(/official firmware files from your/)).toBeInTheDocument();
    });

    it("should display firmware update hints", () => {
      render(<Firmware devices={mockDevices} />);

      expect(screen.getByText("Firmware Notes")).toBeInTheDocument();
      expect(screen.getByText(/only be performed if there are problems/)).toBeInTheDocument();
      expect(screen.getByText(/5–10 minutes/)).toBeInTheDocument();
      expect(screen.getByText(/restarts automatically/)).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should show empty state when no devices available", () => {
      render(<Firmware devices={[]} />);

      expect(screen.getByText("No devices found")).toBeInTheDocument();
      expect(screen.queryByText("Current Device")).not.toBeInTheDocument();
    });

    it("should handle device without firmware version", () => {
      const deviceWithoutFirmware = [
        {
          device_id: "XXYYZZAABBCC",
          name: "Unknown Device",
          model: "SoundTouch 20",
          ip_address: "192.168.1.104",
        },
      ];

      render(<Firmware devices={deviceWithoutFirmware} />);

      expect(screen.getAllByText("Unknown Device").length).toBeGreaterThanOrEqual(2); // Current + All
      expect(screen.getAllByText("Unknown").length).toBeGreaterThanOrEqual(1); // parseFirmwareVersion fallback
    });

    it("should handle device with unknown model", () => {
      const deviceWithoutModel = [
        {
          device_id: "AABBCC123456",
          name: "Schlafzimmer",
          firmware: "1.0.12.0",
          ip_address: "192.168.1.105",
        },
      ];

      render(<Firmware devices={deviceWithoutModel} />);

      expect(screen.getAllByText("Schlafzimmer").length).toBeGreaterThanOrEqual(2); // Current + All
      expect(screen.getByText("Unknown Model")).toBeInTheDocument();
    });
  });
});
