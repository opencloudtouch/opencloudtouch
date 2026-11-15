import { describe, expect, it } from "vitest";
import type { TFunction } from "i18next";
import { ApiError } from "../api/types";
import { getDeviceActionError } from "./apiErrors";

// Echoes the key, so the test shows which message was chosen
const t = ((key: string) => key) as unknown as TFunction;

describe("getDeviceActionError", () => {
  it("names the offline device when the server answered device_unreachable", () => {
    const error = new ApiError("x", { status: 503, code: "device_unreachable" });
    expect(getDeviceActionError(t, error, "errors.presetSaveFailed")).toBe(
      "errors.api.device_unreachable"
    );
  });

  it("keeps the action specific message for any other failure", () => {
    const other = new ApiError("x", { status: 500, code: "internal_error" });
    expect(getDeviceActionError(t, other, "errors.presetSaveFailed")).toBe(
      "errors.presetSaveFailed"
    );
    expect(getDeviceActionError(t, new Error("boom"), "errors.presetSaveFailed")).toBe(
      "errors.presetSaveFailed"
    );
  });
});
