import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import StreamRecoverySettings from "../../src/components/StreamRecoverySettings";
import { QueryWrapper } from "../utils/reactQueryTestUtils";
import { ToastProvider } from "../../src/contexts/ToastContext";

const DEFAULTS = {
  enabled: false,
  min_play_seconds: 600,
  max_attempts_per_hour: 3,
  updated_at: null,
};

const EVENTS = {
  events: [
    {
      id: 2,
      occurred_at: "2026-10-26T05:52:08Z",
      device_id: "AABBCC112233",
      preset_number: 2,
      station_name: "Radio X",
      play_seconds: 21600,
      outcome: "resumed",
      attempts: 1,
      error_code: null,
    },
    {
      id: 1,
      occurred_at: "2026-10-26T01:00:00Z",
      device_id: "UNKNOWN0001",
      preset_number: 1,
      station_name: "Radio Y",
      play_seconds: 5400,
      outcome: "gave_up",
      attempts: 2,
      error_code: "device_unreachable",
    },
  ],
};

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  );
}

let handlers: Record<string, (init?: RequestInit) => Promise<Response>>;
let calls: Array<{ url: string; method: string; body?: string }>;

beforeEach(() => {
  calls = [];
  handlers = {
    "GET /api/stream-recovery": () => json(DEFAULTS),
    "GET /api/stream-recovery/events?limit=20": () => json({ events: [] }),
    "GET /api/devices": () =>
      json({ devices: [{ device_id: "AABBCC112233", name: "Kitchen" }], count: 1 }),
  };
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ url, method, body: init?.body as string | undefined });
    const handler = handlers[`${method} ${url}`];
    return handler ? handler(init) : json({}, 404);
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderSection() {
  return render(
    <QueryWrapper>
      <ToastProvider>
        <StreamRecoverySettings />
      </ToastProvider>
    </QueryWrapper>
  );
}

async function loaded() {
  return screen.findByRole("switch");
}

describe("StreamRecoverySettings", () => {
  it("shows the defaults: switch off, 10 minutes, 3 attempts, fields disabled", async () => {
    renderSection();
    const toggle = await loaded();
    expect(toggle).not.toBeChecked();
    expect(screen.getByLabelText(/Minimum playing time/)).toHaveValue(10);
    expect(screen.getByLabelText(/Maximum attempts/)).toHaveValue(3);
    expect(screen.getByLabelText(/Minimum playing time/)).toBeDisabled();
    expect(screen.getByLabelText(/Maximum attempts/)).toBeDisabled();
    expect(document.getElementById("stream-recovery")).not.toBeNull();
  });

  it("disables Save until something changed, saves seconds and shows a success status", async () => {
    handlers["PUT /api/stream-recovery"] = (init) => {
      const sent = JSON.parse(init?.body as string);
      return json({ ...sent, updated_at: "2026-10-26T06:00:00Z" });
    };
    renderSection();
    const toggle = await loaded();
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    fireEvent.click(toggle);
    const minutes = screen.getByLabelText(/Minimum playing time/);
    fireEvent.change(minutes, { target: { value: "15" } });
    expect(save).toBeEnabled();
    fireEvent.click(save);

    await waitFor(() => {
      expect(screen.getAllByText("Stream recovery settings saved").length).toBeGreaterThan(0);
    });
    const put = calls.find((c) => c.method === "PUT");
    expect(JSON.parse(put!.body!)).toEqual({
      enabled: true,
      min_play_seconds: 900,
      max_attempts_per_hour: 3,
    });
    // the baseline moved to the saved state
    await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeDisabled());
  });

  it.each([
    ["0", /Minimum playing time/],
    ["1441", /Minimum playing time/],
    ["1.5", /Minimum playing time/],
  ])("disables Save with an inline message for %s minutes", async (value, label) => {
    renderSection();
    fireEvent.click(await loaded());
    const input = screen.getByLabelText(label);
    fireEvent.change(input, { target: { value } });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter a whole number from 1 to 1440.")).toBeInTheDocument();
  });

  it("disables Save for 11 attempts", async () => {
    renderSection();
    fireEvent.click(await loaded());
    fireEvent.change(screen.getByLabelText(/Maximum attempts/), { target: { value: "11" } });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByText("Enter a whole number from 1 to 10.")).toBeInTheDocument();
  });

  it("maps a coded 422 to the minutes input with the translated message", async () => {
    handlers["PUT /api/stream-recovery"] = () =>
      json(
        {
          type: "validation_error",
          title: "Unprocessable Entity",
          status: 422,
          detail: "'min_play_seconds' must be an integer from 60 to 86400",
          code: "stream_recovery_min_play_invalid",
          errors: [
            {
              field: "body.min_play_seconds",
              path: "min_play_seconds",
              message: "raw backend text",
              code: "stream_recovery_min_play_invalid",
            },
          ],
        },
        422
      );
    renderSection();
    fireEvent.click(await loaded());
    fireEvent.change(screen.getByLabelText(/Minimum playing time/), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    const message = await screen.findByText(/minimum playing time is out of range/);
    expect(message).toBeInTheDocument();
    expect(screen.queryByText("raw backend text")).toBeNull();
    expect(screen.getByLabelText(/Minimum playing time/)).toHaveAttribute("aria-invalid", "true");
  });

  it("shows a form-level message for other save failures", async () => {
    handlers["PUT /api/stream-recovery"] = () =>
      json({ type: "server_error", title: "x", status: 500, detail: "boom" }, 500);
    renderSection();
    fireEvent.click(await loaded());
    fireEvent.change(screen.getByLabelText(/Maximum attempts/), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save the settings.");
  });

  it("shows a load error with a working Retry", async () => {
    let fail = true;
    handlers["GET /api/stream-recovery"] = () =>
      fail ? json({ detail: "x" }, 500) : json(DEFAULTS);
    renderSection();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load the stream recovery settings.");
    fail = false;
    fireEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("switch")).toBeInTheDocument();
  });

  describe("activity log", () => {
    it("does not load before the disclosure is expanded", async () => {
      renderSection();
      await loaded();
      expect(calls.some((c) => c.url.includes("/events"))).toBe(false);
      expect(screen.getByRole("button", { name: "Recent activity" })).toHaveAttribute(
        "aria-expanded",
        "false"
      );
    });

    it("shows translated outcomes, hours/minutes and device names", async () => {
      handlers["GET /api/stream-recovery/events?limit=20"] = () => json(EVENTS);
      renderSection();
      await loaded();
      fireEvent.click(screen.getByRole("button", { name: "Recent activity" }));

      expect(await screen.findByText("Resumed")).toBeInTheDocument();
      expect(screen.getByText("Kitchen")).toBeInTheDocument();
      expect(screen.getByText("UNKNOWN0001")).toBeInTheDocument();
      expect(screen.getByText("6 h 0 min")).toBeInTheDocument();
      expect(screen.getByText("1 h 30 min")).toBeInTheDocument();
      expect(screen.getByText(/Gave up/)).toHaveTextContent(
        "Gave up (The device is not reachable."
      );
    });

    it("shows the empty state", async () => {
      renderSection();
      await loaded();
      fireEvent.click(screen.getByRole("button", { name: "Recent activity" }));
      expect(await screen.findByText("No activity yet.")).toBeInTheDocument();
    });

    it("shows an error with a working Retry and refreshes on demand", async () => {
      let fail = true;
      handlers["GET /api/stream-recovery/events?limit=20"] = () =>
        fail ? json({ detail: "x" }, 500) : json(EVENTS);
      renderSection();
      await loaded();
      fireEvent.click(screen.getByRole("button", { name: "Recent activity" }));

      const alert = await screen.findByText("Could not load the activity.");
      fail = false;
      fireEvent.click(within(alert.parentElement!).getByRole("button", { name: "Retry" }));
      expect(await screen.findByText("Resumed")).toBeInTheDocument();

      const before = calls.filter((c) => c.url.includes("/events")).length;
      fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
      await waitFor(() =>
        expect(calls.filter((c) => c.url.includes("/events")).length).toBe(before + 1)
      );
      expect(await screen.findByText("Activity refreshed")).toBeInTheDocument();
    });
  });
});
