import { describe, it, expect } from "vitest";
import { presetEditState } from "../../src/components/presetEditState";

const UUID = "123e4567-e89b-12d3-a456-426614174000";
const p = (o: Record<string, unknown>) => ({ station_name: "  Jazz FM ", ...o });

describe("presetEditState", () => {
  it("row 0: empty slot keeps the default provider and an empty term", () => {
    expect(presetEditState(null, true)).toMatchObject({
      mode: "provider",
      provider: "tunein",
      term: "",
    });
    expect(presetEditState(undefined, false)).toMatchObject({
      provider: "radiobrowser",
      term: "",
    });
  });

  it("row 1: dlna reference wins over the uuid", () => {
    const dlna = { server_id: "s", object_id: "o" };
    expect(presetEditState(p({ station_uuid: UUID, dlna }), true)).toMatchObject({
      mode: "dlna",
      dlna,
    });
  });

  it("row 2: source DLNA without reference opens the server list", () => {
    expect(presetEditState(p({ source: "DLNA", dlna: null }), true)).toMatchObject({
      mode: "dlna",
      dlna: null,
    });
  });

  it("row 3: manual stream fills the fields", () => {
    const s = presetEditState(
      p({ station_uuid: "manual-1", station_url: "http://x/s", station_favicon: "http://x/f" }),
      true
    );
    expect(s).toMatchObject({
      mode: "manual",
      manual: { url: "http://x/s", name: "  Jazz FM ", favicon: "http://x/f" },
    });
  });

  it("row 4: a UUID is RadioBrowser with the trimmed name", () => {
    expect(presetEditState(p({ station_uuid: UUID }), true)).toMatchObject({
      mode: "provider",
      provider: "radiobrowser",
      term: "Jazz FM",
    });
  });

  it.each(["s158432", "p1", "g22", "s1"])("row 5: %s with LOCAL_INTERNET_RADIO is TuneIn", (id) => {
    expect(
      presetEditState(p({ station_uuid: id, source: "LOCAL_INTERNET_RADIO" }), true).provider
    ).toBe("tunein");
  });

  it.each(["S1", "s", "sx1", "s1x"])("row 5 does not match %s", (id) => {
    // falls through to the default provider (radiobrowser here because TuneIn is off)
    expect(
      presetEditState(p({ station_uuid: id, source: "LOCAL_INTERNET_RADIO" }), false).provider
    ).toBe("radiobrowser");
    expect(
      presetEditState(p({ station_uuid: id, source: "LOCAL_INTERNET_RADIO" }), true).provider
    ).toBe("tunein");
  });

  it("row 5: a TuneIn-shaped uuid needs the LOCAL_INTERNET_RADIO source", () => {
    // source INTERNET_RADIO is row 7: default provider
    expect(
      presetEditState(p({ station_uuid: "s1", source: "INTERNET_RADIO" }), false).provider
    ).toBe("radiobrowser");
  });

  it("row 6: synced TuneIn presets", () => {
    expect(presetEditState(p({ source: "TUNEIN" }), true).provider).toBe("tunein");
    expect(presetEditState(p({ station_uuid: "tunein_x" }), true).provider).toBe("tunein");
  });

  it("rule a: tunein becomes radiobrowser without TuneIn support, term stays", () => {
    expect(presetEditState(p({ source: "TUNEIN" }), false)).toMatchObject({
      provider: "radiobrowser",
      term: "Jazz FM",
    });
  });

  it.each([
    ["INTERNET_RADIO", "internet_radio_1"],
    ["INTERNET_RADIO", "bmx_imported_1_ab"],
    ["STORED_MUSIC", "stored_1"],
    ["LOCAL_INTERNET_RADIO", "something"],
    ["WEIRD", "weird_1"],
    [undefined, undefined],
  ])("row 7: %s / %s uses the default provider", (source, station_uuid) => {
    expect(presetEditState(p({ source, station_uuid }), true)).toMatchObject({
      mode: "provider",
      provider: "tunein",
      term: "Jazz FM",
    });
  });
});
