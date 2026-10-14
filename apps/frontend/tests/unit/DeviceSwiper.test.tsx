import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DeviceSwiper from "../../src/components/DeviceSwiper";
import type { ReactNode, HTMLAttributes } from "react";

type DragInfo = {
  offset: { x: number; y: number };
  velocity: { x: number; y: number };
};
type DragEndHandler = (
  event: MouseEvent | TouchEvent | PointerEvent,
  info: DragInfo,
) => void;

let capturedOnDragEnd: DragEndHandler | undefined;

vi.mock("framer-motion", () => ({
  motion: {
    div: ({
      children,
      onDragEnd,
      ...rest
    }: {
      children: ReactNode;
      onDragEnd?: DragEndHandler;
    } & HTMLAttributes<HTMLDivElement>) => {
      capturedOnDragEnd = onDragEnd;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

describe("DeviceSwiper Component", () => {
  const mockDevices = [
    { device_id: "1", name: "Living Room", ip: "192.168.1.10" },
    { device_id: "2", name: "Küche", ip: "192.168.1.20" },
    { device_id: "3", name: "Schlafzimmer", ip: "192.168.1.30" },
  ];

  const mockOnIndexChange = vi.fn();

  beforeEach(() => {
    mockOnIndexChange.mockClear();
  });

  it("renders navigation arrows", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    expect(screen.getByLabelText("Previous device")).toBeInTheDocument();
    expect(screen.getByLabelText("Next device")).toBeInTheDocument();
  });

  it("renders dots for each device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    expect(dots).toHaveLength(3);
  });



  it("disables previous arrow at first device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const prevButton = screen.getByLabelText("Previous device");
    expect(prevButton).toBeDisabled();
  });

  it("disables next arrow at last device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={2} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const nextButton = screen.getByLabelText("Next device");
    expect(nextButton).toBeDisabled();
  });



  it("calls onIndexChange with previous index when previous arrow clicked", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={2} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const prevButton = screen.getByLabelText("Previous device");
    fireEvent.click(prevButton);

    expect(mockOnIndexChange).toHaveBeenCalledWith(1);
  });

  it("calls onIndexChange with next index when next arrow clicked", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const nextButton = screen.getByLabelText("Next device");
    fireEvent.click(nextButton);

    expect(mockOnIndexChange).toHaveBeenCalledWith(1);
  });

  it("calls onIndexChange when dot clicked", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    fireEvent.click(dots[2]!);

    expect(mockOnIndexChange).toHaveBeenCalledWith(2);
  });



  it("renders children content", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div data-testid="custom-content">Custom Device Content</div>
      </DeviceSwiper>
    );

    expect(screen.getByTestId("custom-content")).toBeInTheDocument();
    expect(screen.getByText("Custom Device Content")).toBeInTheDocument();
  });

  it("has correct aria labels for dots", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    expect(screen.getByLabelText("Switch to Living Room")).toBeInTheDocument();
    expect(screen.getByLabelText("Switch to Küche")).toBeInTheDocument();
    expect(screen.getByLabelText("Switch to Schlafzimmer")).toBeInTheDocument();
  });

  it("sets correct aria-selected on dots", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    expect(dots[0]).toHaveAttribute("aria-selected", "false");
    expect(dots[1]).toHaveAttribute("aria-selected", "true");
    expect(dots[2]).toHaveAttribute("aria-selected", "false");
  });



  it("handles single device gracefully", () => {
    const singleDevice = [{ device_id: "1", name: "Solo", ip: "192.168.1.10" }];

    render(
      <DeviceSwiper devices={singleDevice} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const prevButton = screen.getByLabelText("Previous device");
    const nextButton = screen.getByLabelText("Next device");

    expect(prevButton).toBeDisabled();
    expect(nextButton).toBeDisabled();
  });

  it("swipes right (via offset past threshold) to the previous device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: 100, y: 0 },
      velocity: { x: 0, y: 0 },
    });

    expect(mockOnIndexChange).toHaveBeenCalledWith(0);
  });

  it("swipes right (via velocity past threshold, offset below it) to the previous device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: 10, y: 0 },
      velocity: { x: 600, y: 0 },
    });

    expect(mockOnIndexChange).toHaveBeenCalledWith(0);
  });

  it("a rightward swipe gesture at the first device is a no-op", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: 100, y: 0 },
      velocity: { x: 0, y: 0 },
    });

    expect(mockOnIndexChange).not.toHaveBeenCalled();
  });

  it("swipes left (via offset past negative threshold) to the next device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: -100, y: 0 },
      velocity: { x: 0, y: 0 },
    });

    expect(mockOnIndexChange).toHaveBeenCalledWith(2);
  });

  it("swipes left (via velocity past negative threshold, offset within bounds) to the next device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: -10, y: 0 },
      velocity: { x: -600, y: 0 },
    });

    expect(mockOnIndexChange).toHaveBeenCalledWith(2);
  });

  it("a leftward swipe gesture at the last device is a no-op", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={2} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: -100, y: 0 },
      velocity: { x: 0, y: 0 },
    });

    expect(mockOnIndexChange).not.toHaveBeenCalled();
  });

  it("a gesture below both offset and velocity thresholds in either direction is a no-op", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    capturedOnDragEnd!({} as MouseEvent, {
      offset: { x: 10, y: 0 },
      velocity: { x: 10, y: 0 },
    });

    expect(mockOnIndexChange).not.toHaveBeenCalled();
  });

  it("clicking a dot before the current index sets the backward drag direction and switches", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={2} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    fireEvent.click(dots[0]!);

    expect(mockOnIndexChange).toHaveBeenCalledWith(0);
  });
});
