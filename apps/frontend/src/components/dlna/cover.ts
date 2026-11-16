/**
 * True when a cover URL must not be shown: none given, or an `http:` cover on an `https:` page
 * (mixed content, blocked by the browser). Callers show a placeholder instead of a broken image.
 */
export function coverBlocked(url: string | null | undefined): boolean {
  return !url || (globalThis.location.protocol === "https:" && url.startsWith("http:"));
}
