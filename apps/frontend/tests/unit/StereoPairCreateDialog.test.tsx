import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import StereoPairCreateDialog from "../../src/components/StereoPairCreateDialog";
import type { Device } from "../../src/api/devices";
import type { StereoPairCreate } from "../../src/hooks/useStereoPairCreate";

const waiting = [
  { key: "preflight", state: "waiting" },
  { key: "create_left", state: "waiting" },
  { key: "create_right", state: "waiting" },
  { key: "verify", state: "waiting" },
] as StereoPairCreate["steps"];

const idle = (): StereoPairCreate => ({
  phase: "idle",
  steps: waiting,
  pair: null,
  error: null,
  request: null,
  start: vi.fn(),
  reset: vi.fn(),
});

const st10 = (id: string, over: Partial<Device> = {}): Device => ({
  device_id: id,
  name: `Speaker ${id}`,
  model: "SoundTouch 10",
  firmware: "27.0.6",
  stereo_capable: true,
  oct_provisioned: true,
  stereo_ineligible_reason: null,
  stereo_pair_id: null,
  stereo_role: null,
  stereo_master: false,
  ...over,
});

const renderDialog = (create: StereoPairCreate, devices: Device[], extra = {}) =>
  render(
    <MemoryRouter>
      <StereoPairCreateDialog
        open
        onClose={vi.fn()}
        devices={devices}
        create={create}
        repairing={false}
        onRepair={vi.fn()}
        {...extra}
      />
    </MemoryRouter>
  );

const speakers = () => [
  st10("A"),
  st10("B"),
  st10("C", { stereo_ineligible_reason: "in_zone" }),
  { device_id: "W", name: "Wave", model: "Wave SoundTouch" } as Device,
];

describe("StereoPairCreateDialog", () => {
  it("step 1 lists only capable speakers and blocks ineligible ones with the reason", () => {
    renderDialog(idle(), speakers());

    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
    expect(screen.queryByText("Wave")).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Speaker C" })).toBeDisabled();
    expect(screen.getByText("In a zone")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("limits the selection to two speakers", () => {
    renderDialog(idle(), [...speakers(), st10("D")]);

    fireEvent.click(screen.getByRole("checkbox", { name: "Speaker A" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Speaker B" }));

    expect(screen.getByRole("checkbox", { name: "Speaker D" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("assigns sides, swaps them and starts the operation with LEFT first", () => {
    const create = idle();
    renderDialog(create, speakers());

    fireEvent.click(screen.getByRole("checkbox", { name: "Speaker A" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Speaker B" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Which speaker stands where?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Swap sides" }));
    fireEvent.change(screen.getByLabelText("Name (optional)"), { target: { value: " Office " } });
    fireEvent.click(screen.getByRole("button", { name: "Create stereo pair" }));

    expect(create.start).toHaveBeenCalledWith({
      left_device_id: "B",
      right_device_id: "A",
      name: "Office",
      leftName: "Speaker B",
      rightName: "Speaker A",
      defaultName: "Speaker B + Speaker A",
    });
  });

  it("warns, but does not block, when the firmware versions differ", () => {
    renderDialog(idle(), [st10("A"), st10("B", { firmware: "27.0.9" })]);

    fireEvent.click(screen.getByRole("checkbox", { name: "Speaker A" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Speaker B" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByRole("status")).toHaveTextContent("27.0.6");
    expect(screen.getByRole("button", { name: "Create stereo pair" })).toBeEnabled();
  });

  it("step 3 shows the four steps while running and lets the user continue in the background", () => {
    const onClose = vi.fn();
    const create: StereoPairCreate = {
      ...idle(),
      phase: "running",
      steps: waiting.map((s, i) => ({
        ...s,
        state: i === 0 ? "done" : i === 1 ? "running" : "waiting",
      })),
    };
    renderDialog(create, speakers(), { onClose });

    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
    fireEvent.click(screen.getAllByRole("button", { name: "Continue in background" }).at(-1)!);
    expect(onClose).toHaveBeenCalled();
  });

  it("step 3 failure shows the translated reason and says nothing was changed", () => {
    const create: StereoPairCreate = {
      ...idle(),
      phase: "failed",
      error: { code: "stereo_pair_marge_failed", message: "raw" },
    };
    renderDialog(create, speakers());

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("The speakers did not accept the pairing");
    expect(alert).toHaveTextContent("Nothing was changed.");
    expect(alert).toHaveTextContent("stereo_pair_marge_failed");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("step 3 degraded offers repair for the pair", () => {
    const onRepair = vi.fn();
    const create: StereoPairCreate = {
      ...idle(),
      phase: "failed",
      error: { code: "stereo_pair_degraded", message: "raw" },
      pair: {
        id: 9,
        name: "Office",
        status: "degraded",
        source: "oct",
        members: [],
        warnings: [],
      },
    };
    renderDialog(create, speakers(), { onRepair });

    fireEvent.click(screen.getByRole("button", { name: "Repair" }));

    expect(onRepair).toHaveBeenCalledWith(9);
  });

  it("step 3 success confirms and resets when done", () => {
    const create: StereoPairCreate = {
      ...idle(),
      phase: "succeeded",
      request: {
        left_device_id: "A",
        right_device_id: "B",
        leftName: "Speaker A",
        rightName: "Speaker B",
        defaultName: "Speaker A + Speaker B",
      },
    };
    const onClose = vi.fn();
    renderDialog(create, speakers(), { onClose });

    expect(screen.getByRole("status")).toHaveTextContent(
      "Speaker A plays left, Speaker B plays right"
    );
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalled();
    expect(create.reset).toHaveBeenCalled();
  });
});
