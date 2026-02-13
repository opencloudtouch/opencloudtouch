/**
 * API Type Definitions
 * Shared types for API communication
 */

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
  // Map by HTTP status code
  if (typeof statusOrType === "number") {
    switch (statusOrType) {
      case 400:
        return "Ungültige Anfrage";
      case 401:
        return "Nicht autorisiert";
      case 403:
        return "Zugriff verweigert";
      case 404:
        return "Nicht gefunden";
      case 429:
        return "Zu viele Anfragen - bitte warten";
      case 500:
        return "Serverfehler";
      case 502:
        return "Gateway-Fehler";
      case 503:
        return "Dienst nicht verfügbar";
      case 504:
        return "Zeitüberschreitung";
      default:
        return "Ein Fehler ist aufgetreten";
    }
  }

  // Map by error type string
  switch (statusOrType) {
    case "service_unavailable":
      return "Dienst nicht verfügbar";
    case "validation_error":
      return "Ungültige Eingabe";
    case "not_found":
      return "Nicht gefunden";
    case "server_error":
      return "Serverfehler";
    case "bad_gateway":
      return "Gateway-Fehler";
    default:
      return "Ein Fehler ist aufgetreten";
  }
}

/**
 * Extract user-friendly error message from various error types
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
  return "Ein unerwarteter Fehler ist aufgetreten";
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
 * Get error type for UI styling/categorization
 */
export function getErrorType(error: unknown): string {
  if (isApiError(error)) {
    return error.type;
  }
  return "unknown";
}
