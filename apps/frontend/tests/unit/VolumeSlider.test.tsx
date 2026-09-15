/**
 * Tests for VolumeSlider.tsx
 *
 * User Story: "Als User möchte ich die Lautstärke präzise steuern"
 *
 * Focus: Functional tests for volume control
 * - Volume display via aria-valuenow
 * - Mute/Unmute toggle
 * - Keyboard navigation (Arrow keys)
 * - Muted visual state
 * - Accessibility (aria-labels)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import VolumeSlider from "../../src/components/VolumeSlider";

describe("VolumeSlider Component", () => {
  describe("Volume Display & Controls", () => {
    it("should render slider with correct volume and aria range attributes", () => {
      render(
        <VolumeSlider volume={45} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      const slider = screen.getByRole("slider");
      expect(slider).toHaveAttribute("aria-valuemin", "0");
      expect(slider).toHaveAttribute("aria-valuemax", "100");
      expect(slider).toHaveAttribute("aria-valuenow", "45");
    });

    it("should call onVolumeChange with +5 on ArrowRight", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(55);
    });

    it("should call onVolumeChange with -5 on ArrowLeft", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowLeft" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(45);
    });

    it("should clamp ArrowLeft at 0", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={3} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowLeft" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(0);
    });

    it("should clamp ArrowRight at 100", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={98} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(100);
    });
  });

  describe("Mute Functionality", () => {
    it("should toggle mute when button clicked", () => {
      const mockOnMuteToggle = vi.fn();
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={mockOnMuteToggle} />
      );
      fireEvent.click(screen.getByRole("button", { name: "Mute" }));
      expect(mockOnMuteToggle).toHaveBeenCalledTimes(1);
    });

    it("should apply muted CSS class to track when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("slider")).toHaveClass("muted");
    });

    it("should show unmute label when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("button", { name: "Unmute" })).toBeInTheDocument();
    });

    it("should show mute label when not muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("button", { name: "Mute" })).toBeInTheDocument();
    });

    it("should apply muted CSS class to mute button when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("button", { name: "Unmute" })).toHaveClass("muted");
    });
  });

  describe("Accessibility", () => {
    it("should have aria-label Volume on slider", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("slider", { name: "Volume" })).toBeInTheDocument();
    });

    it("should have tabIndex 0 for keyboard access", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("slider")).toHaveAttribute("tabindex", "0");
    });
  });

  describe("Pointer Drag Interactions", () => {
    // jsdom does not implement setPointerCapture / releasePointerCapture
    beforeEach(() => {
      HTMLElement.prototype.setPointerCapture = vi.fn();
      HTMLElement.prototype.releasePointerCapture = vi.fn();
    });
    it("should call onVolumeChange after pointerdown + pointerup", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      // Mock getBoundingClientRect for value calculation
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 0, right: 200, width: 200, top: 0, bottom: 20, height: 20, x: 0, y: 0, toJSON: vi.fn(),
      });

      // Simulate drag: pointerdown at 50% → pointerup at same position
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 100, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(50);
    });

    it("should update final value based on pointerup position", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={0} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 0, right: 200, width: 200, top: 0, bottom: 20, height: 20, x: 0, y: 0, toJSON: vi.fn(),
      });

      fireEvent.pointerDown(track, { clientX: 10, pointerId: 1 });
      fireEvent.pointerMove(track, { clientX: 150, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 150, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(75);
    });

    it("should not call onVolumeChange on pointerMove without pointerDown", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;

      fireEvent.pointerMove(track, { clientX: 100, pointerId: 1 });

      expect(mockOnVolumeChange).not.toHaveBeenCalled();
    });

    it("should ignore pointerUp without prior pointerDown", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;

      fireEvent.pointerUp(track, { clientX: 100, pointerId: 1 });

      expect(mockOnVolumeChange).not.toHaveBeenCalled();
    });

    it("should clamp drag value to 0-100 range", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 100, right: 300, width: 200, top: 0, bottom: 20, height: 20, x: 100, y: 0, toJSON: vi.fn(),
      });

      // Drag past right edge
      fireEvent.pointerDown(track, { clientX: 400, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 400, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(100);
    });

    it("should clamp drag to 0 when dragging past left edge", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 100, right: 300, width: 200, top: 0, bottom: 20, height: 20, x: 100, y: 0, toJSON: vi.fn(),
      });

      // Drag past left edge
      fireEvent.pointerDown(track, { clientX: 50, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 50, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(0);
    });
  });

  describe("Programmatic rAF Flush & Throttle Branches", () => {
    let rafCallbacks: FrameRequestCallback[];
    let rafHandle: number;

    beforeEach(() => {
      HTMLElement.prototype.setPointerCapture = vi.fn();
      HTMLElement.prototype.releasePointerCapture = vi.fn();
      rafCallbacks = [];
      rafHandle = 0;
      vi.stubGlobal(
        "requestAnimationFrame",
        vi.fn((cb: FrameRequestCallback) => {
          rafCallbacks.push(cb);
          rafHandle += 1;
          return rafHandle;
        }),
      );
      vi.stubGlobal("cancelAnimationFrame", vi.fn());
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    });

    afterEach(() => {
      vi.useRealTimers();
      vi.unstubAllGlobals();
    });

    function flushRaf() {
      const cb = rafCallbacks.shift();
      expect(cb).toBeDefined();
      cb!(0);
    }

    function setup(volume = 50) {
      const mockOnVolumeChange = vi.fn();
      const { container, rerender } = render(
        <VolumeSlider volume={volume} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      const fill = container.querySelector(".volume-track-fill") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 0, right: 200, width: 200, top: 0, bottom: 20, height: 20, x: 0, y: 0, toJSON: vi.fn(),
      });
      return { mockOnVolumeChange, track, fill, rerender };
    }

    it("does not sync the volume prop to the DOM while a drag is in progress", () => {
      const { track, fill, rerender } = setup(50);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 }); // drags to 50%, isDraggingRef = true
      expect(fill.style.width).toBe("50%");

      // still dragging (no pointerUp yet) - parent re-renders with a new volume prop
      rerender(<VolumeSlider volume={90} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />);

      // the sync effect must have early-returned: DOM still reflects the drag value, not the new prop
      expect(fill.style.width).toBe("50%");
    });

    it("sends the value immediately on the first rAF flush of a drag", () => {
      const { mockOnVolumeChange, track } = setup(50);
      vi.setSystemTime(1000000);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerMove(track, { clientX: 150, pointerId: 1 });
      flushRaf();
      expect(mockOnVolumeChange).toHaveBeenCalledWith(75);
    });

    it("throttles a second rAF flush inside the 150ms window, then sends once the window elapses", () => {
      const { mockOnVolumeChange, track } = setup(50);
      vi.setSystemTime(1000000);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerMove(track, { clientX: 150, pointerId: 1 });
      flushRaf(); // immediate send (75), lastSentRef = 1000000
      expect(mockOnVolumeChange).toHaveBeenCalledTimes(1);

      vi.setSystemTime(1000050); // 50ms later, within the throttle window
      fireEvent.pointerMove(track, { clientX: 160, pointerId: 1 });
      flushRaf(); // now-lastSent=50 < 150 -> schedules a setTimeout instead of sending
      expect(mockOnVolumeChange).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(1);

      vi.advanceTimersByTime(150); // let the scheduled timer fire
      expect(mockOnVolumeChange).toHaveBeenCalledTimes(2);
      expect(mockOnVolumeChange).toHaveBeenLastCalledWith(80);
    });

    it("does not schedule a second throttle timer while one is already pending", () => {
      const { mockOnVolumeChange, track } = setup(50);
      vi.setSystemTime(1000000);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerMove(track, { clientX: 150, pointerId: 1 });
      flushRaf(); // immediate send
      vi.setSystemTime(1000050);
      fireEvent.pointerMove(track, { clientX: 160, pointerId: 1 });
      flushRaf(); // schedules the throttle timer
      expect(vi.getTimerCount()).toBe(1);

      vi.setSystemTime(1000060);
      fireEvent.pointerMove(track, { clientX: 170, pointerId: 1 });
      flushRaf(); // timer already pending -> else-if false branch, no second timer created
      expect(vi.getTimerCount()).toBe(1);
      expect(mockOnVolumeChange).toHaveBeenCalledTimes(1); // still just the one immediate send
    });

    it("does not double-schedule an animation frame when a frame is already pending", () => {
      const { track } = setup(50);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 }); // schedules a frame
      fireEvent.pointerDown(track, { clientX: 110, pointerId: 1 }); // frame still pending -> no-op
      expect(rafCallbacks).toHaveLength(1);
    });

    it("a stale animation frame that fires after the drag ended is a no-op", () => {
      const { mockOnVolumeChange, track } = setup(50);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 100, pointerId: 1 });
      const callsAfterUp = mockOnVolumeChange.mock.calls.length;

      // the frame scheduled by pointerDown was never cancelled (cancelAnimationFrame is a no-op
      // here), so it still fires after the drag ended - it must not call onVolumeChange again.
      flushRaf();
      expect(mockOnVolumeChange.mock.calls).toHaveLength(callsAfterUp);
    });

    it("pointerUp clears a pending throttle timer so it never fires again", () => {
      const { mockOnVolumeChange, track } = setup(50);
      vi.setSystemTime(1000000);
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerMove(track, { clientX: 150, pointerId: 1 });
      flushRaf(); // immediate send, lastSentRef = 1000000
      vi.setSystemTime(1000050);
      fireEvent.pointerMove(track, { clientX: 160, pointerId: 1 });
      flushRaf(); // schedules the throttle timer
      expect(vi.getTimerCount()).toBe(1);

      const callsBeforeUp = mockOnVolumeChange.mock.calls.length;
      fireEvent.pointerUp(track, { clientX: 160, pointerId: 1 }); // clears the pending timer

      expect(vi.getTimerCount()).toBe(0);
      // pointerUp itself sends the final value once (unthrottled)
      expect(mockOnVolumeChange.mock.calls).toHaveLength(callsBeforeUp + 1);
      // advancing timers must not trigger another send - the timer was cleared
      vi.advanceTimersByTime(200);
      expect(mockOnVolumeChange.mock.calls).toHaveLength(callsBeforeUp + 1);
    });
  });
});
