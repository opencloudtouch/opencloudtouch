import type { NativeServer, NativeSlot, NativeState } from "../../api/dlna";

export type { NativeServer, NativeSlot, NativeState };
export type SetupView = NativeState | "loading" | "busy" | "unknown" | "net";
export type SetupBusy = "setup" | "remove" | null;

/** What the panel, the removal dialog and the orphan list need from `useDlnaSetup`. Functions reject with an error whose `.code` is the API error code (undefined = network failure). */
export interface DlnaSetupApi {
  servers: NativeServer[] | undefined;
  isLoading: boolean;
  /** "unreachable" = 503 device_unreachable (speaker unreadable) */
  error: "unreachable" | "network" | null;
  refetch: () => Promise<void>;
  /** PUT; resolves with the state the speaker reports, success is never assumed */
  setup: (serverId: string) => Promise<NativeState>;
  slots: (serverId: string) => Promise<NativeSlot[]>;
  remove: (serverId: string, force: boolean) => Promise<void>;
}

export const SETUP_BADGE: Record<
  SetupView,
  { variant: "info" | "success" | "warning" | "neutral"; icon: string; label: string }
> = {
  loading: { variant: "info", icon: "Clock", label: "loading" },
  busy: { variant: "info", icon: "Clock", label: "settingUp" },
  not_enabled: { variant: "neutral", icon: "CircleMinus", label: "notSetUp" },
  ready: { variant: "success", icon: "CircleCheck", label: "ready" },
  unavailable: { variant: "warning", icon: "Alert", label: "unavailable" },
  unknown: { variant: "neutral", icon: "CircleHelp", label: "unknown" },
  net: { variant: "neutral", icon: "CircleHelp", label: "unknown" },
};

export const errorCode = (e: unknown): string => (e as { code?: string } | null)?.code ?? "unknown";
