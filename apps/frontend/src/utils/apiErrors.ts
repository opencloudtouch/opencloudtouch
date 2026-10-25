/**
 * Translated messages for ApiError — maps the stable server `code` to
 * `errors.api.<code>` (all locales). Never shows raw backend text for coded errors.
 */

import type { TFunction } from "i18next";
import { i18next } from "../i18n";
import { isApiErrorInstance } from "../api/types";

const RESERVED_OPTIONS = new Set([
  "count",
  "context",
  "lng",
  "ns",
  "defaultValue",
  "returnObjects",
  "interpolation",
]);

function safeParams(params: Record<string, string> | undefined): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    if (!RESERVED_OPTIONS.has(key)) result[key] = value;
  }
  return result;
}

/**
 * Message for an API failure: translated by `code` when known, a generic message
 * naming the code when unknown, otherwise `fallbackKey` (default `errors.api.unknown`).
 */
export function getApiErrorMessage(t: TFunction, error: unknown, fallbackKey?: string): string {
  if (isApiErrorInstance(error) && error.code) {
    if (i18next.exists(`errors.api.${error.code}`)) {
      return t(`errors.api.${error.code}`, safeParams(error.params));
    }
    return t("errors.api.unknownWithCode", { code: error.code });
  }
  return t(fallbackKey ?? "errors.api.unknown");
}

/**
 * Field-level messages keyed by input path (`port`, `config.url`).
 * Translated `errors.api.<code>` when the key exists, otherwise the server message;
 * the first error per path wins.
 */
export function getFieldErrors(error: unknown, t: TFunction): Record<string, string> {
  const result: Record<string, string> = {};
  if (!isApiErrorInstance(error)) return result;
  for (const item of error.fieldErrors) {
    if (item.path in result) continue;
    result[item.path] =
      item.code && i18next.exists(`errors.api.${item.code}`)
        ? t(`errors.api.${item.code}`)
        : item.message;
  }
  return result;
}
