export type SearchMode = "provider" | "manual" | "dlna";
export type RadioProviderType = "radiobrowser" | "tunein";

export interface EditablePreset {
  station_uuid?: string;
  station_name: string;
  station_url?: string;
  station_favicon?: string;
  source?: string | null;
  dlna?: { server_id: string; object_id: string } | null;
}

export interface PresetEditState {
  mode: SearchMode;
  provider: RadioProviderType;
  /** Search term of provider mode (trimmed station name); empty for an empty slot. */
  term: string;
  manual: { url: string; name: string; favicon: string } | null;
  /** Saved DLNA reference to resolve; null with mode "dlna" means the plain server list. */
  dlna: { server_id: string; object_id: string } | null;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TUNEIN_ID_RE = /^[a-z]\d+$/;

/** Decides how the preset dialog opens for a saved preset (spec table, first match wins). */
export function presetEditState(
  preset: EditablePreset | null | undefined,
  hasTunein: boolean
): PresetEditState {
  const fallback: RadioProviderType = hasTunein ? "tunein" : "radiobrowser";
  const base: PresetEditState = {
    mode: "provider",
    provider: fallback,
    term: "",
    manual: null,
    dlna: null,
  };
  if (!preset) return base;

  if (preset.dlna) return { ...base, mode: "dlna", dlna: preset.dlna };
  if (preset.source === "DLNA") return { ...base, mode: "dlna" };

  const uuid = preset.station_uuid ?? "";
  if (uuid.startsWith("manual-")) {
    return {
      ...base,
      mode: "manual",
      manual: {
        url: preset.station_url ?? "",
        name: preset.station_name,
        favicon: preset.station_favicon ?? "",
      },
    };
  }

  let provider = fallback;
  if (UUID_RE.test(uuid)) provider = "radiobrowser";
  else if (
    (TUNEIN_ID_RE.test(uuid) && preset.source === "LOCAL_INTERNET_RADIO") ||
    preset.source === "TUNEIN" ||
    uuid.startsWith("tunein_")
  ) {
    provider = hasTunein ? "tunein" : "radiobrowser";
  }
  return { ...base, provider, term: preset.station_name.trim() };
}
