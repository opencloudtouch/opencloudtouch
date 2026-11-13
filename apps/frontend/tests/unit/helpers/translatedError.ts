import { expect } from "vitest";
import { i18next } from "../../../src/i18n";

/**
 * Error messages shown to the user are ALWAYS translated: never the raw exception or server text.
 * `raw` is the text of the error that was thrown/returned in the test.
 */
export function expectTranslatedError(actual: unknown, raw: string): void {
  expect(typeof actual, "an error message is shown").toBe("string");
  const text = String(actual);
  expect(text.length).toBeGreaterThan(0);
  expect(text, "raw error text must not be shown").not.toContain(raw);
  expect(text, "the message is a translation, not a key").not.toMatch(/^errors\./);
}

/** The visible text of the page/body must not contain the raw error text. */
export function expectNoRawText(container: HTMLElement | Document, raw: string): void {
  const body = "body" in container ? container.body : container;
  expect(body.textContent ?? "", "raw error text must not be shown").not.toContain(raw);
}

export const translatedUnknown = () => i18next.t("errors.unknown");
