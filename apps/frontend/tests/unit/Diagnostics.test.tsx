import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import Diagnostics from "../../src/pages/Diagnostics";
import { getDiagnostics } from "../../src/api/diagnostics";
import { i18next } from "../../src/i18n";

vi.mock("../../src/api/diagnostics", () => ({
  getDiagnostics: vi.fn(),
}));

vi.mock("../../src/api/bugReport", () => ({
  downloadDiagnostics: vi.fn(),
}));

vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: vi.fn() }),
}));

const diagnostics = {
  server: {
    version: "1.6.0",
    python_version: "3.13",
    platform: "Linux",
    discovery_enabled: true,
    mock_mode: false,
    log_level: "INFO",
    manual_device_ips: 0,
    timestamp: "2026-10-25T00:00:00Z",
  },
  devices: [],
  db_stats: { devices: 0, presets: 0 },
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("Diagnostics retry", () => {
  beforeEach(async () => {
    await i18next.changeLanguage("en");
    vi.clearAllMocks();
  });

  it("shows Retry after a failed request, then loading and data on success", async () => {
    const retry = deferred<typeof diagnostics>();
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("Connection lost"))
      .mockImplementationOnce(() => retry.promise);

    render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );

    const button = await screen.findByRole("button", { name: "Retry" });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/.+/);
    expect(alert).not.toHaveTextContent("Retry");
    expect(alert.parentElement).toHaveClass("dg-retry-region");
    expect(button).toBeEnabled();
    // Back to Info is first in tab order; Retry is the next focusable control.
    const backLink = screen.getByRole("link", { name: "Info" });
    const user = userEvent.setup();
    await user.tab();
    expect(backLink).toHaveFocus();
    await user.tab();
    expect(button).toHaveFocus();
    expect(button).toHaveAttribute("type", "button");

    fireEvent.click(button);
    expect(screen.getByRole("status")).toHaveTextContent("Loading...");
    expect(screen.getByRole("status")).toHaveClass("dg-retry-region");
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();

    retry.resolve(diagnostics);
    await waitFor(() => {
      expect(screen.getByText("1.6.0")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1, name: "Diagnostics" })).toHaveFocus();
    });
    expect(getDiagnostics).toHaveBeenCalledTimes(2);
  });

  it("shows Retry again when the second request also fails", async () => {
    const retry = deferred<typeof diagnostics>();
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("First failure"))
      .mockImplementationOnce(() => retry.promise);

    render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(screen.getByRole("status")).toHaveTextContent("Loading...");

    retry.reject(new Error("Second failure"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/.+/);
    const retryButton = screen.getByRole("button", { name: "Retry" });
    expect(retryButton).toBeEnabled();
    expect(retryButton).toHaveFocus();
    expect(getDiagnostics).toHaveBeenCalledTimes(2);
  });

  it("allows another retry after a repeated failure", async () => {
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("First failure"))
      .mockRejectedValueOnce(new Error("Second failure"))
      .mockResolvedValueOnce(diagnostics);

    render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );
    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/.+/);

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(screen.getByText("1.6.0")).toBeInTheDocument();
    });
    expect(getDiagnostics).toHaveBeenCalledTimes(3);
  });

  it("does not refetch loaded diagnostics when the language changes", async () => {
    vi.mocked(getDiagnostics).mockResolvedValueOnce(diagnostics);
    render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );
    expect(await screen.findByText("1.6.0")).toBeInTheDocument();

    await act(async () => {
      await i18next.changeLanguage("de");
    });
    expect(screen.getByRole("heading", { level: 1, name: "Diagnose" })).toBeInTheDocument();
    expect(screen.getByText("1.6.0")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(getDiagnostics).toHaveBeenCalledTimes(1);
  });

  it("keeps a retriable error state when the error message is empty", async () => {
    vi.mocked(getDiagnostics).mockRejectedValueOnce(new Error(""));
    render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(i18next.t("errors.unknown"));
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();

    await act(async () => {
      await i18next.changeLanguage("de");
    });
    expect(screen.getByRole("alert")).toHaveTextContent(i18next.t("errors.unknown"));
    expect(screen.getByRole("button", { name: "Erneut versuchen" })).toBeEnabled();
    expect(getDiagnostics).toHaveBeenCalledTimes(1);
  });

  it("ignores a pending retry after leaving and does not steal focus on return", async () => {
    const retry = deferred<typeof diagnostics>();
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("Network error"))
      .mockImplementationOnce(() => retry.promise)
      .mockResolvedValueOnce(diagnostics);

    const view = render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );
    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(screen.getByRole("status")).toBeInTheDocument();

    view.unmount();
    await act(async () => {
      retry.resolve(diagnostics);
      await retry.promise;
    });

    render(
      <MemoryRouter>
        <Diagnostics />
      </MemoryRouter>
    );
    expect(await screen.findByText("1.6.0")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Diagnostics" })).not.toHaveFocus();
    expect(getDiagnostics).toHaveBeenCalledTimes(3);
  });
});
