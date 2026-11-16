import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PresetRow from "../../src/components/PresetRow";

const preset = { station_name: "SWR3" };

describe("PresetRow", () => {
  it("is a toggle with its own change button", () => {
    const onToggle = vi.fn();
    const onChange = vi.fn();
    render(
      <PresetRow number={2} preset={preset} state="idle" onToggle={onToggle} onChange={onChange} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Play preset 2: SWR3" }));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Change station for preset 2" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("offers pause while the preset plays and play again when it is paused", () => {
    const { rerender } = render(
      <PresetRow number={1} preset={preset} state="playing" onToggle={vi.fn()} onChange={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: "Pause preset 1: SWR3" })).toBeInTheDocument();
    expect(screen.getByText("Playing")).toBeInTheDocument();

    rerender(
      <PresetRow number={1} preset={preset} state="paused" onToggle={vi.fn()} onChange={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: "Play preset 1: SWR3" })).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });

  it.each([
    ["starting", "Starting…"],
    ["failed", "Could not start"],
  ] as const)("shows the %s state as a word, not only as a colour", (state, word) => {
    render(
      <PresetRow number={3} preset={preset} state={state} onToggle={vi.fn()} onChange={vi.fn()} />
    );
    expect(screen.getByText(word)).toBeInTheDocument();
  });

  it("ignores taps while the preset is starting (busy)", () => {
    const onToggle = vi.fn();
    render(
      <PresetRow number={1} preset={preset} state="starting" onToggle={onToggle} onChange={vi.fn()} />
    );

    const main = screen.getByRole("button", { name: "Play preset 1: SWR3" });
    expect(main).toHaveAttribute("aria-busy", "true");
    fireEvent.click(main);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("a disabled row (zone member) cannot be started, but its station can still be changed", () => {
    const onToggle = vi.fn();
    const onChange = vi.fn();
    render(
      <PresetRow
        number={1}
        preset={preset}
        state="idle"
        disabled
        onToggle={onToggle}
        onChange={onChange}
      />
    );

    const main = screen.getByRole("button", { name: "Play preset 1: SWR3" });
    const edit = screen.getByRole("button", { name: "Change station for preset 1" });
    expect(main).toHaveAttribute("aria-disabled", "true");
    expect(edit).not.toHaveAttribute("aria-disabled");
    fireEvent.click(main);
    expect(onToggle).not.toHaveBeenCalled();
    fireEvent.click(edit);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("an empty row goes straight to the assignment", () => {
    const onChange = vi.fn();
    render(
      <PresetRow number={4} preset={null} state="idle" onToggle={vi.fn()} onChange={onChange} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Assign preset 4" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: /Change station/ })).not.toBeInTheDocument();
  });

  describe("DLNA preset", () => {
    const dlna = { server_id: "srv", object_id: "o1" };
    const dlnaPreset = (favicon?: string) => ({
      station_name: "Folk Songs",
      station_favicon: favicon,
      dlna,
    });
    const renderDlna = (favicon?: string, state: "idle" | "playing" = "idle") =>
      render(
        <PresetRow
          number={2}
          preset={dlnaPreset(favicon)}
          state={state}
          onToggle={vi.fn()}
          onChange={vi.fn()}
        />
      );

    it("marks the slot with an icon and the word DLNA, in every state", () => {
      const { unmount } = renderDlna();
      expect(screen.getByLabelText("From a DLNA media server")).toHaveTextContent("DLNA");
      expect(screen.getByRole("button", { name: "Play preset 2: Folk Songs" })).toBeInTheDocument();
      unmount();

      renderDlna(undefined, "playing");
      expect(screen.getByText("Playing")).toBeInTheDocument();
      expect(screen.getByLabelText("From a DLNA media server")).toBeInTheDocument();
    });

    it("shows no marker for a radio preset", () => {
      render(
        <PresetRow number={1} preset={preset} state="idle" onToggle={vi.fn()} onChange={vi.fn()} />
      );
      expect(screen.queryByLabelText("From a DLNA media server")).not.toBeInTheDocument();
    });

    it("uses the favicon as cover and a music placeholder instead of initials when there is none", () => {
      const { container, unmount } = renderDlna("http://nas.local/cover.jpg");
      expect(container.querySelector("img.pb-favicon")).toHaveAttribute(
        "src",
        "http://nas.local/cover.jpg"
      );
      unmount();

      const { container: c2 } = renderDlna();
      expect(c2.querySelector("img")).toBeNull();
      expect(c2.querySelector(".pb-logo--ph")).not.toBeNull();
      expect(c2.querySelector(".pb-avatar")).toBeNull();
    });

    it("falls back to the placeholder when the cover fails to load", () => {
      const { container } = renderDlna("http://nas.local/cover.jpg");
      fireEvent.error(container.querySelector("img")!);
      expect(container.querySelector("img")).toBeNull();
      expect(container.querySelector(".pb-logo--ph")).not.toBeNull();
    });

    it("never requests an http cover on an https page", () => {
      vi.stubGlobal("location", { protocol: "https:" });
      try {
        const { container } = renderDlna("http://nas.local/cover.jpg");
        expect(container.querySelector("img")).toBeNull();
        expect(container.querySelector(".pb-logo--ph")).not.toBeNull();
      } finally {
        vi.unstubAllGlobals();
      }
    });
  });
});
