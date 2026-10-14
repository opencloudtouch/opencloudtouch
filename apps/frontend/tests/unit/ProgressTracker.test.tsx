/**
 * Tests for ProgressTracker — branch coverage for the status-driven aria-label
 * selection and description/label fallbacks (see plan-extension-research.md A1).
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import ProgressTracker, { WizardStep } from "../../src/components/wizard/ProgressTracker";

// One step per (status × description-present/absent) combination, covering all
// four branches of the aria-label ternary chain and both sides of each of
// their `description || ""` fallbacks, plus the title's `?? step.label`
// fallback and the icon selection (checkmark / cross / number).
const steps: WizardStep[] = [
  { id: 1, label: "Prepare USB", status: "pending" },
  { id: 2, label: "Detect Device", description: "Detect the SoundTouch on the network", status: "pending" },
  { id: 3, label: "Backup Config", status: "in-progress" },
  { id: 4, label: "Modify Config", description: "Point the device at the new server", status: "in-progress" },
  { id: 5, label: "Verify Setup", status: "completed" },
  { id: 6, label: "Finalize", description: "Write the final configuration", status: "completed" },
  { id: 7, label: "Reboot Device", status: "error" },
  { id: 8, label: "Confirm Redirect", description: "Confirm DNS redirect resolves", status: "error" },
];

describe("ProgressTracker", () => {
  it("renders a title and status-appropriate aria-label for every status/description combination", () => {
    const { container } = render(<ProgressTracker steps={steps} currentStep={3} />);

    const circles = container.querySelectorAll(".step-circle");
    expect(circles).toHaveLength(8);

    // Title: falls back to label when description is absent, uses description when present.
    expect(circles[0]).toHaveAttribute("title", "Prepare USB");
    expect(circles[1]).toHaveAttribute("title", "Detect the SoundTouch on the network");
    expect(circles[2]).toHaveAttribute("title", "Backup Config");
    expect(circles[3]).toHaveAttribute("title", "Point the device at the new server");
    expect(circles[4]).toHaveAttribute("title", "Verify Setup");
    expect(circles[5]).toHaveAttribute("title", "Write the final configuration");
    expect(circles[6]).toHaveAttribute("title", "Reboot Device");
    expect(circles[7]).toHaveAttribute("title", "Confirm DNS redirect resolves");

    // aria-label: each status routes to its own t() call; each call's own
    // description fallback (`description || ""`) is exercised by the
    // no-description sibling in the same status pair. Assert on the parts
    // that come straight from props, not on exact translated punctuation.
    const pendingNoDesc = circles[0].getAttribute("aria-label") ?? "";
    expect(pendingNoDesc).toContain("Prepare USB");
    expect(pendingNoDesc).not.toContain("undefined");

    const pendingWithDesc = circles[1].getAttribute("aria-label") ?? "";
    expect(pendingWithDesc).toContain("Detect Device");
    expect(pendingWithDesc).toContain("Detect the SoundTouch on the network");

    const inProgressNoDesc = circles[2].getAttribute("aria-label") ?? "";
    expect(inProgressNoDesc).toContain("Backup Config");
    expect(inProgressNoDesc).not.toContain("undefined");

    const inProgressWithDesc = circles[3].getAttribute("aria-label") ?? "";
    expect(inProgressWithDesc).toContain("Modify Config");
    expect(inProgressWithDesc).toContain("Point the device at the new server");

    const completedNoDesc = circles[4].getAttribute("aria-label") ?? "";
    expect(completedNoDesc).toContain("Verify Setup");
    expect(completedNoDesc).not.toContain("undefined");

    const completedWithDesc = circles[5].getAttribute("aria-label") ?? "";
    expect(completedWithDesc).toContain("Finalize");
    expect(completedWithDesc).toContain("Write the final configuration");

    const errorNoDesc = circles[6].getAttribute("aria-label") ?? "";
    expect(errorNoDesc).toContain("Reboot Device");
    expect(errorNoDesc).not.toContain("undefined");

    const errorWithDesc = circles[7].getAttribute("aria-label") ?? "";
    expect(errorWithDesc).toContain("Confirm Redirect");
    expect(errorWithDesc).toContain("Confirm DNS redirect resolves");

    // The four aria-label branches must actually differ from each other
    // (proves the ternary chain picks a different t() key per status, not
    // the same fallback every time).
    const labels = [pendingNoDesc, inProgressNoDesc, completedNoDesc, errorNoDesc];
    expect(new Set(labels).size).toBe(4);
  });

  it("selects the checkmark icon for completed, the cross icon for error, and the step number otherwise", () => {
    const { container } = render(<ProgressTracker steps={steps} currentStep={3} />);

    const stepDivs = container.querySelectorAll(".progress-step");
    expect(stepDivs).toHaveLength(8);

    // pending (index 0) and in-progress (index 2) show the plain step number.
    expect(stepDivs[0].querySelector(".step-number")?.textContent).toBe("1");
    expect(stepDivs[0].querySelector(".step-icon")).toBeNull();
    expect(stepDivs[2].querySelector(".step-number")?.textContent).toBe("3");
    expect(stepDivs[2].querySelector(".step-icon")).toBeNull();

    // completed (index 4) shows the checkmark.
    expect(stepDivs[4].querySelector(".step-icon")?.textContent).toBe("✓");
    expect(stepDivs[4].querySelector(".step-number")).toBeNull();

    // error (index 6) shows the cross.
    expect(stepDivs[6].querySelector(".step-icon")?.textContent).toBe("✗");
    expect(stepDivs[6].querySelector(".step-number")).toBeNull();
  });

  it("marks only the step matching currentStep as active, and omits the connector after the last step", () => {
    const { container } = render(<ProgressTracker steps={steps} currentStep={3} />);

    const stepDivs = container.querySelectorAll(".progress-step");

    // currentStep=3 → only the third step (id 3, index 2) gets the "active" class.
    expect(stepDivs[2].className).toContain("active");
    expect(stepDivs[0].className).not.toContain("active");
    expect(stepDivs[7].className).not.toContain("active");

    // Every step except the last renders a connector; the last does not.
    expect(stepDivs[0].querySelector(".step-connector")).not.toBeNull();
    expect(stepDivs[6].querySelector(".step-connector")).not.toBeNull();
    expect(stepDivs[7].querySelector(".step-connector")).toBeNull();
  });
});
