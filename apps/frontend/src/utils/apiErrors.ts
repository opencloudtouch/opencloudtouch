/**
 * Translated messages for ApiError — maps the stable server `code` to
 * `errors.api.<code>` (all locales). Never shows raw backend text for coded errors.
 */

import type { TFunction } from "i18next";
import { i18next } from "../i18n";
import { isApiErrorInstance } from "../api/types";

/**
 * Message for an API failure: translated by `code` when known, a generic message
 * naming the code when unknown, otherwise `fallbackKey` (default `errors.api.unknown`).
 */
export function getApiErrorMessage(t: TFunction, error: unknown, fallbackKey?: string): string {
  if (isApiErrorInstance(error) && error.code) {
    if (i18next.exists(`errors.api.${error.code}`)) {
      // params go through `replace`, so no key of the server data can act as an i18next option
      return t(`errors.api.${error.code}`, { replace: error.params });
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
  if (!isApiErrorInstance(error)) return {};
  // A Map keeps "first wins" correct for paths such as "constructor" or "__proto__".
  const messages = new Map<string, string>();
  for (const item of error.fieldErrors) {
    if (messages.has(item.path)) continue;
    messages.set(
      item.path,
      item.code && i18next.exists(`errors.api.${item.code}`)
        ? t(`errors.api.${item.code}`)
        : item.message
    );
  }
  return Object.fromEntries(messages);
}
