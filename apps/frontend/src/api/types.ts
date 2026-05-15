/**
 * API Type Definitions
 * Shared types for API communication
 */
import i18next from "i18next";

/**
 * Standardized API Error Response (RFC 7807-inspired)
 * Matches backend ErrorDetail model
 */
export interface ApiError {
  /** Error category (validation_error, not_found, server_error, etc.) */
  type: string;
  /** Human-readable error title */
  title: string;
  /** HTTP status code */
  status: number;
  /** Detailed error message */
  detail: string;
  /** Request path that triggered error */
  instance?: string;
  /** Field-level validation errors (for 422 responses) */
  errors?: Array<{
    field: string;
    message: string;
    type: string;
  }>;
}

/**
 * Type guard to check if error is an ApiError
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "type" in error &&
    "title" in error &&
    "status" in error &&
    "detail" in error
  );
}

/**
 * Map error status code or type to user-friendly German message
 */
function getUserFriendlyMessage(statusOrType: number | string): string {
  const t = i18next.t.bind(i18next);
  // Map by HTTP status code
  if (typeof statusOrType === "number") {
    switch (statusOrType) {
      case 400:
        return t("errors.badRequest");
      case 401:
        return t("errors.unauthorized");
      case 403:
        return t("errors.forbidden");
      case 404:
        return t("errors.notFound");
      case 429:
        return t("errors.tooManyRequests");
      case 500:
        return t("errors.serverError");
      case 502:
        return t("errors.badGateway");
      case 503:
        return t("errors.serviceUnavailable");
      case 504:
        return t("errors.timeout");
      default:
        return t("common.error");
    }
  }

  // Map by error type string
  switch (statusOrType) {
    case "service_unavailable":
      return t("errors.serviceUnavailable");
    case "validation_error":
      return t("errors.badRequest");
    case "not_found":
      return t("errors.notFound");
    case "server_error":
      return t("errors.serverError");
    case "bad_gateway":
      return t("errors.badGateway");
    default:
      return t("common.error");
  }
}

/**
 * Extract error message from various error types.
 * Used in the API client layer for error propagation.
 * UI display should use toUserMessage() from utils/errorMessages.ts instead.
 */
export function getErrorMessage(error: unknown): string {
  // Check if it's our standardized ApiError
  if (isApiError(error)) {
    // Return user-friendly message based on status code
    return getUserFriendlyMessage(error.status);
  }

  // Check if it's an Error object
  if (error instanceof Error) {
    return error.message;
  }

  // Fallback
  return i18next.t("errors.unknown");
}

/**
 * Parse API error response into ApiError object
 * @param response - Failed fetch Response
 * @returns ApiError object or null if parsing fails
 */
export async function parseApiError(response: Response): Promise<ApiError | null> {
  try {
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      const errorData = await response.json();
      if (isApiError(errorData)) {
        return errorData;
      }
    }
  } catch (parseError) {
    console.error("Failed to parse error response:", parseError);
  }
  return null;
}

/**
 * Throw a descriptive error if the response is not OK.
 * Centralizes the `if (!response.ok)` pattern used across all API clients.
 */
export async function throwIfNotOk(response: Response, context: string): Promise<void> {
  if (response.ok) return;
  let detail: string | null = null;
  try {
    const errorData = await response.json();
    detail = errorData?.detail || (isApiError(errorData) ? errorData.title : null);
  } catch {
    // JSON parse failed — try text
    try {
      detail = await response.text();
    } catch {
      // ignore
    }
  }
  throw new Error(detail || `${context}: ${response.statusText}`);
}

/**
 * Get error type for UI styling/categorization
 */
export function getErrorType(error: unknown): string {
  if (isApiError(error)) {
    return error.type;
  }
  return "unknown";
}
