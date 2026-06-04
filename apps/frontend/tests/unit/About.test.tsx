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
    // Match /supporters.csv with or without query params (cache-busting timestamp)
    if (url.startsWith("/supporters.csv")) {
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
      // Match /supporters.csv with or without query params (cache-busting timestamp)
      if (url.startsWith("/supporters.csv")) {
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

  it("sorts supporters by amount DESC, monthlyAmount DESC, date ASC", async () => {
    setupHealthMock();
    const realCsv = [
      "name,type,amount,monthlyAmount,firstSupportDate",
      "Elvis Presley,one-time,30,0,2026-05-26",
      "Freddie Mercury,one-time,23.3,0,2026-05-28",
      "John Lennon,one-time,23.2,0,2026-05-20",
      "Paul McCartney,one-time,21.47,0,2026-06-01",
      "Mick Jagger,one-time,20,0,2026-05-11",
      "David Bowie,one-time,20,0,2026-05-16",
      "Jimi Hendrix,one-time,20,0,2026-05-16",
      "Kurt Cobain,one-time,20,0,2026-05-17",
      "Michael Jackson,one-time,20,0,2026-05-22",
      "Madonna,one-time,20,0,2026-05-23",
      "Prince,one-time,15,0,2026-06-04",
      "Elton John,one-time,11.6,0,2026-05-23",
      "Lady Gaga,one-time,11.6,0,2026-05-24",
      "Beyoncé,one-time,10,0,2026-05-10",
      "Ozzy Osbourne,one-time,10,0,2026-05-15",
      "James Hetfield,one-time,10,0,2026-05-16",
      "Dave Grohl,one-time,10,0,2026-05-17",
      "Jared Leto,one-time,10,0,2026-05-17",
      "Eminem,monthly,5,5,2026-05-20",
      "Tupac,one-time,10,0,2026-05-27",
      "Jay-Z,one-time,10,0,2026-05-31",
      "Aretha Franklin,one-time,10,0,2026-06-03",
      "Stevie Wonder,one-time,10,0,2026-06-04",
      "Whitney Houston,one-time,8.5,0,2026-05-10",
      "Marvin Gaye,one-time,8,0,2026-06-02",
      "Johnny Cash,one-time,5,0,2026-05-09",
      "Dolly Parton,one-time,5,0,2026-05-11",
      "Bob Dylan,one-time,5,0,2026-05-16",
      "Rihanna,one-time,5,0,2026-05-18",
      "Ed Sheeran,one-time,5,0,2026-05-31",
      "Bruno Mars,monthly,1,1,2026-06-02",
    ].join("\n");

    mockFetchWith({ ok: true, text: () => Promise.resolve(realCsv) });

    const { container } = render(
      <QueryWrapper>
        <About />
      </QueryWrapper>,
    );

    const expectedOrder = [
      "Elvis Presley",
      "Freddie Mercury",
      "John Lennon",
      "Paul McCartney",
      "Mick Jagger",
      "David Bowie",
      "Jimi Hendrix",
      "Kurt Cobain",
      "Michael Jackson",
      "Madonna",
      "Prince",
      "Elton John",
      "Lady Gaga",
      "Beyoncé",
      "Ozzy Osbourne",
      "James Hetfield",
      "Dave Grohl",
      "Jared Leto",
      "Tupac",
      "Jay-Z",
      "Aretha Franklin",
      "Stevie Wonder",
      "Whitney Houston",
      "Marvin Gaye",
      "Eminem",
      "Johnny Cash",
      "Dolly Parton",
      "Bob Dylan",
      "Rihanna",
      "Ed Sheeran",
      "Bruno Mars",
    ];

    await waitFor(() => {
      const names = container.querySelectorAll(".supporter-name-wimmelbild");
      expect(names.length).toBe(expectedOrder.length);
      const actualOrder = Array.from(names).map((el) => el.textContent);
      expect(actualOrder).toEqual(expectedOrder);
    });
  });
});
