/**
 * Regression tests (final browser audit F20): error messages shown to users are ALWAYS translated.
 */
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve, relative } from "node:path";
import { i18next } from "../../src/i18n";
import { ApiError } from "../../src/api/types";
import { userErrorMessage } from "../../src/utils/errorMessages";

describe("userErrorMessage", () => {
  it("translates a coded API error by its code", () => {
    const error = new ApiError("Device AA not found", { status: 404, code: "device_not_found" });
    const text = userErrorMessage(error);
    expect(text).toBe(i18next.t("errors.api.device_not_found"));
    expect(text).not.toContain("Device AA not found");
  });

  it("names the code for an API error whose code is unknown, without the raw text", () => {
    const error = new ApiError("raw server text", { status: 500, code: "brand_new_code" });
    const text = userErrorMessage(error);
    expect(text).toBe(i18next.t("errors.api.unknownWithCode", { code: "brand_new_code" }));
    expect(text).not.toContain("raw server text");
  });

  it.each([
    ["an Error with technical text", new Error("touch: /mnt/nv/remote_services: Read-only file system")],
    ["a string", "boom-string"],
    ["a plain object", { message: "internal detail 0xDEADBEEF" }],
    ["undefined", undefined],
    ["null", null],
  ])("never returns the raw text of %s", (_label, input) => {
    const text = userErrorMessage(input);
    expect(text.length).toBeGreaterThan(0);
    expect(text).not.toMatch(/Read-only|boom-string|0xDEADBEEF/);
    expect(text).not.toMatch(/^errors\./);
  });

  it("returns the generic translated message for an unrecognised error", () => {
    expect(userErrorMessage(new Error("something odd"))).toBe(i18next.t("errors.unknown"));
  });

  it("gives the same answer in every UI language that has the message", async () => {
    const original = i18next.language;
    for (const lng of ["en", "de", "ja", "sv", "pl"]) {
      await i18next.changeLanguage(lng);
      expect(userErrorMessage(new Error("odd"))).toBe(i18next.t("errors.unknown"));
    }
    await i18next.changeLanguage(original);
  });
});

/** Walk src and return the TSX/TS files that are not tests. */
function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === "generated" || name === "i18n") continue;
      sourceFiles(full, out);
    } else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name)) {
      out.push(full);
    }
  }
  return out;
}

describe("no raw error text reaches the UI", () => {
  const srcDir = resolve(__dirname, "../../src");
  const files = sourceFiles(srcDir);

  it("no component or hook turns an exception into display text with `.message`", () => {
    const offenders: string[] = [];
    const pattern = /(?:err|error|e)\s+instanceof\s+Error\s*\?\s*(?:err|error|e)\.message/;
    for (const file of files) {
      const rel = relative(srcDir, file).replace(/\\/g, "/");
      if (rel.startsWith("utils/errorMessages.ts") || rel.startsWith("api/")) continue;
      if (pattern.test(readFileSync(file, "utf-8"))) offenders.push(rel);
    }
    expect(offenders, "use userErrorMessage(error) instead").toEqual([]);
  });

  it("no hard-coded error sentence is set as an error message", () => {
    const offenders: string[] = [];
    const pattern = /set(?:Error|ErrorMessage)\(\s*"[A-Za-zÄÖÜäöü][^"]{12,}"/;
    for (const file of files) {
      const rel = relative(srcDir, file).replace(/\\/g, "/");
      if (pattern.test(readFileSync(file, "utf-8"))) offenders.push(rel);
    }
    expect(offenders, "use t(...) / userErrorMessage(...)").toEqual([]);
  });

  it("no `{error}` of a caught exception is rendered raw in a component", () => {
    const offenders: string[] = [];
    const pattern = /\(error as Error\)\.message|\(err as Error\)\.message/;
    for (const file of files) {
      const rel = relative(srcDir, file).replace(/\\/g, "/");
      if (pattern.test(readFileSync(file, "utf-8"))) offenders.push(rel);
    }
    expect(offenders).toEqual([]);
  });
});

describe("restore messages never include the raw device error", () => {
  it("no restore.messages text of any language has an {{error}} placeholder", async () => {
    const { readFileSync, readdirSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const dir = resolve(__dirname, "../../src/i18n/locales");
    for (const file of readdirSync(dir).filter((f) => f.endsWith(".json"))) {
      const messages = JSON.parse(readFileSync(resolve(dir, file), "utf-8")).restore.messages as Record<string, string>;
      const withError = Object.entries(messages).filter(([, v]) => v.includes("{{error}}"));
      expect(withError, file).toEqual([]);
    }
  });
});
