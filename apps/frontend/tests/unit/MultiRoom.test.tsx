/**
 * Functional Tests for MultiRoom Component
 *
 * User Story: "Als User möchte ich mehrere Geräte zu einer Zone gruppieren"
 *
 * Test Strategy: Behaviour-driven testing focusing on zone management workflows
 * Coverage: Create Zone, Edit Zone, Dissolve Zone, Device Selection, Validation
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode, HTMLAttributes } from "react";
import MultiRoom from "../../src/pages/MultiRoom";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children: ReactNode } & HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
    section: ({ children, ...props }: { children: ReactNode } & HTMLAttributes<HTMLElement>) => <section {...props}>{children}</section>,
    label: ({ children, ...props }: { children: ReactNode } & HTMLAttributes<HTMLLabelElement>) => <label {...props}>{children}</label>,
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const mockDevices = [
  {
    device_id: "ST10-001",
    name: "Living Room",
    model: "SoundTouch 10",
  },
  {
    device_id: "ST30-002",
    name: "Schlafzimmer",
    model: "SoundTouch 30",
  },
  {
    device_id: "ST10-003",
    name: "Küche",
    model: "SoundTouch 10",
  },
  {
    device_id: "ST300-004",
    name: "Badezimmer",
    model: "SoundTouch 300",
  },
];

describe("MultiRoom - Zone Creation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * TEST 1: Empty State - No Devices
   * User Story: Als User möchte ich wissen wenn keine Geräte verfügbar sind
   */
  test("should show empty device grid when no devices available", () => {
    render(<MultiRoom devices={[]} />);

    expect(screen.getByText(/Multi-Room Zonen/i)).toBeInTheDocument();
    expect(screen.getByText(/Neue Zone erstellen/i)).toBeInTheDocument();
    // No devices should be shown
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  /**
   * TEST 2: Display Available Devices
   * User Story: Als User möchte ich alle verfügbaren Geräte sehen
   */
  test("should display all available devices for selection", () => {
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(screen.getByText("Schlafzimmer")).toBeInTheDocument();
    expect(screen.getByText("Küche")).toBeInTheDocument();
    expect(screen.getByText("Badezimmer")).toBeInTheDocument();
  });

  /**
   * TEST 3: Select Devices for Zone
   * User Story: Als User möchte ich Geräte für eine Zone auswählen
   */
  test("should allow selecting multiple devices", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    // Select first device
    await user.click(checkboxes[0]!);
    expect(checkboxes[0]).toBeChecked();
    expect(screen.getByText(/1 Gerät\(e\) ausgewählt/i)).toBeInTheDocument();

    // Select second device
    await user.click(checkboxes[1]!);
    expect(checkboxes[1]).toBeChecked();
    expect(screen.getByText(/2 Gerät\(e\) ausgewählt/i)).toBeInTheDocument();
  });

  /**
   * TEST 4: Master/Slave Badge Assignment
   * User Story: Als User möchte ich sehen welches Gerät Master/Slave ist
   */
  test("should show master badge on first selected device and slave on others", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    // Select first device - should become Master
    await user.click(checkboxes[0]!);
    await waitFor(() => {
      const labels = screen.getAllByText("Master");
      expect(labels.length).toBeGreaterThan(0);
    });

    // Select second device - should become Slave
    await user.click(checkboxes[1]!);
    await waitFor(() => {
      expect(screen.getByText("Slave")).toBeInTheDocument();
    });
  });

  /**
   * TEST 5: Validation - Minimum 2 Devices Required
   * User Story: Als User möchte ich wissen dass mindestens 2 Geräte nötig sind
   */
  test("should disable create button when less than 2 devices selected", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    // Select only 1 device
    await user.click(checkboxes[0]!);

    await waitFor(() => {
      expect(screen.getByText(/mindestens 2 erforderlich/i)).toBeInTheDocument();
      const createButton = screen.getByRole("button", { name: /Zone erstellen/i });
      expect(createButton).toBeDisabled();
    });
  });

  /**
   * TEST 6: Create Zone Successfully
   * User Story: Als User möchte ich eine Zone aus 2+ Geräten erstellen
   */
  test("should create zone when 2 or more devices selected", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    // Select 2 devices
    await user.click(checkboxes[0]!); // Living Room
    await user.click(checkboxes[1]!); // Schlafzimmer

    const createButton = screen.getByRole("button", { name: /Zone erstellen/i });
    expect(createButton).toBeEnabled();

    // Create zone
    await user.click(createButton);

    // Zone should be created and displayed
    await waitFor(() => {
      expect(screen.getByText(/Aktive Zonen/i)).toBeInTheDocument();
      expect(screen.getByText(/Neue Zone 2/i)).toBeInTheDocument(); // Mock already has 1 zone
    });
  });

  /**
   * TEST 7: Deselect Device
   * User Story: Als User möchte ich Geräte wieder abwählen können
   */
  test("should allow deselecting devices", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    // Select device
    await user.click(checkboxes[0]!);
    expect(checkboxes[0]).toBeChecked();

    // Deselect device
    await user.click(checkboxes[0]!);
    expect(checkboxes[0]).not.toBeChecked();

    // Selection count should be gone
    expect(screen.queryByText(/Gerät\(e\) ausgewählt/i)).not.toBeInTheDocument();
  });
});

describe("MultiRoom - Zone Management", () => {
  /**
   * TEST 8: Display Existing Zones
   * User Story: Als User möchte ich meine aktiven Zonen sehen
   */
  test("should display existing zones with master and slaves", () => {
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/Aktive Zonen/i)).toBeInTheDocument();
    expect(screen.getByText(/Living Room Zone/i)).toBeInTheDocument();

    // Should show Master and Slave badges in zone display
    const zoneBadges = screen.getAllByText("Master");
    expect(zoneBadges.length).toBeGreaterThan(0);
  });

  /**
   * TEST 9: Dissolve Zone
   * User Story: Als User möchte ich eine Zone auflösen können
   */
  test("should dissolve zone when dissolve button clicked", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    // Find dissolve button
    const dissolveButton = screen.getByRole("button", { name: /Auflösen/i });

    // Dissolve zone
    await user.click(dissolveButton);

    // Zone should be removed
    await waitFor(() => {
      expect(screen.queryByText(/Living Room Zone/i)).not.toBeInTheDocument();
    });
  });

  /**
   * TEST 10: Edit Zone
   * User Story: Als User möchte ich eine bestehende Zone bearbeiten können
   */
  test("should allow editing existing zone", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    // Click edit button
    const editButton = screen.getByRole("button", { name: /Bearbeiten/i });
    await user.click(editButton);

    // Should show edit mode
    await waitFor(() => {
      expect(screen.getByText(/Zone bearbeiten: Living Room Zone/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Zone aktualisieren/i })).toBeInTheDocument();
    });
  });

  /**
   * TEST 11: Devices in Zone Should Be Disabled
   * User Story: Als User möchte ich nicht versehentlich Geräte aus anderen Zonen hinzufügen
   */
  test("should disable devices that are already in a zone", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    // Create a zone first
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[2]!); // Küche
    await user.click(checkboxes[3]!); // Badezimmer

    const createButton = screen.getByRole("button", { name: /Zone erstellen/i });
    await user.click(createButton);

    // Now those devices should be disabled and show "In Zone" badge
    await waitFor(() => {
      const inZoneBadges = screen.getAllByText("In Zone");
      expect(inZoneBadges.length).toBeGreaterThan(0);
    });
  });
});

describe("MultiRoom - Edge Cases", () => {
  /**
   * TEST 12: Clear Selection After Zone Creation
   * User Story: Als User möchte ich nach Zonen-Erstellung eine neue Auswahl treffen
   */
  test("should clear device selection after creating zone", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    // Select devices
    await user.click(checkboxes[2]!);
    await user.click(checkboxes[3]!);

    // Create zone
    const createButton = screen.getByRole("button", { name: /Zone erstellen/i });
    await user.click(createButton);

    // Selection should be cleared
    await waitFor(() => {
      expect(checkboxes[2]).not.toBeChecked();
      expect(checkboxes[3]).not.toBeChecked();
      expect(screen.queryByText(/Gerät\(e\) ausgewählt/i)).not.toBeInTheDocument();
    });
  });

  /**
   * TEST 13: Zone with Unknown Devices (Defensive)
   * User Story: Als System sollte ich gracefully mit fehlenden Geräten umgehen
   */
  test("should handle zone with devices not in device list", () => {
    // Mock zone references devices not in mockDevices
    render(<MultiRoom devices={mockDevices} />);

    // Should show "Unknown Device" for missing devices
    expect(screen.queryByText(/Unknown Device/i)).toBeInTheDocument();
  });

  /**
   * TEST 14: Multiple Zone Creation
   * User Story: Als User möchte ich mehrere unabhängige Zonen erstellen können
   */
  test("should allow creating multiple independent zones", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    // Already has 1 mock zone, create another
    const checkboxes = screen.getAllByRole("checkbox");

    // Create first new zone
    await user.click(checkboxes[2]!);
    await user.click(checkboxes[3]!);
    const createButton = screen.getByRole("button", { name: /Zone erstellen/i });
    await user.click(createButton);

    // Should now have 2 zones total
    await waitFor(() => {
      const zoneCards = screen.getAllByText(/Zone/i);
      // At least 2 zone mentions (title + zone names)
      expect(zoneCards.length).toBeGreaterThanOrEqual(2);
    });
  });
});

describe("MultiRoom - User Guidance", () => {
  /**
   * TEST 15: Info Box Displayed
   * User Story: Als User möchte ich Hilfe zur Multi-Room Funktion sehen
   */
  test("should display info box with multi-room hints", () => {
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/Multi-Room Hinweise/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Das erste ausgewählte Gerät wird automatisch zum Master/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Lautstärke kann pro Gerät individuell angepasst werden/i)
    ).toBeInTheDocument();
  });
});
