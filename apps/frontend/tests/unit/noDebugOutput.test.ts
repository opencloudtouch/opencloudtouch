/**
 * Regression test (final browser audit F15): no plain console.log in the production code.
 * Debug output goes through `octDebug`, which is switched by the backend log level.
 */
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve, relative } from "node:path";

function files(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) files(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

describe("no plain console.log in src", () => {
  const srcDir = resolve(__dirname, "../../src");
  it("uses octDebug instead", () => {
    const offenders = files(srcDir)
      .filter((f) => !relative(srcDir, f).replace(/\\/g, "/").startsWith("utils/debug.ts"))
      .filter((f) => /console\.log\(/.test(readFileSync(f, "utf-8")))
      .map((f) => relative(srcDir, f).replace(/\\/g, "/"));
    expect(offenders).toEqual([]);
  });
});
