import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useSettledPresetState,
  PAUSE_SETTLE_MS,
  START_TIMEOUT_MS,
} from "../../src/hooks/useSettledPresetState";

const DEVICE = "device-under-test";

interface Props {
  deviceId: string;
  matched: number | null;
  state: string | undefined;
  error: unknown;
}

/** [ms after the previous event, state] as the speaker sent them, all for the same ContentItem. */
type Sequence = [number, string][];

// Recorded on a SoundTouch 10, one DLNA track preset with repeat all, at every track restart.
const RESTART: Sequence = [
  [0, "STOP_STATE"],
  [100, "STOP_STATE"],
  [600, "BUFFERING_STATE"],
  [400, "PLAY_STATE"],
];
const RESTART_SLOW: Sequence = [
  [0, "STOP_STATE"],
  [100, "STOP_STATE"],
  [600, "BUFFERING_STATE"],
  [1700, "PLAY_STATE"],
];

function setup(initial: Partial<Props> = {}) {
  const props: Props = { deviceId: DEVICE, matched: 1, state: undefined, error: null, ...initial };
  const view = renderHook(
    (p: Props) => useSettledPresetState(p.deviceId, p.matched, p.state, p.error),
    {
      initialProps: props,
    }
  );
  const seen: string[] = [];
  const sample = () => {
    const s = view.result.current.stateOf(1);
    if (seen.at(-1) !== s) seen.push(s);
  };
  const feed = (seq: Sequence, extra: Partial<Props> = {}) => {
    for (const [wait, state] of seq) {
      // Sample every 100 ms in between, as a user looking at the row would.
      for (let t = 0; t < wait; t += 100) {
        act(() => vi.advanceTimersByTime(Math.min(100, wait - t)));
        sample();
      }
      Object.assign(props, extra, { state });
      view.rerender({ ...props });
      sample();
    }
  };
  const wait = (ms: number) => {
    act(() => vi.advanceTimersByTime(ms));
    sample();
  };
  return { view, props, seen, sample, feed, wait };
}

describe("useSettledPresetState", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it.each([
    ["the recorded restart", RESTART],
    ["the slower variant", RESTART_SLOW],
  ])("a playing preset stays playing through %s", (_label, seq) => {
    const { seen, feed, wait } = setup({ state: "PLAY_STATE" });
    feed(seq);
    wait(5000);
    feed(seq);
    wait(5000);
    expect(seen).toEqual(["playing"]);
  });

  it("a click shows only starting, then playing, through buffering and a later restart", () => {
    const { view, seen, sample, feed, wait } = setup({ matched: null, state: "STOP_STATE" });
    sample();
    act(() => view.result.current.start(1));
    sample();
    // The play request returned long ago; the speaker reports the new preset as it goes.
    feed(
      [
        [300, "STOP_STATE"],
        [700, "BUFFERING_STATE"],
        [400, "PLAY_STATE"],
      ],
      { matched: 1 }
    );
    wait(3000);
    feed(RESTART);
    wait(5000);
    expect(seen).toEqual(["idle", "starting", "playing"]);
  });

  it("a radio station restart (stream drop) does not leave playing", () => {
    const { seen, feed, wait } = setup({ state: "PLAY_STATE" });
    feed([
      [0, "STOP_STATE"],
      [800, "BUFFERING_STATE"],
      [900, "BUFFERING_STATE"],
      [600, "PLAY_STATE"],
    ]);
    wait(5000);
    expect(seen).toEqual(["playing"]);
  });

  it("a radio start shows starting while buffering, then playing", () => {
    const { view, feed } = setup({ matched: null, state: undefined });
    act(() => view.result.current.start(2));
    const second = () => view.result.current.stateOf(2);
    expect(second()).toBe("starting");
    feed([[500, "BUFFERING_STATE"]], { matched: 2 });
    expect(second()).toBe("starting");
    feed([[1500, "PLAY_STATE"]], { matched: 2 });
    expect(second()).toBe("playing");
  });

  it("a stop that lasts shows paused after the settle time", () => {
    const { seen, feed, wait } = setup({ state: "PLAY_STATE" });
    feed([[0, "PAUSE_STATE"]]);
    wait(PAUSE_SETTLE_MS - 100);
    expect(seen).toEqual(["playing"]);
    wait(100);
    expect(seen).toEqual(["playing", "paused"]);
  });

  it("a pause by the user shows paused at once", () => {
    const { view, seen, feed } = setup({ state: "PLAY_STATE" });
    act(() => view.result.current.release());
    feed([[200, "PAUSE_STATE"]]);
    expect(seen).toEqual(["playing", "paused"]);
    // Playing again re-arms the hold for the next restart.
    feed([[500, "PLAY_STATE"], ...RESTART]);
    expect(seen).toEqual(["playing", "paused", "playing"]);
  });

  it("buffering without a previous play shows starting", () => {
    const { view } = setup({ state: "BUFFERING_STATE" });
    expect(view.result.current.stateOf(1)).toBe("starting");
  });

  it("a start ends after the timeout and then shows the speaker's state", () => {
    const { view, wait, seen } = setup({ matched: null, state: "STOP_STATE" });
    act(() => view.result.current.start(1));
    wait(START_TIMEOUT_MS - 1);
    expect(view.result.current.stateOf(1)).toBe("starting");
    wait(1);
    expect(view.result.current.stateOf(1)).toBe("idle");
    expect(seen.at(-1)).toBe("idle");
  });

  it("a new source error ends the start, one shown before the click does not", () => {
    const { view, props } = setup({ matched: null, state: "STOP_STATE", error: { code: 1 } });
    act(() => view.result.current.start(1));
    expect(view.result.current.stateOf(1)).toBe("starting");
    view.rerender({ ...props, error: { code: 2 } });
    expect(view.result.current.stateOf(1)).toBe("idle");
  });

  it("stop ends the start at once (the play request failed)", () => {
    const { view } = setup({ matched: null });
    act(() => view.result.current.start(1));
    act(() => view.result.current.stop());
    expect(view.result.current.stateOf(1)).toBe("idle");
  });

  it("nothing carries over to another device", () => {
    const { view, props } = setup({ state: "PLAY_STATE" });
    view.rerender({ ...props, deviceId: "other-device", state: "STOP_STATE" });
    expect(view.result.current.stateOf(1)).toBe("paused");
  });
});
