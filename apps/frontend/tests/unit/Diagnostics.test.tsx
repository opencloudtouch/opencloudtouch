import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Diagnostics from "../../src/pages/Diagnostics";
import { getDiagnostics } from "../../src/api/diagnostics";

vi.mock("../../src/api/diagnostics", () => ({
  getDiagnostics: vi.fn(),
}));

vi.mock("../../src/api/bugReport", () => ({
  downloadDiagnostics: vi.fn(),
}));

vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: vi.fn() }),
}));

let errorLanguage = "en";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => (key === "common.error" ? `${errorLanguage}:error` : key),
  }),
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
  beforeEach(() => {
    errorLanguage = "en";
    vi.clearAllMocks();
  });

  it("shows Retry after a failed request, then loading and data on success", async () => {
    const retry = deferred<typeof diagnostics>();
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("Connection lost"))
      .mockImplementationOnce(() => retry.promise);

    render(<Diagnostics />);

    const button = await screen.findByRole("button", { name: "common.retry" });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Connection lost");
    expect(alert).not.toHaveTextContent("common.retry");
    expect(alert.parentElement).toHaveClass("diagnostics-state");
    expect(button).toBeEnabled();
    // The retry action is the first and only tabbable control inside this page.
    expect(screen.getAllByRole("button")).toEqual([button]);
    expect(button).toHaveAttribute("type", "button");

    fireEvent.click(button);
    expect(screen.getByRole("status")).toHaveTextContent("common.loading");
    expect(screen.getByRole("status")).toHaveClass("diagnostics-state");
    expect(screen.queryByRole("button", { name: "common.retry" })).not.toBeInTheDocument();

    retry.resolve(diagnostics);
    await waitFor(() => {
      expect(screen.getByText("1.6.0")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "diagnostics.title" })).toHaveFocus();
    expect(getDiagnostics).toHaveBeenCalledTimes(2);
  });

  it("shows Retry again when the second request also fails", async () => {
    const retry = deferred<typeof diagnostics>();
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("First failure"))
      .mockImplementationOnce(() => retry.promise);

    render(<Diagnostics />);

    fireEvent.click(await screen.findByRole("button", { name: "common.retry" }));
    expect(screen.getByRole("status")).toHaveTextContent("common.loading");

    retry.reject(new Error("Second failure"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Second failure");
    const retryButton = screen.getByRole("button", { name: "common.retry" });
    expect(retryButton).toBeEnabled();
    expect(retryButton).toHaveFocus();
    expect(getDiagnostics).toHaveBeenCalledTimes(2);
  });

  it("allows another retry after a repeated failure", async () => {
    vi.mocked(getDiagnostics)
      .mockRejectedValueOnce(new Error("First failure"))
      .mockRejectedValueOnce(new Error("Second failure"))
      .mockResolvedValueOnce(diagnostics);

    render(<Diagnostics />);
    fireEvent.click(await screen.findByRole("button", { name: "common.retry" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Second failure");

    fireEvent.click(screen.getByRole("button", { name: "common.retry" }));
    await waitFor(() => {
      expect(screen.getByText("1.6.0")).toBeInTheDocument();
    });
    expect(getDiagnostics).toHaveBeenCalledTimes(3);
  });

  it("does not refetch loaded diagnostics when the language changes", async () => {
    vi.mocked(getDiagnostics).mockResolvedValueOnce(diagnostics);
    const view = render(<Diagnostics />);
    expect(await screen.findByText("1.6.0")).toBeInTheDocument();

    errorLanguage = "de";
    view.rerender(<Diagnostics />);
    expect(screen.getByText("1.6.0")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(getDiagnostics).toHaveBeenCalledTimes(1);
  });

  it("keeps a retriable error state when the error message is empty", async () => {
    vi.mocked(getDiagnostics).mockRejectedValueOnce(new Error(""));
    const view = render(<Diagnostics />);
    expect(await screen.findByRole("alert")).toHaveTextContent("en:error");
    expect(screen.getByRole("button", { name: "common.retry" })).toBeEnabled();

    errorLanguage = "de";
    view.rerender(<Diagnostics />);
    expect(screen.getByRole("alert")).toHaveTextContent("de:error");
    expect(getDiagnostics).toHaveBeenCalledTimes(1);
  });
});
