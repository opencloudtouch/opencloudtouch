import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
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

const presence = vi.hoisted(() => ({ present: true }));
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
  useIsPresent: () => presence.present,
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

    const dots = within(screen.getByRole("group", { name: "Device selection" })).getAllByRole("button");
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

    const dots = within(screen.getByRole("group", { name: "Device selection" })).getAllByRole("button");
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

  it("marks the current device dot with aria-current", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = within(screen.getByRole("group", { name: "Device selection" })).getAllByRole("button");
    expect(dots[0]).not.toHaveAttribute("aria-current");
    expect(dots[1]).toHaveAttribute("aria-current", "true");
    expect(dots[2]).not.toHaveAttribute("aria-current");
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

    const dots = within(screen.getByRole("group", { name: "Device selection" })).getAllByRole("button");
    fireEvent.click(dots[0]!);

    expect(mockOnIndexChange).toHaveBeenCalledWith(0);
  });
});

describe("DeviceSwiper dots and leaving card", () => {
  const many = Array.from({ length: 12 }, (_, i) => ({
    device_id: `D${i}`,
    name: `Device ${i + 1}`,
    model: "SoundTouch 10",
    ip: `192.168.1.${i}`,
  })) as unknown as Parameters<typeof DeviceSwiper>[0]["devices"];

  afterEach(() => {
    presence.present = true;
    delete (HTMLElement.prototype as unknown as Record<string, unknown>).clientWidth;
  });

  it("shows only a window of dots around the current device when even 24px per dot does not fit", () => {
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 184 });
    render(
      <DeviceSwiper devices={many} currentIndex={6} onIndexChange={vi.fn()}>
        <div>Card</div>
      </DeviceSwiper>,
    );

    const group = screen.getByRole("group", { name: "Device selection" });
    const dots = within(group).getAllByRole("button");
    expect(dots).toHaveLength(7); // floor(184 / 24)
    expect(dots.filter((d) => d.getAttribute("aria-current") === "true")).toHaveLength(1);
    expect(within(group).getByRole("status")).toHaveTextContent("Device 7 of 12");
  });

  it("keeps all dots (dense, no window) when 24px per dot fits", () => {
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 456 });
    render(
      <DeviceSwiper devices={many} currentIndex={0} onIndexChange={vi.fn()}>
        <div>Card</div>
      </DeviceSwiper>,
    );
    const group = screen.getByRole("group", { name: "Device selection" });
    expect(within(group).getAllByRole("button")).toHaveLength(12);
    expect(within(group).queryByRole("status")).not.toBeInTheDocument();
  });

  it("hides the leaving card from assistive technology and makes it inert", () => {
    presence.present = false;
    const { container } = render(
      <DeviceSwiper devices={many} currentIndex={0} onIndexChange={vi.fn()}>
        <div>Card</div>
      </DeviceSwiper>,
    );
    const shell = container.querySelector(".ds-card-shell")!;
    expect(shell).toHaveAttribute("aria-hidden", "true");
    expect(shell).toHaveAttribute("data-state", "leaving");
    expect(shell.hasAttribute("inert")).toBe(true);
  });
});
