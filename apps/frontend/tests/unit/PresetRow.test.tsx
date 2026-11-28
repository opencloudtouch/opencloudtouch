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
      <PresetRow
        number={1}
        preset={preset}
        state="starting"
        onToggle={onToggle}
        onChange={vi.fn()}
      />
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

  it.each([
    ["an occupied", preset],
    ["an empty", null],
  ])("%s row shows the saving progress and ignores taps while it saves", (_label, p) => {
    const onToggle = vi.fn();
    const onChange = vi.fn();
    render(
      <PresetRow number={3} preset={p} state="saving" onToggle={onToggle} onChange={onChange} />
    );
    expect(screen.getByText("Saving to preset 3 …")).toBeInTheDocument();
    const main = screen.getByTestId(p ? "preset-play-3" : "preset-empty-3");
    expect(main).toHaveAttribute("aria-busy", "true");
    fireEvent.click(main);
    expect(onToggle).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
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

  it("dlna preset shows cover or the dlna badge and no DLNA label", () => {
    const { rerender, container } = render(
      <PresetRow
        number={1}
        preset={{ station_name: "Album", dlna: true }}
        state="idle"
        onToggle={vi.fn()}
        onChange={vi.fn()}
      />
    );
    expect(container.querySelector(".pb-dlna")).toBeInTheDocument();
    expect(screen.getByText("DLNA", { selector: ".visually-hidden" })).toBeInTheDocument();
    expect(
      screen.queryByText("DLNA", { selector: ".pr-name, .pr-name *, .pr-state *" })
    ).toBeNull();

    rerender(
      <PresetRow
        number={1}
        preset={{ station_name: "Album", dlna: true, station_favicon: "http://x/c.png" }}
        state="idle"
        onToggle={vi.fn()}
        onChange={vi.fn()}
      />
    );
    expect(container.querySelector(".pb-favicon")).toBeInTheDocument();
    expect(container.querySelector(".pb-dlna")).not.toBeInTheDocument();
  });

  it("non-dlna rows unchanged", () => {
    const { container } = render(
      <PresetRow number={1} preset={preset} state="idle" onToggle={vi.fn()} onChange={vi.fn()} />
    );
    expect(container.querySelector(".pb-dlna")).not.toBeInTheDocument();
    expect(container.querySelector(".pb-avatar")).toBeInTheDocument();
    expect(screen.queryByText("DLNA")).not.toBeInTheDocument();
  });
  it("a broken logo falls back to the avatar and a new logo URL shows again without remount", () => {
    const row = (favicon: string) => (
      <PresetRow
        number={1}
        preset={{ station_name: "SWR3", station_favicon: favicon }}
        state="idle"
        onToggle={vi.fn()}
        onChange={vi.fn()}
      />
    );
    const { rerender, container } = render(row("http://x/broken.png"));
    const broken = container.querySelector(".pb-favicon");
    expect(broken).not.toBeNull();
    if (broken) fireEvent.error(broken);
    expect(container.querySelector(".pb-favicon")).not.toBeInTheDocument();
    expect(container.querySelector(".pb-avatar")).toBeVisible();

    rerender(row("http://x/new.png"));
    expect(container.querySelector(".pb-favicon")).toHaveAttribute("src", "http://x/new.png");
    expect(container.querySelector(".pb-avatar")).not.toBeInTheDocument();
  });

  it.each([
    ["no artist, no state", null, "idle"],
    ["artist only", "Some Artist", "idle"],
    ["state only", null, "playing"],
    ["artist and state", "Some Artist", "playing"],
  ] as const)("always reserves line 2 below the title (%s)", (_case, artist, state) => {
    render(
      <PresetRow
        number={4}
        preset={{ station_name: "Track", dlna: true, station_artist: artist }}
        state={state}
        onToggle={vi.fn()}
        onChange={vi.fn()}
      />
    );
    const title = screen.getByText("Track");
    const line2 = title.nextElementSibling;
    expect(line2).toHaveClass("pr-state");
    const artistEl = line2?.querySelector(".pr-artist");
    if (artist) expect(artistEl).toHaveTextContent(artist);
    else expect(artistEl).toBeNull();
    if (state === "playing") expect(line2).toHaveTextContent("Playing");
  });
});
