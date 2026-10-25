/**
 * Tests for utils/apiErrors — translated messages and field errors from ApiError.
 */
import { describe, it, expect, vi } from "vitest";
import { i18next } from "../../src/i18n";
import { ApiError } from "../../src/api/types";
import { getApiErrorMessage, getFieldErrors } from "../../src/utils/apiErrors";

const t = i18next.t.bind(i18next);

function apiError(
  init: Partial<ConstructorParameters<typeof ApiError>[1]> & { message?: string } = {}
) {
  const { message = "English detail", ...rest } = init;
  return new ApiError(message, { status: 404, ...rest });
}

describe("getApiErrorMessage", () => {
  it("returns the translated message for a known code", () => {
    const message = getApiErrorMessage(t, apiError({ code: "device_not_found" }));
    expect(message).toBe(i18next.t("errors.api.device_not_found"));
    expect(message).not.toBe("errors.api.device_not_found");
  });

  it("returns unknownWithCode containing the code for an unknown code", () => {
    const message = getApiErrorMessage(t, apiError({ code: "x_new" }));
    expect(message).toContain("x_new");
    expect(message).toBe(i18next.t("errors.api.unknownWithCode", { code: "x_new" }));
  });

  it("returns the generic message for an error without code", () => {
    const error = apiError({ status: 502, message: "<html>Bad Gateway</html>" });
    expect(getApiErrorMessage(t, error)).toBe(i18next.t("errors.api.unknown"));
  });

  it("uses the fallback key for an error without code", () => {
    expect(getApiErrorMessage(t, apiError(), "manualIpModal.saveError")).toBe(
      i18next.t("manualIpModal.saveError")
    );
  });

  it("uses the fallback for non-ApiError values", () => {
    expect(getApiErrorMessage(t, new Error("x"), "manualIpModal.saveError")).toBe(
      i18next.t("manualIpModal.saveError")
    );
    expect(getApiErrorMessage(t, "weird")).toBe(i18next.t("errors.api.unknown"));
  });

  it("strips reserved i18next option names from params", () => {
    const spy = vi.fn(
      (key: string, options?: Record<string, unknown>) => `${key}|${JSON.stringify(options)}`
    );
    const error = apiError({
      code: "device_not_found",
      params: { count: "5", context: "x", lng: "de", ns: "n", id: "abc" },
    });
    const result = getApiErrorMessage(spy as unknown as typeof t, error);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith("errors.api.device_not_found", { id: "abc" });
    expect(result).toContain("errors.api.device_not_found");
  });
});

describe("getFieldErrors", () => {
  const body422 = {
    fieldErrors: [
      { field: "body.port", path: "port", code: "validation_error", message: "server port msg" },
      { field: "body.port", path: "port", code: "validation_error", message: "second port msg" },
      { field: "body.host", path: "host", code: "mqtt_invalid_host", message: "server host msg" },
      { field: "body.name", path: "name", message: "plain server message" },
    ],
  };

  it("maps path to translated message when the key exists, else the server message", () => {
    const result = getFieldErrors(apiError({ status: 422, ...body422 }), t);
    expect(result.port).toBe(i18next.t("errors.api.validation_error"));
    expect(result.host).toBe("server host msg");
    expect(result.name).toBe("plain server message");
  });

  it("keeps the first error per path", () => {
    const result = getFieldErrors(apiError({ status: 422, ...body422 }), t);
    expect(Object.keys(result).sort()).toEqual(["host", "name", "port"]);
    expect(result.port).not.toBe("second port msg");
  });

  it("returns an empty object for errors without field errors or non-ApiErrors", () => {
    expect(getFieldErrors(apiError(), t)).toEqual({});
    expect(getFieldErrors(new Error("x"), t)).toEqual({});
  });
});
