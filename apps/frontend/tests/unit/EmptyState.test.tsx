/**
 * Tests for EmptyState.tsx
 *
 * User Story: "Als neuer User möchte ich durch das Setup geführt werden"
 *
 * Focus: Functional tests for initial device discovery
 * - Display welcome message and setup steps
 * - Auto-discovery flow (SSE via useDiscoveryStream)
 * - Manual IP configuration modal
 * - IP validation (format, invalid IPs)
 * - Navigation after successful discovery
 * - Error handling (no devices, API errors)
 */

import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import React from "react";
import * as ToastContextModule from "../../src/contexts/ToastContext";
import { ToastProvider } from "../../src/contexts/ToastContext";
import EmptyState from "../../src/components/EmptyState";
import { QueryWrapper } from "../utils/reactQueryTestUtils";

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock useDiscoveryStream – control SSE state without real EventSource
const mockStartDiscovery = vi.fn();
const mockCancelDiscovery = vi.fn();
let mockDiscoveryState = {
  isDiscovering: false,
  devicesFound: [] as { device_id: string; name: string }[],
  completed: false,
  error: null as string | null,
  stats: { discovered: 0, synced: 0, failed: 0 },
  startDiscovery: mockStartDiscovery,
  cancelDiscovery: mockCancelDiscovery,
};

vi.mock("../../src/hooks/useDiscoveryStream", () => ({
  useDiscoveryStream: () => mockDiscoveryState,
}));

interface FetchMockOverrides {
  manualIps?: string[];
}

let mockFetch: Mock;

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <QueryWrapper>
      <BrowserRouter>
        <ToastProvider>{component}</ToastProvider>
      </BrowserRouter>
    </QueryWrapper>
  );
};

// Helper to create fetch mock that handles settings/devices endpoints
const createFetchMock = (overrides: FetchMockOverrides = {}) => {
  const manualIps = overrides.manualIps ?? [];

  return vi.fn((url: string) => {
    if (url.includes("/api/settings/manual-ips")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ ips: manualIps }),
      });
    }
    if (url.includes("/api/devices")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ devices: [] }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({}),
    });
  });
};

describe("EmptyState Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset discovery mock state
    mockDiscoveryState = {
      isDiscovering: false,
      devicesFound: [],
      completed: false,
      error: null,
      stats: { discovered: 0, synced: 0, failed: 0 },
      startDiscovery: mockStartDiscovery,
      cancelDiscovery: mockCancelDiscovery,
    };
    // Default fetch mock for settings/devices endpoints
    mockFetch = createFetchMock();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("Welcome & Setup Steps", () => {
    it("should display welcome message and setup instructions", () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState />);

      expect(screen.getByText("Welcome to OpenCloudTouch")).toBeInTheDocument();
      expect(screen.getByText("No devices found yet.")).toBeInTheDocument();

      // Setup steps
      expect(screen.getByText("Turn on devices")).toBeInTheDocument();
      expect(screen.getByText("Search for devices")).toBeInTheDocument();
      expect(screen.getByText("Manage presets")).toBeInTheDocument();
    });

    it("should show discovery button", () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState />);

      const discoverButton = screen.getByRole("button", { name: /Search for devices now/i });
      expect(discoverButton).toBeInTheDocument();
      expect(discoverButton).not.toBeDisabled();
    });
  });

  describe("Auto-Discovery Flow", () => {
    it("should call startDiscovery when clicking discover button", async () => {
      renderWithProviders(<EmptyState />);

      const discoverButton = screen.getByRole("button", { name: /Search for devices now/i });
      fireEvent.click(discoverButton);

      expect(mockStartDiscovery).toHaveBeenCalledTimes(1);
    });

    it("should navigate to dashboard after successful discovery", async () => {
      // Render with discovery already completed and devices found
      mockDiscoveryState = {
        ...mockDiscoveryState,
        completed: true,
        devicesFound: [{ device_id: "abc123", name: "Wohnzimmer" }],
      };

      renderWithProviders(<EmptyState />);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/");
      });

      // BUG-15: navigate should only be called once, not in a loop
      const navigateCalls = (mockNavigate as Mock).mock.calls.length;
      expect(navigateCalls).toBe(1);
    });

    it("should show discovering state when isDiscovering is true", async () => {
      mockDiscoveryState = {
        ...mockDiscoveryState,
        isDiscovering: true,
      };

      renderWithProviders(<EmptyState />);

      // Button should be disabled while discovering
      const discoverButton = screen.getByRole("button", { name: /Searching.../i });
      expect(discoverButton).toBeDisabled();
    });

  });

  describe("Manual IP Configuration", () => {
    it("should open modal when clicking manual add button", async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState />);

      // Expand help section
      const helpSummary = screen.getByText("No devices found?");
      fireEvent.click(helpSummary);

      // Click manual add button (using text since component uses data-test not data-testid)
      const manualAddButton = screen.getByRole("button", { name: /Add device IPs manually/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByText("Manual IP Configuration")).toBeInTheDocument();
      });
    });

    it("should validate IP addresses and show error for invalid format", async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState />);

      // Open modal
      const helpSummary = screen.getByText("No devices found?");
      fireEvent.click(helpSummary);
      const manualAddButton = screen.getByRole("button", { name: /Add device IPs manually/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByRole("textbox")).toBeInTheDocument();
      });

      // Enter invalid IP
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, { target: { value: "invalid-ip\n999.999.999.999" } });

      // Save
      const saveButton = screen.getByRole("button", { name: /Save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getAllByText(/Invalid format:/).length).toBeGreaterThan(0);
      });
    });

    it("should save valid IP addresses successfully", async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState />);

      // Open modal
      const helpSummary = screen.getByText("No devices found?");
      fireEvent.click(helpSummary);
      const manualAddButton = screen.getByRole("button", { name: /Add device IPs manually/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByRole("textbox")).toBeInTheDocument();
      });

      // Enter valid IPs
      const textarea = screen.getByRole("textbox");
      fireEvent.change(textarea, {
        target: { value: "192.168.1.100\n192.168.1.101" },
      });

      // Save
      const saveButton = screen.getByRole("button", { name: /Save/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith("/api/settings/manual-ips", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ips: ["192.168.1.100", "192.168.1.101"] }),
        });
      });

      // Success message
      await waitFor(() => {
        expect(screen.getByText("IP-Adressen gespeichert!")).toBeInTheDocument();
      });
    });

    it("should close modal when clicking cancel button", async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState />);

      // Open modal
      const helpSummary = screen.getByText("No devices found?");
      fireEvent.click(helpSummary);
      const manualAddButton = screen.getByRole("button", { name: /Add device IPs manually/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByText("Manual IP Configuration")).toBeInTheDocument();
      });

      // Click cancel
      const cancelButton = screen.getByRole("button", { name: /Cancel/i });
      fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByText("Manual IP Configuration")).not.toBeInTheDocument();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // BUG-16: 409 Discovery Conflict should show INFO toast not ERROR toast
  // ---------------------------------------------------------------------------

  describe("BUG-16: 409 Conflict → info toast (not error)", () => {
    it("shows info toast when discovery is already in progress", async () => {
      const mockShowToast = vi.fn();
      const useToastSpy = vi.spyOn(ToastContextModule, "useToast").mockReturnValue({
        show: mockShowToast,
        hide: vi.fn(),
      });

      // Set error state to simulate 409 conflict response
      mockDiscoveryState.error = "Discovery already in progress";
      mockDiscoveryState.isDiscovering = false;

      renderWithProviders(<EmptyState />);

      // The useEffect fires with discoveryError and must call showToast with
      // the "info" type (not "error") — this is BUG-16's actual assertion,
      // not just "the component didn't crash".
      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith(
          "Device search already running. Please wait...",
          "info"
        );
      });

      // vi.clearAllMocks() (in this file's beforeEach and the global
      // afterEach) clears call history but not the mocked implementation, so
      // restore it explicitly to avoid leaking a fake useToast into later
      // tests that rely on the real ToastProvider.
      useToastSpy.mockRestore();
    });
  });

  // ---------------------------------------------------------------------------
  // BUG-31: showToast() must NOT be called synchronously during render
  // ---------------------------------------------------------------------------

  describe("BUG-31: showToast must be in useEffect, not render phase", () => {
    it("does not throw React warning from synchronous showToast in render", () => {
      // BUG-31: old code called showToast() synchronously in render:
      //   if (error?.statusCode === 409) { showToast("...", "info"); }
      // This caused: "Warning: Cannot update a component (ToastProvider) while
      // rendering a different component (EmptyState)"
      // Fix: moved to useEffect([error])

      mockDiscoveryState.error = "Discovery already in progress";

      // Capture console.error to detect React warnings
      const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      expect(() => {
        renderWithProviders(<EmptyState />);
      }).not.toThrow();

      // Verify no "Cannot update a component while rendering" React error
      const reactRenderWarnings = consoleSpy.mock.calls.filter(
        (args) =>
          typeof args[0] === "string" &&
          args[0].includes("Cannot update a component") &&
          args[0].includes("while rendering")
      );
      expect(reactRenderWarnings.length).toBe(0);

      consoleSpy.mockRestore();
    });

  });
});
