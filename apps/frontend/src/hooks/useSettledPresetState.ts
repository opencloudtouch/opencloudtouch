import { useCallback, useEffect, useState } from "react";
import type { PresetRowState } from "../components/PresetRow";

/** A restart (repeat, next track) passes STOP/BUFFERING for about 1-2 s: "playing" holds this long. */
export const PAUSE_SETTLE_MS = 3000;
/** "starting" ends at the latest after this; then the speaker's report applies. */
export const START_TIMEOUT_MS = 20000;

interface Settle {
  id: string | undefined;
  /** The preset that reached PLAY_STATE and keeps "playing" through a short stop. */
  held: number | null;
  /** Set by a pause from the user: no hold until the speaker has left PLAY_STATE once. */
  blocked: boolean;
  /** The preset the user started; "starting" until the speaker plays it. */
  starting: number | null;
}

const fresh = (id: string | undefined): Settle => ({
  id,
  held: null,
  blocked: false,
  starting: null,
});

/**
 * Smooths the row state of the preset the speaker plays (every source): a start shows "starting"
 * until PLAY_STATE, and a STOP/PAUSE after "playing" shows "paused" only once it lasted 3 s.
 */
export function useSettledPresetState(
  deviceId: string | undefined,
  /** The preset the speaker plays, null when none matches. */
  matched: number | null,
  playState: string | undefined,
  sourceError: unknown
) {
  const [stored, setStored] = useState<Settle>(() => fresh(deviceId));
  const current = stored.id === deviceId ? stored : fresh(deviceId);
  const playing = playState === "PLAY_STATE" && matched !== null;

  // Derived during render (no effect round trip): the hold follows the speaker's reports.
  let next = current;
  if (next.blocked && playState !== "PLAY_STATE") next = { ...next, blocked: false };
  if (playing && !next.blocked && next.held !== matched) next = { ...next, held: matched };
  else if (next.held !== null && next.held !== matched) next = { ...next, held: null };
  if (playing && next.starting === matched) next = { ...next, starting: null };
  if (next !== stored) setStored(next);

  const pausing = next.held !== null && (playState === "STOP_STATE" || playState === "PAUSE_STATE");
  useEffect(() => {
    if (!pausing) return;
    const timer = setTimeout(() => setStored((s) => ({ ...s, held: null })), PAUSE_SETTLE_MS);
    return () => clearTimeout(timer);
  }, [pausing]);

  const starting = next.starting;
  useEffect(() => {
    if (starting === null) return;
    const timer = setTimeout(() => setStored((s) => ({ ...s, starting: null })), START_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [starting]);

  // Only a new source error ends a start; one already shown before the click does not.
  useEffect(() => {
    if (sourceError) setStored((s) => ({ ...s, starting: null }));
  }, [sourceError]);

  const start = useCallback(
    (num: number) =>
      setStored((s) => ({ ...(s.id === deviceId ? s : fresh(deviceId)), starting: num })),
    [deviceId]
  );
  const stop = useCallback(() => setStored((s) => ({ ...s, starting: null })), []);
  const release = useCallback(() => setStored((s) => ({ ...s, held: null, blocked: true })), []);

  const stateOf = (num: number): PresetRowState => {
    if (num === next.starting) return "starting";
    if (num !== matched) return "idle";
    if (playState === "PLAY_STATE" || num === next.held) return "playing";
    if (playState === "BUFFERING_STATE") return "starting";
    // A radio stream cannot really pause: many devices report STOP_STATE with the station still selected
    if (playState === "PAUSE_STATE" || playState === "STOP_STATE") return "paused";
    return "idle";
  };

  return { stateOf, start, stop, release };
}
