import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import Diagnostics from "./Diagnostics";
import type { DiagnosticsResponse } from "../api/diagnostics";

// Mock getDiagnostics
vi.mock("../api/diagnostics", () => ({
  getDiagnostics: vi.fn(),
}));

// Mock downloadDiagnostics
vi.mock("../api/bugReport", () => ({
  downloadDiagnostics: vi.fn(),
}));

// Mock logBuffer
vi.mock("../utils/logBuffer", () => ({
  getLogEntries: vi.fn(() => []),
}));

// Mock ToastContext
const mockShowToast = vi.fn();
vi.mock("../contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShowToast }),
}));

import { getDiagnostics } from "../api/diagnostics";
import { downloadDiagnostics } from "../api/bugReport";

const mockedGetDiagnostics = vi.mocked(getDiagnostics);
const mockedDownloadDiagnostics = vi.mocked(downloadDiagnostics);

const MOCK_RESPONSE: DiagnosticsResponse = {
  server: {
    version: "1.2.3",
    python_version: "3.11.9",
    platform: "Linux-6.1.0",
    discovery_enabled: true,
    mock_mode: false,
    log_level: "INFO",
    manual_device_ips: 2,
    timestamp: "2026-06-01T12:00:00+00:00",
  },
  devices: [
    {
      device_id: "AABBCCDDEEFF",
      name: "Living Room",
      model: "SoundTouch 30",
      ip: "192.168.1.100",
      firmware_version: "24.0.5",
      setup_status: "complete",
      last_seen: new Date(Date.now() - 60_000).toISOString(), // 1 min ago → green
      setup_completed_at: "2026-01-01T00:00:00+00:00",
      ssh_permanent: true,
    },
  ],
  db_stats: { devices: 1, presets: 6 },
};

describe("Diagnostics Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", () => {
    mockedGetDiagnostics.mockReturnValue(new Promise(() => {})); // never resolves
    render(<Diagnostics />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders error state", async () => {
    mockedGetDiagnostics.mockRejectedValue(new Error("Network failure"));
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Network failure")).toBeInTheDocument();
    });
  });

  it("renders server info after loading", async () => {
    mockedGetDiagnostics.mockResolvedValue(MOCK_RESPONSE);
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("1.2.3")).toBeInTheDocument();
    });
    expect(screen.getByText("3.11.9")).toBeInTheDocument();
    expect(screen.getByText("Linux-6.1.0")).toBeInTheDocument();
    expect(screen.getByText("INFO")).toBeInTheDocument();
  });

  it("renders device cards", async () => {
    mockedGetDiagnostics.mockResolvedValue(MOCK_RESPONSE);
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    expect(screen.getByText("SoundTouch 30")).toBeInTheDocument();
    expect(screen.getByText("192.168.1.100")).toBeInTheDocument();
    expect(screen.getByText("24.0.5")).toBeInTheDocument();
  });

  it("renders db stats", async () => {
    mockedGetDiagnostics.mockResolvedValue(MOCK_RESPONSE);
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument(); // devices count
    });
    expect(screen.getByText("6")).toBeInTheDocument(); // presets count
  });

  it("shows no-devices message when device list is empty", async () => {
    mockedGetDiagnostics.mockResolvedValue({
      ...MOCK_RESPONSE,
      devices: [],
      db_stats: { devices: 0, presets: 0 },
    });
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("No devices found")).toBeInTheDocument();
    });
  });

  it("renders StatusDot with green status for recently seen device", async () => {
    mockedGetDiagnostics.mockResolvedValue(MOCK_RESPONSE);
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    // StatusDot renders <span aria-label="green"> — multiple may exist (server + device)
    const greenDots = screen.getAllByLabelText("green");
    expect(greenDots.length).toBeGreaterThan(0);
    expect(greenDots[0]).toHaveClass("status-dot", "status-green");
  });

  it("renders StatusDot with red status for device with null last_seen", async () => {
    mockedGetDiagnostics.mockResolvedValue({
      ...MOCK_RESPONSE,
      devices: [{ ...MOCK_RESPONSE.devices[0], last_seen: null }],
    });
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    // Device status dot should be red (null last_seen)
    const dots = screen.getAllByLabelText("red");
    expect(dots.length).toBeGreaterThan(0);
    expect(dots[0]).toHaveClass("status-dot", "status-red");
  });

  it("renders StatusDot with yellow for device seen 10 min ago", async () => {
    mockedGetDiagnostics.mockResolvedValue({
      ...MOCK_RESPONSE,
      devices: [
        {
          ...MOCK_RESPONSE.devices[0],
          last_seen: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
        },
      ],
    });
    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    const yellowDot = screen.getByLabelText("yellow");
    expect(yellowDot).toHaveClass("status-dot", "status-yellow");
  });

  it("calls downloadDiagnostics when download button is clicked", async () => {
    mockedGetDiagnostics.mockResolvedValue(MOCK_RESPONSE);
    mockedDownloadDiagnostics.mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Download Support Bundle")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Download Support Bundle"));

    await waitFor(() => {
      expect(mockedDownloadDiagnostics).toHaveBeenCalledTimes(1);
    });
    expect(mockShowToast).toHaveBeenCalledWith(
      "Diagnostics downloaded! Attach the .log.gz file to your GitHub issue.",
      "success",
      8000
    );
  });

  it("shows error toast when download fails", async () => {
    mockedGetDiagnostics.mockResolvedValue(MOCK_RESPONSE);
    mockedDownloadDiagnostics.mockRejectedValue(new Error("Download failed"));
    const user = userEvent.setup();

    render(<Diagnostics />);
    await waitFor(() => {
      expect(screen.getByText("Download Support Bundle")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Download Support Bundle"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("Failed to download diagnostics"),
        "error",
        8000
      );
    });
  });
});
