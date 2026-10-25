/**
 * API Type Definitions
 * Shared types for API communication
 */
import i18next from "i18next";

/**
 * Standardized API Error Response (RFC 7807-inspired)
 * Matches backend ErrorDetail model
 */
export interface ApiErrorBody {
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
    /** `field` without the leading body./query./path. segment */
    path?: string;
    message: string;
    type?: string | null;
    code?: string | null;
  }> | null;
  /** Stable machine-readable error identifier */
  code?: string | null;
  /** Flat string map for message interpolation */
  params?: Record<string, string> | null;
  /** Structured data for the client (not for translation) */
  extra?: Record<string, unknown> | null;
}

/** One field-level error of an {@link ApiError}. */
export interface FieldError {
  field: string;
  path: string;
  code?: string;
  message: string;
}

export interface ApiErrorInit {
  status: number;
  code?: string;
  params?: Record<string, string>;
  extra?: Record<string, unknown>;
  fieldErrors?: FieldError[];
  body?: ApiErrorBody;
}

/**
 * Error thrown by `throwIfNotOk` for non-2xx responses.
 * `message` is the server's English `detail`; use `getApiErrorMessage`
 * (utils/apiErrors.ts) for a translated message.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly params?: Record<string, string>;
  readonly extra?: Record<string, unknown>;
  readonly fieldErrors: FieldError[];
  readonly body?: ApiErrorBody;

  constructor(message: string, init: ApiErrorInit) {
    super(message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.params = init.params;
    this.extra = init.extra;
    this.fieldErrors = init.fieldErrors ?? [];
    this.body = init.body;
  }
}

/** Type guard for {@link ApiError} instances (as opposed to the wire shape). */
export function isApiErrorInstance(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/**
 * Type guard to check if a value has the ApiErrorBody wire shape
 */
export function isApiError(error: unknown): error is ApiErrorBody {
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
  if (isApiErrorInstance(error)) {
    return error.message;
  }

  // Check if it's our standardized ApiErrorBody
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
 * Parse API error response into ApiErrorBody object
 * @param response - Failed fetch Response
 * @returns ApiErrorBody object or null if parsing fails
 */
export async function parseApiError(response: Response): Promise<ApiErrorBody | null> {
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

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stripLocationPrefix(field: string): string {
  return field.replace(/^(body|query|path|header)(\.|$)/, "");
}

function toFieldErrors(errors: unknown): FieldError[] {
  if (!Array.isArray(errors)) return [];
  const result: FieldError[] = [];
  for (const item of errors) {
    if (!isPlainObject(item) || typeof item.field !== "string") continue;
    result.push({
      field: item.field,
      path: typeof item.path === "string" ? item.path : stripLocationPrefix(item.field),
      code: typeof item.code === "string" ? item.code : undefined,
      message: typeof item.message === "string" ? item.message : "",
    });
  }
  return result;
}

/** Read the response body once as text; unreadable bodies count as empty. */
async function readBodyText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

function parseJson(text: string): { ok: true; value: unknown } | { ok: false } {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false };
  }
}

/** `detail` when it is a non-empty string, else the title of a valid ApiErrorBody. */
function messageFromBody(body: Record<string, unknown>): string | null {
  if (typeof body.detail === "string" && body.detail) return body.detail;
  if (isApiError(body) && typeof body.title === "string") return body.title;
  return null;
}

function stringParams(value: unknown): Record<string, string> | undefined {
  if (!isPlainObject(value)) return undefined;
  return Object.values(value).every((v) => typeof v === "string")
    ? (value as Record<string, string>)
    : undefined;
}

function apiErrorInitFromBody(status: number, body: Record<string, unknown>): ApiErrorInit {
  return {
    status,
    code: typeof body.code === "string" ? body.code : undefined,
    params: stringParams(body.params),
    extra: isPlainObject(body.extra) ? body.extra : undefined,
    fieldErrors: toFieldErrors(body.errors),
    body: isApiError(body) ? body : undefined,
  };
}

/**
 * Throw an {@link ApiError} if the response is not OK.
 * Centralizes the `if (!response.ok)` pattern used across all API clients.
 * The body is read once as text; `message` is the body's `detail`, else its
 * title, else the response text (non-JSON bodies), else `${context}: ${statusText}`.
 */
export async function throwIfNotOk(response: Response, context: string): Promise<void> {
  if (response.ok) return;
  const text = await readBodyText(response);
  const parsed = parseJson(text);
  const fallback = `${context}: ${response.statusText}`;

  if (!parsed.ok) {
    throw new ApiError(text || fallback, { status: response.status });
  }
  if (!isPlainObject(parsed.value)) {
    throw new ApiError(fallback, { status: response.status });
  }
  throw new ApiError(
    messageFromBody(parsed.value) || fallback,
    apiErrorInitFromBody(response.status, parsed.value)
  );
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
