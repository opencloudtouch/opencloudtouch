/**
 * Unit tests for API types and error handling utilities
 *
 * User Story: Als User sehe ich verständliche Fehlermeldungen statt HTTP-Codes
 *
 * Focus: Error message translation and type guards
 */
import { describe, it, expect, vi } from "vitest";
import {
  isApiError,
  getErrorMessage,
  parseApiError,
  getErrorType,
  throwIfNotOk,
  type ApiError,
} from "../../../src/api/types";

describe("API Types", () => {
  describe("isApiError", () => {
    it("validates ApiError object structure", () => {
      // Valid error
      const validError: ApiError = {
        type: "validation_error",
        title: "Validation Error",
        status: 400,
        detail: "Invalid input",
      };
      expect(isApiError(validError)).toBe(true);

      // With optional fields
      const withOptionals: ApiError = {
        ...validError,
        instance: "/api/devices",
        errors: [{ field: "name", message: "Required", type: "required" }],
      };
      expect(isApiError(withOptionals)).toBe(true);

      // Invalid: missing required fields
      expect(isApiError({ type: "error" })).toBe(false);
      expect(isApiError({ type: "error", title: "Title", status: 400 })).toBe(false);

      // Invalid: wrong types
      expect(isApiError(null)).toBe(false);
      expect(isApiError(undefined)).toBe(false);
      expect(isApiError("error")).toBe(false);
      expect(isApiError(42)).toBe(false);
    });
  });

  describe("getErrorMessage", () => {
    it("maps HTTP status codes to user-friendly German messages", () => {
      const httpCodeTests: Array<[number, string]> = [
        [400, "Invalid request. Please check your inputs."],
        [401, "Unauthorized. Please log in again."],
        [403, "Access denied."],
        [404, "The requested resource was not found."],
        [429, "Too many requests — please wait"],
        [500, "Server error. Please try again later."],
        [502, "Gateway error"],
        [503, "Service unavailable"],
        [504, "The request took too long. Please try again."],
        [418, "An error occurred"], // Unknown code -> generic message
      ];

      httpCodeTests.forEach(([status, expectedMessage]) => {
        const error: ApiError = {
          type: "test",
          title: "Test",
          status,
          detail: "Test detail",
        };
        expect(getErrorMessage(error)).toBe(expectedMessage);
      });
    });

    it("extracts message from standard Error objects", () => {
      const error = new Error("Custom error message");
      expect(getErrorMessage(error)).toBe("Custom error message");
    });

    it("returns fallback for unknown error types", () => {
      expect(getErrorMessage("string")).toBe("An unexpected error occurred. Please try again.");
      expect(getErrorMessage(42)).toBe("An unexpected error occurred. Please try again.");
      expect(getErrorMessage(null)).toBe("An unexpected error occurred. Please try again.");
    });

    it("maps error type strings to the same user-friendly messages as their HTTP-status equivalents", () => {
      // isApiError only checks key presence, not the `status` key's runtime type, so a
      // malformed-but-key-complete payload with a string `status` still reaches
      // getUserFriendlyMessage's string-keyed switch (the numeric switch's sibling branch).
      const typeStringTests: Array<[string, string]> = [
        ["service_unavailable", "Service unavailable"],
        ["validation_error", "Invalid request. Please check your inputs."],
        ["not_found", "The requested resource was not found."],
        ["server_error", "Server error. Please try again later."],
        ["bad_gateway", "Gateway error"],
        ["totally_unrecognized_type", "An error occurred"], // Unknown string -> generic message
      ];

      typeStringTests.forEach(([statusString, expectedMessage]) => {
        const malformedError = {
          type: "test",
          title: "Test",
          status: statusString,
          detail: "Test detail",
        } as unknown as ApiError;
        expect(getErrorMessage(malformedError)).toBe(expectedMessage);
      });
    });
  });

  describe("parseApiError", () => {
    it("parses JSON ApiError from response", async () => {
      const mockError: ApiError = {
        type: "not_found",
        title: "Not Found",
        status: 404,
        detail: "Device not found",
      };

      const mockResponse = {
        headers: { get: vi.fn().mockReturnValue("application/json; charset=utf-8") },
        json: vi.fn().mockResolvedValue(mockError),
      } as unknown as Response;

      expect(await parseApiError(mockResponse)).toEqual(mockError);
    });

    it("returns null for non-ApiError responses", async () => {
      // Non-JSON content type
      const htmlResponse = {
        headers: { get: vi.fn().mockReturnValue("text/html") },
      } as unknown as Response;
      expect(await parseApiError(htmlResponse)).toBeNull();

      // JSON parse failure
      const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      const parseErrorResponse = {
        headers: { get: vi.fn().mockReturnValue("application/json") },
        json: vi.fn().mockRejectedValue(new Error("Parse error")),
      } as unknown as Response;
      expect(await parseApiError(parseErrorResponse)).toBeNull();
      consoleSpy.mockRestore();

      // JSON but not ApiError structure
      const wrongStructure = {
        headers: { get: vi.fn().mockReturnValue("application/json") },
        json: vi.fn().mockResolvedValue({ message: "Not an ApiError" }),
      } as unknown as Response;
      expect(await parseApiError(wrongStructure)).toBeNull();
    });
  });

  describe("getErrorType", () => {
    it("extracts error type from ApiError or returns 'unknown'", () => {
      const apiError: ApiError = {
        type: "validation_error",
        title: "Validation",
        status: 422,
        detail: "Invalid",
      };
      expect(getErrorType(apiError)).toBe("validation_error");

      // Non-ApiError values
      expect(getErrorType(new Error("Test"))).toBe("unknown");
      expect(getErrorType("string")).toBe("unknown");
      expect(getErrorType(null)).toBe("unknown");
    });
  });

  describe("throwIfNotOk", () => {
    it("does nothing when the response is ok", async () => {
      const okResponse = { ok: true } as unknown as Response;
      await expect(throwIfNotOk(okResponse, "test context")).resolves.toBeUndefined();
    });

    it("throws with the response body's detail when present", async () => {
      const response = {
        ok: false,
        statusText: "Bad Request",
        json: vi.fn().mockResolvedValue({ detail: "Specific failure detail" }),
      } as unknown as Response;

      await expect(throwIfNotOk(response, "test context")).rejects.toThrow(
        "Specific failure detail",
      );
    });

    it("falls back to the ApiError's title when detail is empty but the body is a valid ApiError", () => {
      const response = {
        ok: false,
        statusText: "Bad Request",
        json: vi.fn().mockResolvedValue({
          type: "validation_error",
          title: "Friendly Title",
          status: 400,
          detail: "",
        }),
      } as unknown as Response;

      return expect(throwIfNotOk(response, "test context")).rejects.toThrow("Friendly Title");
    });

    it("falls back to context and statusText when the body has neither detail nor a valid ApiError shape", async () => {
      const response = {
        ok: false,
        statusText: "Internal Server Error",
        json: vi.fn().mockResolvedValue({ unrelated: "field" }),
      } as unknown as Response;

      await expect(throwIfNotOk(response, "loading widgets")).rejects.toThrow(
        "loading widgets: Internal Server Error",
      );
    });

    it("falls back to context and statusText when the response body isn't JSON and has no readable text", async () => {
      const response = {
        ok: false,
        statusText: "Internal Server Error",
        json: vi.fn().mockRejectedValue(new Error("not json")),
        text: vi.fn().mockRejectedValue(new Error("not readable either")),
      } as unknown as Response;

      await expect(throwIfNotOk(response, "loading widgets")).rejects.toThrow(
        "loading widgets: Internal Server Error",
      );
    });
  });
});
