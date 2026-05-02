/**
 * Functional Tests for MultiRoom Component
 *
 * User Story: "Als User möchte ich mehrere Geräte zu einer Zone gruppieren"
 *
 * Test Strategy: Behaviour-driven testing focusing on zone management workflows
 * Coverage: Create Zone, Edit Zone, Dissolve Zone, Device Selection, Validation,
 *           Zone Names, NowPlaying, Volume per Member, Master Selection
 */

import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode, HTMLAttributes } from "react";
import MultiRoom from "../../src/pages/MultiRoom";
import type { ZoneInfo } from "../../src/api/zones";

// ---- Mock framer-motion ----
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: { children: ReactNode } & HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
    section: ({ children, ...props }: { children: ReactNode } & HTMLAttributes<HTMLElement>) => <section {...props}>{children}</section>,
    label: ({ children, ...props }: { children: ReactNode } & HTMLAttributes<HTMLLabelElement>) => <label {...props}>{children}</label>,
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

// ---- Mock useZones hook ----
const mockCreateZone = vi.fn().mockResolvedValue({});
const mockDissolveZone = vi.fn().mockResolvedValue(undefined);
const mockAddMembers = vi.fn().mockResolvedValue({});
const mockRemoveMembers = vi.fn().mockResolvedValue(undefined);
const mockChangeMaster = vi.fn().mockResolvedValue({});
const mockRefetch = vi.fn().mockResolvedValue(undefined);

let mockZonesState: { zones: ZoneInfo[]; isLoading: boolean; error: string | null } = {
  zones: [],
  isLoading: false,
  error: null,
};

vi.mock("../../src/hooks/useZones", () => ({
  useZones: () => ({
    ...mockZonesState,
    createZone: mockCreateZone,
    dissolveZone: mockDissolveZone,
    addMembers: mockAddMembers,
    removeMembers: mockRemoveMembers,
    changeMaster: mockChangeMaster,
    refetch: mockRefetch,
  }),
}));

// ---- Mock useZoneNames hook ----
const mockGetZoneName = vi.fn((_, defaultName: string) => defaultName);
const mockSetZoneName = vi.fn();
const mockRemoveZoneName = vi.fn();

vi.mock("../../src/hooks/useZoneNames", () => ({
  useZoneNames: () => ({
    getZoneName: mockGetZoneName,
    setZoneName: mockSetZoneName,
    removeZoneName: mockRemoveZoneName,
  }),
}));

// ---- Mock useVolume hook ----
vi.mock("../../src/hooks/useVolume", () => ({
  useVolume: () => ({
    volume: 40,
    muted: false,
    loading: false,
    setDeviceVolume: vi.fn(),
    toggleMute: vi.fn(),
  }),
}));

// ---- Mock useNowPlaying hook ----
vi.mock("../../src/hooks/useNowPlaying", () => ({
  useNowPlaying: () => ({
    nowPlaying: null,
    loading: false,
    refresh: vi.fn(),
  }),
}));

// ---- Mock VolumeSlider & NowPlaying ----
vi.mock("../../src/components/VolumeSlider", () => ({
  default: () => <div data-testid="volume-slider">VolumeSlider</div>,
}));

vi.mock("../../src/components/NowPlaying", () => ({
  default: () => <div data-testid="now-playing">NowPlaying</div>,
}));

// ---- Mock ToastContext ----
const mockShowToast = vi.fn();
vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShowToast }),
}));

const mockDevices = [
  { device_id: "ST10-001", name: "Living Room", model: "SoundTouch 10" },
  { device_id: "ST30-002", name: "Schlafzimmer", model: "SoundTouch 30" },
  { device_id: "ST10-003", name: "Küche", model: "SoundTouch 10" },
  { device_id: "ST300-004", name: "Badezimmer", model: "SoundTouch 300" },
];

const MOCK_ZONE: ZoneInfo = {
  master_id: "ST10-001",
  master_ip: "192.168.1.10",
  is_master: true,
  members: [
    { device_id: "ST10-001", ip_address: "192.168.1.10", role: "master", name: "Living Room" },
    { device_id: "ST30-002", ip_address: "192.168.1.20", role: "slave", name: "Schlafzimmer" },
  ],
};

describe("MultiRoom - Zone Creation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockZonesState = { zones: [], isLoading: false, error: null };
  });

  test("should show empty device grid when no devices available", () => {
    render(<MultiRoom devices={[]} />);

    expect(screen.getByText(/Multi-Room Zones/i)).toBeInTheDocument();
    expect(screen.getByText(/Create New Zone/i)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  test("should display all available devices for selection", () => {
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText("Living Room")).toBeInTheDocument();
    expect(screen.getByText("Schlafzimmer")).toBeInTheDocument();
    expect(screen.getByText("Küche")).toBeInTheDocument();
    expect(screen.getByText("Badezimmer")).toBeInTheDocument();
  });

  test("should allow selecting multiple devices", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    await user.click(checkboxes[0]!);
    expect(checkboxes[0]).toBeChecked();
    expect(screen.getByText(/1 device\(s\) selected/i)).toBeInTheDocument();

    await user.click(checkboxes[1]!);
    expect(checkboxes[1]).toBeChecked();
    expect(screen.getByText(/2 device\(s\) selected/i)).toBeInTheDocument();
  });

  test("should show master badge on first selected device and slave on others", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");

    await user.click(checkboxes[0]!);
    await waitFor(() => {
      expect(screen.getAllByText("Master").length).toBeGreaterThan(0);
    });

    await user.click(checkboxes[1]!);
    await waitFor(() => {
      expect(screen.getByText("Slave")).toBeInTheDocument();
    });
  });

  test("should disable create button when less than 2 devices selected", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!);

    await waitFor(() => {
      expect(screen.getByText(/at least 2 required/i)).toBeInTheDocument();
      const createButton = screen.getByRole("button", { name: /Create Zone/i });
      expect(createButton).toBeDisabled();
    });
  });

  test("should call createZone API when 2+ devices selected and button clicked", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!);
    await user.click(checkboxes[1]!);

    const createButton = screen.getByRole("button", { name: /Create Zone/i });
    expect(createButton).toBeEnabled();

    await user.click(createButton);

    expect(mockCreateZone).toHaveBeenCalledWith("ST10-001", ["ST30-002"]);
  });

  test("should allow deselecting devices", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!);
    expect(checkboxes[0]).toBeChecked();

    await user.click(checkboxes[0]!);
    expect(checkboxes[0]).not.toBeChecked();
    expect(screen.queryByText(/device\(s\) selected/i)).not.toBeInTheDocument();
  });

  test("should clear selection after successful zone creation", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[2]!);
    await user.click(checkboxes[3]!);

    const createButton = screen.getByRole("button", { name: /Create Zone/i });
    await user.click(createButton);

    await waitFor(() => {
      expect(checkboxes[2]).not.toBeChecked();
      expect(checkboxes[3]).not.toBeChecked();
      expect(screen.queryByText(/device\(s\) selected/i)).not.toBeInTheDocument();
    });
  });
});

describe("MultiRoom - Zone Display", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockZonesState = { zones: [MOCK_ZONE], isLoading: false, error: null };
  });

  test("should display existing zones with master and slaves", () => {
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/Active Zones/i)).toBeInTheDocument();
    const masterBadges = screen.getAllByText("Master");
    expect(masterBadges.length).toBeGreaterThan(0);
    const slaveBadges = screen.getAllByText("Slave");
    expect(slaveBadges.length).toBeGreaterThan(0);
  });

  test("should show volume slider per zone member", () => {
    render(<MultiRoom devices={mockDevices} />);

    const sliders = screen.getAllByTestId("volume-slider");
    expect(sliders.length).toBe(2); // master + 1 slave
  });

  test("should show now-playing section in zone card", () => {
    render(<MultiRoom devices={mockDevices} />);

    // NowPlaying returns null → shows standby
    expect(screen.getByText("Standby")).toBeInTheDocument();
  });

  test("should show zone name from useZoneNames", () => {
    mockGetZoneName.mockReturnValue("Mein Wohnzimmer");
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText("Mein Wohnzimmer")).toBeInTheDocument();
  });
});

describe("MultiRoom - Zone Management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockZonesState = { zones: [MOCK_ZONE], isLoading: false, error: null };
  });

  test("should require confirmation before dissolving zone", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const dissolveButton = screen.getByRole("button", { name: /Dissolve/i });
    await user.click(dissolveButton);

    // Should show confirmation
    expect(screen.getByRole("button", { name: /Really dissolve/i })).toBeInTheDocument();
  });

  test("should call dissolveZone API on confirmation", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const dissolveButton = screen.getByRole("button", { name: /Dissolve/i });
    await user.click(dissolveButton);

    const confirmButton = screen.getByRole("button", { name: /Really dissolve/i });
    await user.click(confirmButton);

    expect(mockDissolveZone).toHaveBeenCalledWith("ST10-001");
    expect(mockRemoveZoneName).toHaveBeenCalledWith("ST10-001");
  });

  test("should allow editing existing zone", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const editButton = screen.getByRole("button", { name: /Edit/i });
    await user.click(editButton);

    await waitFor(() => {
      expect(screen.getByText(/Edit zone/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Update Zone/i })).toBeInTheDocument();
    });
  });

  test("should show cancel button in edit mode", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const editButton = screen.getByRole("button", { name: /Edit/i });
    await user.click(editButton);

    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
  });

  test("should disable devices already in a different zone", () => {
    render(<MultiRoom devices={mockDevices} />);

    // ST10-001 and ST30-002 are in zone → In Zone badge
    const inZoneBadges = screen.getAllByText("In Zone");
    expect(inZoneBadges.length).toBeGreaterThan(0);
  });
});

describe("MultiRoom - Master Selection (STORY-1011)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockZonesState = { zones: [], isLoading: false, error: null };
  });

  test("should show set-master button on slave devices", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!);
    await user.click(checkboxes[1]!);

    // Slave should have ★ button
    expect(screen.getByTitle("Set as master")).toBeInTheDocument();
  });

  test("should swap master when set-master button clicked", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!); // ST10-001 = Master
    await user.click(checkboxes[1]!); // ST30-002 = Slave

    const setMasterBtn = screen.getByTitle("Set as master");
    await user.click(setMasterBtn);

    // Now create zone - ST30-002 should be first (master)
    const createButton = screen.getByRole("button", { name: /Create Zone/i });
    await user.click(createButton);

    expect(mockCreateZone).toHaveBeenCalledWith("ST30-002", ["ST10-001"]);
  });
});

describe("MultiRoom - Zone Name Editing (STORY-1009)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetZoneName.mockImplementation((_, defaultName: string) => defaultName);
    mockZonesState = { zones: [MOCK_ZONE], isLoading: false, error: null };
  });

  test("should show editable zone name button", () => {
    render(<MultiRoom devices={mockDevices} />);

    const nameButton = screen.getByTitle("Click to edit");
    expect(nameButton).toBeInTheDocument();
  });

  test("should switch to input on zone name click", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const nameButton = screen.getByTitle("Click to edit");
    await user.click(nameButton);

    const input = screen.getByRole("textbox", { name: /Edit zone name/i });
    expect(input).toBeInTheDocument();
  });

  test("should save zone name on Enter", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const nameButton = screen.getByTitle("Click to edit");
    await user.click(nameButton);

    const input = screen.getByRole("textbox", { name: /Edit zone name/i });
    await user.clear(input);
    await user.type(input, "Mein Wohnzimmer{Enter}");

    expect(mockSetZoneName).toHaveBeenCalledWith("ST10-001", "Mein Wohnzimmer");
  });
});

describe("MultiRoom - Loading & Error States", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("should show loading state", () => {
    mockZonesState = { zones: [], isLoading: true, error: null };
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/Loading zones/i)).toBeInTheDocument();
  });

  test("should show error state", () => {
    mockZonesState = { zones: [], isLoading: false, error: "Network Error" };
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/Error loading/i)).toBeInTheDocument();
    expect(screen.getByText("Network Error")).toBeInTheDocument();
  });

  test("should show empty state when no zones exist", () => {
    mockZonesState = { zones: [], isLoading: false, error: null };
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/No active zones/i)).toBeInTheDocument();
  });
});

describe("MultiRoom - User Guidance", () => {
  beforeEach(() => {
    mockZonesState = { zones: [], isLoading: false, error: null };
  });

  test("should display info box with multi-room hints", () => {
    render(<MultiRoom devices={mockDevices} />);

    expect(screen.getByText(/Multi-Room Notes/i)).toBeInTheDocument();
    expect(
      screen.getByText(/first selected device automatically becomes the master/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Volume can be adjusted individually per device/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Click the zone name to rename it/i)
    ).toBeInTheDocument();
  });
});

describe("MultiRoom - Toast Notifications (STORY-1008)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockZonesState = { zones: [], isLoading: false, error: null };
  });

  test("should show success toast on zone creation", async () => {
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!);
    await user.click(checkboxes[1]!);

    const createButton = screen.getByRole("button", { name: /Create Zone/i });
    await user.click(createButton);

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("Zone created", "success");
    });
  });

  test("should show error toast on zone creation failure", async () => {
    mockCreateZone.mockRejectedValueOnce(new Error("Network error"));
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!);
    await user.click(checkboxes[1]!);

    const createButton = screen.getByRole("button", { name: /Create Zone/i });
    await user.click(createButton);

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("Zone could not be created", "error");
    });
  });

  test("should show success toast on zone dissolve", async () => {
    mockZonesState = { zones: [MOCK_ZONE], isLoading: false, error: null };
    const user = userEvent.setup();
    render(<MultiRoom devices={mockDevices} />);

    const dissolveButton = screen.getByRole("button", { name: /Dissolve/i });
    await user.click(dissolveButton);

    const confirmButton = screen.getByRole("button", { name: /Really dissolve/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("Zone dissolved", "success");
    });
  });
});

describe("MultiRoom - 5+ Device Zone Display", () => {
  const fiveDevices = [
    { device_id: "D001", name: "Wohnzimmer", model: "SoundTouch 30" },
    { device_id: "D002", name: "Küche", model: "SoundTouch 10" },
    { device_id: "D003", name: "Schlafzimmer", model: "SoundTouch 10" },
    { device_id: "D004", name: "Bad", model: "SoundTouch 300" },
    { device_id: "D005", name: "Büro", model: "SoundTouch 20" },
  ];

  const fiveMemberZone: ZoneInfo = {
    master_id: "D001",
    master_ip: "192.168.1.10",
    is_master: true,
    members: [
      { device_id: "D001", ip_address: "192.168.1.10", role: "master", name: "Wohnzimmer" },
      { device_id: "D002", ip_address: "192.168.1.11", role: "slave", name: "Küche" },
      { device_id: "D003", ip_address: "192.168.1.12", role: "slave", name: "Schlafzimmer" },
      { device_id: "D004", ip_address: "192.168.1.13", role: "slave", name: "Bad" },
      { device_id: "D005", ip_address: "192.168.1.14", role: "slave", name: "Büro" },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("should display all 5 zone members with correct badges", () => {
    mockZonesState = { zones: [fiveMemberZone], isLoading: false, error: null };
    render(<MultiRoom devices={fiveDevices} />);

    // All 5 device names visible in zone display
    expect(screen.getAllByText("Wohnzimmer").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Küche").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Schlafzimmer").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Bad").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Büro").length).toBeGreaterThanOrEqual(1);

    // 1 Master badge + 4 Slave badges in zone
    const masterBadges = screen.getAllByText("Master");
    const slaveBadges = screen.getAllByText("Slave");
    expect(masterBadges.length).toBeGreaterThanOrEqual(1);
    expect(slaveBadges.length).toBeGreaterThanOrEqual(4);
  });

  test("should render volume slider for each of 5 zone members", () => {
    mockZonesState = { zones: [fiveMemberZone], isLoading: false, error: null };
    render(<MultiRoom devices={fiveDevices} />);

    const volumeSliders = screen.getAllByTestId("volume-slider");
    expect(volumeSliders.length).toBe(5);
  });

  test("should select all 5 devices and create zone", async () => {
    mockZonesState = { zones: [], isLoading: false, error: null };
    const user = userEvent.setup();
    render(<MultiRoom devices={fiveDevices} />);

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(5);

    for (const cb of checkboxes) {
      await user.click(cb);
    }

    await waitFor(() => {
      expect(screen.getByText(/5 device\(s\) selected/i)).toBeInTheDocument();
    });

    const createButton = screen.getByRole("button", { name: /Create Zone/i });
    expect(createButton).toBeEnabled();

    await user.click(createButton);

    expect(mockCreateZone).toHaveBeenCalledWith("D001", ["D002", "D003", "D004", "D005"]);
  });
});
