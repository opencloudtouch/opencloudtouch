import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import StereoPairSection from "../../src/components/StereoPairSection";
import { ToastProvider } from "../../src/contexts/ToastContext";
import type { Device } from "../../src/api/devices";
import type { StereoPair } from "../../src/api/stereoPairs";
import type { StereoPairCreate } from "../../src/hooks/useStereoPairCreate";
import type { StereoPairs } from "../../src/hooks/useStereoPairs";

/** The components carry Cypress-style `data-test` attributes (not `data-testid`). */
const byTest = (name: string): HTMLElement => {
  const element = document.querySelector<HTMLElement>(`[data-test="${name}"]`);
  if (!element) throw new Error(`No element with data-test="${name}"`);
  return element;
};

const pairsState: StereoPairs = {
  pairs: [],
  isLoading: false,
  error: null,
  reload: vi.fn(),
  busyId: null,
  renamePair: vi.fn().mockResolvedValue(undefined),
  dissolvePair: vi.fn().mockResolvedValue(undefined),
  repairPair: vi.fn().mockResolvedValue(undefined),
};
const idleCreate: StereoPairCreate = {
  phase: "idle",
  steps: [
    { key: "preflight", state: "waiting" },
    { key: "create_left", state: "waiting" },
    { key: "create_right", state: "waiting" },
    { key: "verify", state: "waiting" },
  ],
  pair: null,
  error: null,
  request: null,
  start: vi.fn(),
  reset: vi.fn(),
};
let createState: StereoPairCreate = idleCreate;

vi.mock("../../src/hooks/useStereoPairs", () => ({ useStereoPairs: () => pairsState }));
vi.mock("../../src/hooks/useStereoPairCreate", () => ({ useStereoPairCreate: () => createState }));

const st10 = (id: string, over: Partial<Device> = {}): Device => ({
  device_id: id,
  name: `Speaker ${id}`,
  model: "SoundTouch 10",
  stereo_capable: true,
  oct_provisioned: true,
  stereo_ineligible_reason: null,
  stereo_pair_id: null,
  stereo_role: null,
  stereo_master: false,
  ...over,
});

const renderSection = (devices: Device[]) =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <StereoPairSection devices={devices} />
      </ToastProvider>
    </MemoryRouter>
  );

const pair: StereoPair = {
  id: 7,
  name: "Office",
  status: "active",
  source: "oct",
  members: [
    { device_id: "A", name: "Speaker A", role: "LEFT", reachable: true },
    { device_id: "B", name: "Speaker B", role: "RIGHT", reachable: true },
  ],
  warnings: [],
};

describe("StereoPairSection", () => {
  beforeEach(() => {
    pairsState.pairs = [];
    pairsState.error = null;
    pairsState.isLoading = false;
    createState = idleCreate;
    vi.clearAllMocks();
  });

  it("empty state: no capable speaker", () => {
    renderSection([{ device_id: "X", name: "X", model: "SoundTouch 20" } as Device]);

    expect(byTest("stereo-empty-none")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Create stereo pair/ })).toBeDisabled();
  });

  it("empty state: only one capable speaker", () => {
    renderSection([st10("A")]);

    expect(byTest("stereo-empty-one")).toHaveTextContent("Speaker A");
  });

  it("empty state: capable speakers not set up offers the wizard", () => {
    renderSection([
      st10("A", { oct_provisioned: false, stereo_ineligible_reason: "not_provisioned" }),
      st10("B", { oct_provisioned: false, stereo_ineligible_reason: "not_provisioned" }),
    ]);

    expect(byTest("stereo-empty-setup")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start setup/ })).toHaveAttribute("href", "/setup");
  });

  it("empty state: ready to create enables the button", () => {
    renderSection([st10("A"), st10("B")]);

    expect(byTest("stereo-empty-ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Create stereo pair/ })).toBeEnabled();
  });

  it("lists existing pairs", () => {
    pairsState.pairs = [pair];
    renderSection([st10("A"), st10("B")]);

    expect(byTest("stereo-pair")).toHaveTextContent("Office");
  });

  it("dissolves after confirmation", async () => {
    pairsState.pairs = [pair];
    renderSection([st10("A"), st10("B")]);

    fireEvent.click(screen.getByRole("button", { name: "Dissolve" }));
    const confirm = (await screen.findAllByRole("button", { name: "Dissolve" })).at(-1)!;
    fireEvent.click(confirm);

    await waitFor(() => expect(pairsState.dissolvePair).toHaveBeenCalledWith(7));
  });

  it("shows a load error with retry", () => {
    pairsState.error = "Backend down";
    renderSection([st10("A"), st10("B")]);

    expect(screen.getByRole("alert")).toHaveTextContent("Backend down");
    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    expect(pairsState.reload).toHaveBeenCalledTimes(1);
  });

  it.each(["succeeded", "failed"] as const)(
    "reloads the pair list when the create operation %s",
    (phase) => {
      pairsState.reload = vi.fn();
      createState = { ...idleCreate, phase };
      renderSection([st10("A"), st10("B")]);
      expect(pairsState.reload).toHaveBeenCalled();
    }
  );

  it("shows the running create operation as a pending card and disables creating", () => {
    createState = {
      ...idleCreate,
      phase: "running",
      request: {
        left_device_id: "A",
        right_device_id: "B",
        leftName: "Speaker A",
        rightName: "Speaker B",
        defaultName: "Speaker A + Speaker B",
      },
    };
    renderSection([st10("A"), st10("B")]);

    expect(byTest("stereo-pair")).toHaveTextContent("Speaker A + Speaker B");
    expect(byTest("stereo-status")).toHaveTextContent("Creating");
    expect(screen.getByRole("button", { name: /Create stereo pair/ })).toBeDisabled();
  });
});
