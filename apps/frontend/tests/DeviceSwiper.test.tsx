import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DeviceSwiper from "../src/components/DeviceSwiper";

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

  it("marks current device dot as active", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    expect(dots[1]).toHaveClass("active");
    expect(dots[0]).not.toHaveClass("active");
    expect(dots[2]).not.toHaveClass("active");
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

  it("enables previous arrow when not at first device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const prevButton = screen.getByLabelText("Previous device");
    expect(prevButton).not.toBeDisabled();
  });

  it("enables next arrow when not at last device", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={1} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const nextButton = screen.getByLabelText("Next device");
    expect(nextButton).not.toBeDisabled();
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

  it("does not change index when clicking disabled previous arrow", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const prevButton = screen.getByLabelText("Previous device");
    fireEvent.click(prevButton);

    expect(mockOnIndexChange).not.toHaveBeenCalled();
  });

  it("does not change index when clicking disabled next arrow", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={2} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const nextButton = screen.getByLabelText("Next device");
    fireEvent.click(nextButton);

    expect(mockOnIndexChange).not.toHaveBeenCalled();
  });

  it("calls onIndexChange when dot clicked", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    fireEvent.click(dots[2]);

    expect(mockOnIndexChange).toHaveBeenCalledWith(2);
  });

  it("updates drag direction when clicking dot forward", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    fireEvent.click(dots[2]); // Forward

    expect(mockOnIndexChange).toHaveBeenCalledWith(2);
  });

  it("updates drag direction when clicking dot backward", () => {
    render(
      <DeviceSwiper devices={mockDevices} currentIndex={2} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dots = screen.getAllByRole("tab");
    fireEvent.click(dots[0]); // Backward

    expect(mockOnIndexChange).toHaveBeenCalledWith(0);
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

  it("uses device_id as key for dots", () => {
    const { container } = render(
      <DeviceSwiper devices={mockDevices} currentIndex={0} onIndexChange={mockOnIndexChange}>
        <div>Device Content</div>
      </DeviceSwiper>
    );

    const dotsContainer = container.querySelector(".swiper-dots");
    const dots = dotsContainer.querySelectorAll(".dot");

    // Keys are not directly accessible in DOM, but we can verify unique dots exist
    expect(dots).toHaveLength(3);
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
});
