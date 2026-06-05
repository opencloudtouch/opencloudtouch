/**
 * Tests for DeviceNameEditor component.
 *
 * Covers: display, edit mode, save, cancel, validation, error handling.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeviceNameEditor from "../../src/components/DeviceNameEditor";

// Mock i18n
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "deviceRename.clickToEdit": "Click to edit",
        "deviceRename.inputLabel": "Device name",
        "deviceRename.tooLong": "Name too long",
        "deviceRename.failed": "Rename failed",
      };
      return map[key] ?? key;
    },
  }),
}));

// Mock TanStack Query
const mockInvalidateQueries = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

// Mock API
const mockRenameDevice = vi.fn();
vi.mock("../../src/api/devices", () => ({
  renameDevice: (...args: unknown[]) => mockRenameDevice(...args),
}));

describe("DeviceNameEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders device name as heading", () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("data-test", "device-name");
  });

  it("enters edit mode on click", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));

    expect(screen.getByLabelText("Device name")).toBeInTheDocument();
    expect(screen.getByLabelText("Device name")).toHaveValue("Living Room");
  });

  it("enters edit mode on Enter key", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    fireEvent.keyDown(screen.getByRole("button"), { key: "Enter" });

    expect(screen.getByLabelText("Device name")).toBeInTheDocument();
  });

  it("submits on Enter key and calls API", async () => {
    mockRenameDevice.mockResolvedValue({
      device_id: "ABC123",
      name: "Kitchen",
      previous_name: "Living Room",
    });
    const onRenamed = vi.fn();

    render(
      <DeviceNameEditor deviceId="ABC123" name="Living Room" onRenamed={onRenamed} />
    );

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Kitchen");
    // Prevent blur from firing cancel before Enter
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(mockRenameDevice).toHaveBeenCalledWith("ABC123", "Kitchen");
    });

    await waitFor(() => {
      expect(onRenamed).toHaveBeenCalledWith("Kitchen");
    });

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ["devices"] });
  });

  it("cancels on Escape key and reverts value", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Changed");
    fireEvent.keyDown(input, { key: "Escape" });

    // Should be back to display mode
    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("cancels when unchanged name is submitted", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    fireEvent.keyDown(input, { key: "Enter" });

    // Same name = cancel, no API call
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("shows validation error for names exceeding 30 chars", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    // The input has maxLength=30, so type a long name and validate via save
    // We need to set value directly since maxLength prevents typing
    fireEvent.change(input, { target: { value: "A".repeat(31) } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("Name too long")).toBeInTheDocument();
    });

    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("shows error message when API call fails", async () => {
    mockRenameDevice.mockRejectedValue(new Error("Network error"));

    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "NewName");
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("Rename failed")).toBeInTheDocument();
    });
  });

  it("disables input while saving", async () => {
    // Never-resolving promise to keep saving state
    mockRenameDevice.mockReturnValue(new Promise(() => {}));

    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "NewName");
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByLabelText("Device name")).toBeDisabled();
    });
  });

  // REGRESSION TESTS for onBlur auto-save (added 2026-06-05)
  it("auto-saves on blur when value changed", async () => {
    mockRenameDevice.mockResolvedValue({
      device_id: "ABC123",
      name: "Kitchen",
      previous_name: "Living Room",
    });
    const onRenamed = vi.fn();

    render(
      <DeviceNameEditor deviceId="ABC123" name="Living Room" onRenamed={onRenamed} />
    );

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Kitchen");
    
    // Blur without pressing Enter should trigger save
    fireEvent.blur(input);

    await waitFor(() => {
      expect(mockRenameDevice).toHaveBeenCalledWith("ABC123", "Kitchen");
    });

    await waitFor(() => {
      expect(onRenamed).toHaveBeenCalledWith("Kitchen");
    });
  });

  it("cancels on blur when value unchanged", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    
    // Blur without changing value should cancel
    fireEvent.blur(input);

    // Should be back to display mode, no API call
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("cancels on blur when value is empty", async () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    
    // Blur with empty value should cancel
    fireEvent.blur(input);

    // Should be back to display mode with original name, no API call
    await waitFor(() => {
      expect(screen.getByText("Living Room")).toBeInTheDocument();
    });
    expect(mockRenameDevice).not.toHaveBeenCalled();
  });

  it("does not trigger blur handler while saving", async () => {
    // Slow-resolving promise to test saving state
    mockRenameDevice.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ name: "Kitchen" }), 100))
    );

    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    await userEvent.click(screen.getByText("Living Room"));
    const input = screen.getByLabelText("Device name");
    await userEvent.clear(input);
    await userEvent.type(input, "Kitchen");
    fireEvent.keyDown(input, { key: "Enter" });

    // Try to blur while saving
    fireEvent.blur(input);

    // Should only call API once (from Enter, not from blur)
    await waitFor(() => {
      expect(mockRenameDevice).toHaveBeenCalledTimes(1);
    });
  });

  // REGRESSION TEST for centered layout with placeholder icon (added 2026-06-05)
  it("renders placeholder icon for balanced centering", () => {
    render(<DeviceNameEditor deviceId="ABC123" name="Living Room" />);

    const heading = screen.getByRole("button");
    const icons = heading.querySelectorAll('span[aria-hidden="true"]');
    
    // Should have 2 icons: placeholder (invisible) + edit icon (visible on hover)
    expect(icons).toHaveLength(2);
    expect(icons[0]).toHaveClass("device-name-placeholder-icon");
    expect(icons[1]).toHaveClass("device-name-edit-icon");
  });
});
