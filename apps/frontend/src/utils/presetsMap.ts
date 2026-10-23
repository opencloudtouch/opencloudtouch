import type { Preset } from "../components/PresetButton";
import type { PresetResponse } from "../api/presets";

/** Turns the API list into the slot map the Presets page works with (preset number -> preset). */
export function buildPresetsMap(devicePresets: PresetResponse[]): Record<number, Preset> {
  const map: Record<number, Preset> = {};
  devicePresets.forEach((p) => {
    map[p.preset_number] = {
      station_uuid: p.station_uuid,
      station_name: p.station_name,
      station_url: p.station_url,
      station_favicon: p.station_favicon,
      source: p.source,
    };
  });
  return map;
}
