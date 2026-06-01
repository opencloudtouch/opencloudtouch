/**
 * Tests for AboutSection component
 *
 * US1 (P1): Version badge in Settings
 * US2 (P2): Device count + external links
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { QueryWrapper } from "../utils/reactQueryTestUtils";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    section: ({
      children,
      initial: _initial,
      animate: _animate,
      transition: _transition,
      ...props
    }: Record<string, unknown>) => (
      <section {...props}>{children as React.ReactNode}</section>
    ),
  },
}));

// Mock useHealth
vi.mock("../../src/hooks/useHealth");

// Mock useDevices
vi.mock("../../src/hooks/useDevices");

describe("AboutSection — US1 (P1): Version badge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders section title 'Über diese App'", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.1.5" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText(/about/i)).toBeInTheDocument();
  });

  it("renders app name 'OpenCloudTouch'", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.1.5" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText("OpenCloudTouch")).toBeInTheDocument();
  });

  it("renders version badge with v{version} when health succeeds", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.1.5" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText("v1.1.5")).toBeInTheDocument();
  });

  it("renders skeleton while version is loading", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    // Skeleton exists (test-id or role aria-hidden skeleton)
    const skeleton = document.querySelector(".skeleton");
    expect(skeleton).toBeInTheDocument();
  });

  it("renders 'Version nicht verfügbar' on error without badge styling", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText("Version unavailable")).toBeInTheDocument();
    expect(document.querySelector(".about-version-badge")).not.toBeInTheDocument();
  });

  it("renders app description text", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.1.5" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    // Description text via i18n key about.appDescription (English)
    expect(
      screen.getByText(/local control for bose soundtouch/i)
    ).toBeInTheDocument();
  });
});

describe("AboutSection — US2 (P2): Device count & external links", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders '3 devices connected' for 3 devices", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [
        { device_id: "1", name: "A" },
        { device_id: "2", name: "B" },
        { device_id: "3", name: "C" },
      ],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText("3 devices connected")).toBeInTheDocument();
  });

  it("renders 'No devices connected' for 0 devices", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText("No devices connected")).toBeInTheDocument();
    expect(screen.queryByText(/0 device/i)).not.toBeInTheDocument();
  });

  it("renders '1 device connected' for 1 device", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [{ device_id: "1", name: "A" }],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    expect(screen.getByText("1 device connected")).toBeInTheDocument();
  });

  it("renders skeleton for device count when devices are loading", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    const skeletons = document.querySelectorAll(".skeleton");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders GitHub link with correct href and security attributes", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    const githubLink = screen.getByRole("link", { name: /github/i });
    expect(githubLink).toHaveAttribute("href", "https://github.com/opencloudtouch/opencloudtouch");
    expect(githubLink).toHaveAttribute("target", "_blank");
    expect(githubLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders 'Report a problem' link with correct href", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    const issuesLink = screen.getByRole("link", { name: /report a problem/i });
    expect(issuesLink).toHaveAttribute(
      "href",
      "https://github.com/opencloudtouch/opencloudtouch/issues/new?template=bug_report.yml"
    );
    expect(issuesLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders Support link with BuyMeACoffee href", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    const bmcLink = screen.getByRole("link", { name: /support/i });
    expect(bmcLink).toHaveAttribute("href", "https://buymeacoffee.com/b49rjg5k6vj");
    expect(bmcLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("all external links have rel='noopener noreferrer'", async () => {
    const { useHealth } = await import("../../src/hooks/useHealth");
    const { useDevices } = await import("../../src/hooks/useDevices");
    vi.mocked(useHealth).mockReturnValue({
      data: { status: "ok", version: "1.0.0" },
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useHealth>);
    vi.mocked(useDevices).mockReturnValue({
      data: [],
      isLoading: false,
    } as ReturnType<typeof useDevices>);

    const { default: AboutSection } = await import("../../src/components/AboutSection");
    render(<AboutSection />, { wrapper: QueryWrapper });

    const links = screen.getAllByRole("link");
    links.forEach((link) => {
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    });
  });
});
