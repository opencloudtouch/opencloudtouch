/**
 * Accessibility regressions: document language, landmark labels, wizard focus management,
 * tracker semantics and text alternatives for status icons.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { i18next } from "../../src/i18n";
import Navigation from "../../src/components/Navigation";
import ProgressTracker, { type WizardStep as TrackerStep } from "../../src/components/wizard/ProgressTracker";

const mockRestore = vi.fn();
let mockRestoreData: unknown = null;

vi.mock("../../src/hooks/useRestore", () => ({
  useExecuteRestore: () => ({
    mutate: mockRestore,
    data: mockRestoreData,
    isPending: false,
    error: null,
  }),
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

afterEach(async () => {
  await i18next.changeLanguage("en");
});

describe("document language", () => {
  it("keeps <html lang> in sync with the UI language", async () => {
    await i18next.changeLanguage("de");
    expect(document.documentElement.lang).toBe("de");
    await i18next.changeLanguage("ja");
    expect(document.documentElement.lang).toBe("ja");
  });
});

describe("Navigation", () => {
  it("is a labelled navigation landmark and hides the decorative icons from screen readers", async () => {
    await i18next.changeLanguage("de");
    const { container } = render(
      <MemoryRouter>
        <Navigation />
      </MemoryRouter>
    );
    expect(screen.getByRole("navigation", { name: "Hauptnavigation" })).toBeInTheDocument();
    const icons = container.querySelectorAll(".nav-icon");
    expect(icons.length).toBeGreaterThan(0);
    icons.forEach((icon) => expect(icon).toHaveAttribute("aria-hidden", "true"));
  });
});

describe("ProgressTracker semantics", () => {
  const steps: TrackerStep[] = [
    { id: 1, label: "Auswahl", status: "completed" },
    { id: 2, label: "Backup", status: "skipped" },
    { id: 3, label: "Wiederherstellen", status: "pending" },
  ];

  it("marks only the current step with aria-current and gives each circle an image role with a label", () => {
    const { container } = render(<ProgressTracker steps={steps} currentStep={3} />);
    const stepEls = container.querySelectorAll(".progress-step");
    expect(stepEls[0]).not.toHaveAttribute("aria-current");
    expect(stepEls[2]).toHaveAttribute("aria-current", "step");

    const circles = container.querySelectorAll(".step-circle");
    expect(circles).toHaveLength(3);
    circles.forEach((circle) => {
      expect(circle).toHaveAttribute("role", "img");
      expect(circle.getAttribute("aria-label")).toBeTruthy();
    });
  });
});

describe("WizardStep focus management", () => {
  it("moves focus to the step title when a step appears", async () => {
    const { default: WizardStep } = await import("../../src/components/wizard/WizardStep");
    render(
      <WizardStep stepNumber={1} title="USB-Stick vorbereiten">
        <p>content</p>
      </WizardStep>
    );
    const title = screen.getByRole("heading", { name: "USB-Stick vorbereiten" });
    expect(title).toHaveAttribute("tabindex", "-1");
    expect(document.activeElement).toBe(title);
  });
});

describe("RestoreExecution status icons", () => {
  beforeEach(() => {
    mockRestore.mockClear();
  });

  it("gives every status icon a translated text alternative", async () => {
    await i18next.changeLanguage("de");
    mockRestoreData = {
      success: false,
      restore_type: "clean",
      pre_restore_snapshot: null,
      snapshot_skipped: false,
      device_rebooted: false,
      total_duration_seconds: 3,
      steps: [
        { name: "config", status: "completed", message: "ok", error: null, duration_seconds: 1 },
        { name: "hosts", status: "skipped", message: "clean", error: null, duration_seconds: 0 },
        { name: "ntp", status: "failed", message: "boom", error: "boom", duration_seconds: 1 },
      ],
    };
    const { default: RestoreExecution } = await import(
      "../../src/components/wizard/RestoreExecution"
    );
    const { container } = render(
      <RestoreExecution
        stepNumber={3}
        deviceIp="1.2.3.4"
        deviceId="X"
        restoreType="clean"
        backupSet={null}
        onComplete={vi.fn()}
        onPrevious={vi.fn()}
      />
    );
    const labels = Array.from(container.querySelectorAll(".restore-execution__icon")).map((el) => {
      expect(el).toHaveAttribute("role", "img");
      return el.getAttribute("aria-label");
    });
    expect(labels).toEqual(["Abgeschlossen", "Übersprungen", "Fehlgeschlagen"]);
  });
});

describe("DLNA browser in the preset dialog", () => {
  it("has no axe violations in the server list and in a folder with one folder and one track", async () => {
    const { default: axe } = await import("axe-core");
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { default: RadioSearch } = await import("../../src/components/RadioSearch");
    const { fireEvent, waitFor } = await import("@testing-library/react");
    const json = (body: unknown) =>
      new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        String(url).includes("/browse")
          ? json({
              server_id: "srv",
              object_id: "0",
              items: [
                { id: "f", parent_id: "0", title: "Albums", is_container: true },
                { id: "t", parent_id: "0", title: "Song", is_container: false, artist: "Ann" },
              ],
              starting_index: 0,
              number_returned: 2,
              total_matches: 2,
              next_index: 2,
              has_more: false,
            })
          : json([{ id: "srv", name: "NAS" }])
      )
    );
    // jsdom has no layout: colour contrast is covered by the Cypress audit
    const run = () => axe.run(document.body, { rules: { "color-contrast": { enabled: false } } });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <RadioSearch isOpen presetNumber={2} onStationSelect={vi.fn()} onDlnaSelect={vi.fn()} />
      </QueryClientProvider>
    );
    fireEvent.click(document.querySelector('[data-test="dlna-mode"]')!);
    await screen.findByText("NAS");
    expect((await run()).violations).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "Open server “NAS”" }));
    await screen.findByText("Song");
    expect((await run()).violations).toEqual([]);
    await waitFor(() =>
      expect(screen.getByRole("navigation", { name: "Path" })).toBeInTheDocument()
    );

    vi.unstubAllGlobals();
  });
});
