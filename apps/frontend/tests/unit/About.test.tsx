import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { QueryWrapper } from "../utils/reactQueryTestUtils";
import { useHealth } from "../../src/hooks/useHealth";
import About from "../../src/pages/About";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...props}>{children as React.ReactNode}</div>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...props}>{children as React.ReactNode}</span>
    ),
  },
}));

// Mock useHealth
vi.mock("../../src/hooks/useHealth");

const CSV_HEADER = "name,type,amount,monthlyAmount,firstSupportDate\n";
const CSV_DATA =
  CSV_HEADER + "Alice,monthly,100,20,2024-01-01\nBob,one-time,50,0,2024-02-01\n";

function setupHealthMock(version = "1.5.0") {
  vi.mocked(useHealth).mockReturnValue({
    data: { version },
    isLoading: false,
  } as ReturnType<typeof useHealth>);
}

function mockFetchWith(csvResponse: { ok: boolean; text?: () => Promise<string> }) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/supporters.csv") {
      return Promise.resolve(csvResponse as Response);
    }
    return Promise.resolve({ ok: false } as Response);
  });
}

describe("About page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders OpenCloudTouch title", () => {
    setupHealthMock();
    mockFetchWith({ ok: false });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    expect(screen.getByText("OpenCloudTouch")).toBeTruthy();
  });

  it("renders version badge when health data available", () => {
    setupHealthMock("1.5.0");
    mockFetchWith({ ok: false });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    expect(screen.getByText("v1.5.0")).toBeTruthy();
  });

  it("renders supporters from CSV", async () => {
    setupHealthMock();
    mockFetchWith({ ok: true, text: () => Promise.resolve(CSV_DATA) });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeTruthy();
      expect(screen.getByText("Bob")).toBeTruthy();
    });
  });

  it("handles empty supporters CSV", async () => {
    setupHealthMock();
    mockFetchWith({ ok: true, text: () => Promise.resolve(CSV_HEADER) });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    await waitFor(() => {
      expect(screen.queryByText("Supp❤️rters")).toBeNull();
    });
  });

  it("handles failed supporters fetch", async () => {
    setupHealthMock();
    mockFetchWith({ ok: false });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    await waitFor(() => {
      expect(screen.queryByText("Supp❤️rters")).toBeNull();
    });
  });

  it("handles fetch error gracefully", async () => {
    setupHealthMock();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/supporters.csv") {
        return Promise.reject(new Error("Network error"));
      }
      return Promise.resolve({ ok: false } as Response);
    });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith("Failed to load supporters:", expect.any(Error));
    });
  });

  it("renders GitHub and support links", () => {
    setupHealthMock();
    mockFetchWith({ ok: false });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs.some((h) => h?.includes("github.com/opencloudtouch"))).toBe(true);
    expect(hrefs.some((h) => h?.includes("buymeacoffee.com"))).toBe(true);
  });

  it("strips BOM from CSV", async () => {
    setupHealthMock();
    const bomCsv = "\uFEFF" + CSV_DATA;
    mockFetchWith({ ok: true, text: () => Promise.resolve(bomCsv) });

    render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeTruthy();
    });
  });

  it("shows monthly supporters with correct class", async () => {
    setupHealthMock();
    mockFetchWith({ ok: true, text: () => Promise.resolve(CSV_DATA) });

    const { container } = render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    await waitFor(() => {
      const monthlyNames = container.querySelectorAll(".supporter-name-wimmelbild.monthly");
      expect(monthlyNames.length).toBeGreaterThan(0);
    });
  });
});
