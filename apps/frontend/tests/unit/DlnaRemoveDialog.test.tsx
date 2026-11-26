import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DlnaRemoveDialog from "../../src/components/dlna/DlnaRemoveDialog";
import { ApiError } from "../../src/api/types";
import * as api from "../../src/api/dlna";

vi.mock("../../src/api/dlna");

function setup(onClose = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DlnaRemoveDialog deviceId="d" serverId="s" serverName="Alpha" onClose={onClose} />
    </QueryClientProvider>
  );
  return onClose;
}

const slotsError = () =>
  new ApiError("x", { status: 409, code: "dlna_native_slots_affected", extra: { slots: [2, 5] } });

describe("DlnaRemoveDialog", () => {
  beforeEach(() => vi.resetAllMocks());

  it("removes without force and closes", async () => {
    vi.mocked(api.disableNativeServer).mockResolvedValue();
    const onClose = setup();
    await userEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    expect(api.disableNativeServer).toHaveBeenCalledWith("d", "s", false);
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("remove with slots shows the slot numbers and removes anyway with force", async () => {
    vi.mocked(api.disableNativeServer).mockRejectedValueOnce(slotsError()).mockResolvedValue();
    const onClose = setup();
    await userEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    expect(await screen.findByText(/slots 2, 5/i)).toBeInTheDocument();
    expect(screen.getByTestId("confirm-dialog-cancel")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Remove anyway" }));
    expect(api.disableNativeServer).toHaveBeenLastCalledWith("d", "s", true);
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("cancel after the slot warning does not force", async () => {
    vi.mocked(api.disableNativeServer).mockRejectedValue(slotsError());
    const onClose = setup();
    await userEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    await screen.findByText(/slots 2, 5/i);
    await userEvent.click(screen.getByTestId("confirm-dialog-cancel"));
    expect(onClose).toHaveBeenCalled();
    expect(api.disableNativeServer).toHaveBeenCalledTimes(1);
  });

  it("other failures show a retryable message", async () => {
    vi.mocked(api.disableNativeServer).mockRejectedValue(new Error("boom"));
    const onClose = setup();
    await userEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    expect(await screen.findByText(/could not be removed/i)).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
