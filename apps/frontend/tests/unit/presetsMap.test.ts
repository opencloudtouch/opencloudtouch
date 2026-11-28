import { describe, it, expect } from "vitest";
import { buildPresetsMap } from "../../src/utils/presetsMap";

describe("buildPresetsMap", () => {
  it("carries dlna and source_account so a DLNA preset opens in the DLNA tab", () => {
    const map = buildPresetsMap([
      {
        id: 1,
        device_id: "D",
        preset_number: 3,
        station_uuid: "u",
        station_name: "Album",
        station_url: "1$4 TRACK",
        source: "STORED_MUSIC",
        source_account: "uuid:abc/0",
        dlna: true,
        station_artist: "Some Artist",
        created_at: "",
        updated_at: "",
      },
    ]);
    expect(map[3]).toMatchObject({
      dlna: true,
      source_account: "uuid:abc/0",
      station_artist: "Some Artist",
    });
  });
});
