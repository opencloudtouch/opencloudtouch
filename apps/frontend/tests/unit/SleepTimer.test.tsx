import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import SleepTimer from "../../src/components/SleepTimer";
import { createQueryWrapper } from "../utils/reactQueryTestUtils";
import { STORAGE_KEY } from "../../src/utils/sleepTimer";

const DEVICE = "AABBCC112233";
const URL = `/api/devices/${DEVICE}/sleep-timer`;
const SKEW_MS = 5 * 60_000; // this device's clock runs 5 minutes ahead of the server

const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");

/** Server clock = device clock minus the skew; the fake clock drives both. */
const serverNow = () => Date.now() - SKEW_MS;

type Active = { endsAtMs: number; fade?: number; action?: "stop" | "standby" };

/** A timer that ends `seconds` from now on the server clock (fixed, not sliding). */
function timer(
  seconds: number,
  extra: { fade?: number; action?: "stop" | "standby" } = {}
): Active {
  return { endsAtMs: serverNow() + seconds * 1000, ...extra };
}

function statusBody(timer: Active | null) {
  if (!timer) return { active: false, server_time: iso(serverNow()) };
  return {
    active: true,
    server_time: iso(serverNow()),
    device_id: DEVICE,
    ends_at: iso(timer.endsAtMs),
    duration_minutes: 30,
    fade_seconds: timer.fade ?? 30,
    end_action: timer.action ?? "stop",
    state: "running",
  };
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(body === null ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  );
}

let current: Active | null;
let calls: Array<{ method: string; body?: string }>;
let putHandler: (body: unknown) => Promise<Response>;

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
  localStorage.clear();
  current = null;
  calls = [];
  putHandler = (body) => {
    const input = body as {
      duration_minutes: number;
      fade_seconds: number;
      end_action: "stop" | "standby";
    };
    current = timer(input.duration_minutes * 60, {
      fade: input.fade_seconds,
      action: input.end_action,
    });
    return json(statusBody(current));
  };
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, body: init?.body as string | undefined });
    if (url !== URL) return json({}, 404);
    if (method === "PUT") return putHandler(JSON.parse(init?.body as string));
    if (method === "DELETE") {
      current = null;
      return json(null, 204);
    }
    return json(statusBody(current));
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function renderTimer(deviceOffline = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = createQueryWrapper(client);
  render(
    <Wrapper>
      <SleepTimer deviceId={DEVICE} deviceOffline={deviceOffline} />
    </Wrapper>
  );
  await settle();
}

/** Let promises and React Query's scheduling run without moving the clock much. */
async function settle(ms = 10) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

const gets = () => calls.filter((c) => c.method === "GET").length;
const countdown = () => screen.getByRole("timer").textContent;

describe("start", () => {
  it("shows the form with the defaults when no timer runs, without an error", async () => {
    await renderTimer();
    expect(screen.getByLabelText("Duration")).toHaveValue("30");
    expect(screen.getByLabelText("Fade out")).toHaveValue("30");
    expect(screen.getByLabelText("When finished")).toHaveValue("stop");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("sends exactly the chosen values and shows the countdown", async () => {
    await renderTimer();
    fireEvent.click(screen.getByRole("button", { name: "Start timer" }));
    await settle();

    const put = calls.find((c) => c.method === "PUT");
    expect(JSON.parse(put!.body!)).toEqual({
      duration_minutes: 30,
      fade_seconds: 30,
      end_action: "stop",
    });
    expect(countdown()).toBe("30:00");
    expect(screen.getByText("Sleep timer started")).toBeInTheDocument();
  });

  it("sends a changed duration, fade and end action", async () => {
    await renderTimer();
    fireEvent.change(screen.getByLabelText("Duration"), { target: { value: "90" } });
    fireEvent.change(screen.getByLabelText("Fade out"), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("When finished"), { target: { value: "standby" } });
    fireEvent.click(screen.getByRole("button", { name: "Start timer" }));
    await settle();

    const put = calls.find((c) => c.method === "PUT");
    expect(JSON.parse(put!.body!)).toEqual({
      duration_minutes: 90,
      fade_seconds: 0,
      end_action: "standby",
    });
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual({
      duration: 90,
      fade: 0,
      endAction: "standby",
    });
  });

  it.each(["0", "721", "1.5", ""])("rejects the custom value %j without sending", async (value) => {
    await renderTimer();
    fireEvent.change(screen.getByLabelText("Duration"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Minutes"), { target: { value } });

    expect(screen.getByText("Enter a whole number from 1 to 720.")).toBeInTheDocument();
    expect(screen.getByLabelText("Minutes")).toHaveAttribute("aria-invalid", "true");
    const start = screen.getByRole("button", { name: "Start timer" });
    expect(start).toBeDisabled();
    fireEvent.click(start);
    await settle();
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("accepts a valid custom duration", async () => {
    await renderTimer();
    fireEvent.change(screen.getByLabelText("Duration"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Minutes"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Start timer" }));
    await settle();
    expect(JSON.parse(calls.find((c) => c.method === "PUT")!.body!).duration_minutes).toBe(1);
  });

  it("shows the translated error at the fade control", async () => {
    putHandler = () =>
      json(
        {
          type: "validation_error",
          title: "Unprocessable Entity",
          status: 422,
          detail: "fade too long",
          code: "sleep_timer_fade_too_long",
          errors: [
            {
              field: "fade_seconds",
              path: "fade_seconds",
              message: "raw backend text",
              code: "sleep_timer_fade_too_long",
            },
          ],
        },
        422
      );
    await renderTimer();
    fireEvent.click(screen.getByRole("button", { name: "Start timer" }));
    await settle();

    expect(screen.getByText("The fade-out must not be longer than the timer.")).toBeInTheDocument();
    expect(screen.queryByText("raw backend text")).toBeNull();
    expect(screen.getByLabelText("Fade out")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows a generic message for other failures", async () => {
    putHandler = () =>
      json({ type: "x", title: "x", status: 503, detail: "x", code: "device_unreachable" }, 503);
    await renderTimer();
    fireEvent.click(screen.getByRole("button", { name: "Start timer" }));
    await settle();
    expect(screen.getByRole("alert")).toHaveTextContent("The device is not reachable.");
  });
});

describe("remembered defaults", () => {
  it("restores and validates them", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ duration: 45, fade: 10, endAction: "standby" })
    );
    await renderTimer();
    expect(screen.getByLabelText("Duration")).toHaveValue("45");
    expect(screen.getByLabelText("Fade out")).toHaveValue("10");
    expect(screen.getByLabelText("When finished")).toHaveValue("standby");
  });

  it("shows a stored custom duration as 'Custom'", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ duration: 50, fade: 0, endAction: "stop" }));
    await renderTimer();
    expect(screen.getByLabelText("Duration")).toHaveValue("custom");
    expect(screen.getByLabelText("Minutes")).toHaveValue(50);
  });

  it("works when storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    await renderTimer();
    fireEvent.click(screen.getByRole("button", { name: "Start timer" }));
    await settle();
    expect(countdown()).toBe("30:00");
  });
});

describe("countdown", () => {
  it("matches ends_at against the server clock although this device is 5 minutes off", async () => {
    current = timer(1800);
    await renderTimer();
    expect(countdown()).toBe("30:00");

    await advance(10_000);
    expect(countdown()).toBe("29:50");
  });

  it("uses h:mm:ss from one hour on", async () => {
    current = timer(3 * 3600 + 5 * 60 + 7);
    await renderTimer();
    expect(countdown()).toBe("3:05:07");
  });

  it("continues from the server data after a reload", async () => {
    current = timer(600);
    await renderTimer();
    expect(countdown()).toBe("10:00");
    expect(screen.getByRole("button", { name: "Cancel timer" })).toBeInTheDocument();
  });

  it("names the countdown and the end action", async () => {
    current = timer(600, { action: "standby" });
    await renderTimer();
    expect(screen.getByRole("timer")).toHaveAccessibleName("Time until the timer ends");
    expect(screen.getByText("When finished: Switch to standby")).toBeInTheDocument();
  });

  it("announces fading when the fade window starts", async () => {
    current = timer(40, { fade: 30 });
    await renderTimer();
    expect(screen.queryByText(/Fading out/)).toBeNull();
    await advance(11_000);
    expect(screen.getByText(/Fading out/)).toBeInTheDocument();
  });

  it("is not announced every second", async () => {
    current = timer(600);
    await renderTimer();
    expect(screen.getByRole("timer")).not.toHaveAttribute("aria-live", "polite");
  });
});

describe("cancel", () => {
  it("sends DELETE, returns to the start state and says nothing about an end", async () => {
    current = timer(600);
    await renderTimer();
    fireEvent.click(screen.getByRole("button", { name: "Cancel timer" }));
    await settle();

    expect(calls.some((c) => c.method === "DELETE")).toBe(true);
    expect(screen.getByRole("button", { name: "Start timer" })).toBeInTheDocument();
    expect(screen.queryByText("Timer is no longer active")).toBeNull();
    expect(screen.getByText("Sleep timer cancelled")).toBeInTheDocument();
  });
});

describe("offline device", () => {
  it("disables start with an explanation", async () => {
    await renderTimer(true);
    const start = screen.getByRole("button", { name: "Start timer" });
    expect(start).toBeDisabled();
    expect(start).toHaveAccessibleDescription(
      "The speaker is offline. A new timer cannot be started."
    );
  });

  it("keeps a running timer visible and cancellable", async () => {
    current = timer(600);
    await renderTimer(true);
    expect(countdown()).toBe("10:00");
    const cancel = screen.getByRole("button", { name: "Cancel timer" });
    expect(cancel).toBeEnabled();
    fireEvent.click(cancel);
    await settle();
    expect(calls.some((c) => c.method === "DELETE")).toBe(true);
  });
});

describe("polling", () => {
  it("polls at most every 30 seconds while a timer runs", async () => {
    current = timer(900);
    await renderTimer();
    const before = gets();
    await advance(29_000);
    expect(gets()).toBe(before);
    await advance(2_000);
    expect(gets()).toBe(before + 1);
  });

  it("does not poll without a timer", async () => {
    await renderTimer();
    const before = gets();
    await advance(120_000);
    expect(gets()).toBe(before);
  });

  it("stops polling while the tab is hidden", async () => {
    current = timer(900);
    await renderTimer();
    const before = gets();
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await advance(120_000);
    expect(gets()).toBe(before);
  });

  it("shows 'ending…' at 0, polls every 3 s and then the neutral message once", async () => {
    current = timer(5);
    await renderTimer();
    expect(countdown()).toBe("0:05");

    await advance(6_000);
    expect(screen.getByRole("timer")).toHaveTextContent("0:00");
    expect(screen.getByText("Ending…")).toBeInTheDocument();
    const afterZero = gets();
    expect(afterZero).toBeGreaterThan(1); // looked at the server right away

    await advance(3_000);
    expect(gets()).toBeGreaterThan(afterZero);

    current = null; // the server finished the end sequence
    await advance(3_500);
    expect(screen.getAllByText("Timer is no longer active").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Start timer" })).toBeInTheDocument();

    const settled = gets();
    await advance(60_000);
    expect(gets()).toBe(settled); // no further polling
  });

  it("returns to the start state silently when the timer vanished before it ended", async () => {
    current = timer(900);
    await renderTimer();
    current = null; // cancelled elsewhere / manual volume change
    await advance(31_000);

    expect(screen.getByRole("button", { name: "Start timer" })).toBeInTheDocument();
    expect(screen.queryByText("Timer is no longer active")).toBeNull();
  });

  it("gives up polling 90 seconds after the end", async () => {
    current = timer(2);
    await renderTimer();
    await advance(100_000);
    const before = gets();
    await advance(60_000);
    expect(gets()).toBe(before);
  });
});

describe("load error", () => {
  it("shows a retry for a failing status request", async () => {
    vi.stubGlobal("fetch", () => json({ detail: "x" }, 500));
    await renderTimer();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load the sleep timer.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
