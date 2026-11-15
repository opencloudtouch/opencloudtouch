import { describe, it, expect } from "vitest";
import { visibleDevices } from "../../src/utils/visibleDevices";

const d = (device_id: string, role: "LEFT" | "RIGHT" | null = null, master = false) => ({
  device_id,
  stereo_role: role,
  stereo_master: master,
});

describe("visibleDevices", () => {
  it("keeps single speakers and the master of a pair", () => {
    const list = [d("A"), d("L", "LEFT", true), d("B")];
    expect(visibleDevices(list)).toEqual(list);
  });

  it("hides the speaker of a pair that is not the master", () => {
    const list = [d("L", "LEFT", true), d("R", "RIGHT", false), d("A")];
    expect(visibleDevices(list).map((x) => x.device_id)).toEqual(["L", "A"]);
  });

  it("keeps the order of the list", () => {
    const list = [d("R", "RIGHT", false), d("A"), d("L", "LEFT", true)];
    expect(visibleDevices(list).map((x) => x.device_id)).toEqual(["A", "L"]);
  });

  it("treats a missing role as a single speaker", () => {
    expect(visibleDevices([{ device_id: "A" }])).toHaveLength(1);
  });
});
