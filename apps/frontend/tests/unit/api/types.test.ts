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
        [400, "Ungültige Anfrage"],
        [401, "Nicht autorisiert"],
        [403, "Zugriff verweigert"],
        [404, "Nicht gefunden"],
        [429, "Zu viele Anfragen - bitte warten"],
        [500, "Serverfehler"],
        [502, "Gateway-Fehler"],
        [503, "Dienst nicht verfügbar"],
        [504, "Zeitüberschreitung"],
        [418, "Ein Fehler ist aufgetreten"], // Unknown code -> generic message
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
      expect(getErrorMessage("string")).toBe("Ein unerwarteter Fehler ist aufgetreten");
      expect(getErrorMessage(42)).toBe("Ein unerwarteter Fehler ist aufgetreten");
      expect(getErrorMessage(null)).toBe("Ein unerwarteter Fehler ist aufgetreten");
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
});
