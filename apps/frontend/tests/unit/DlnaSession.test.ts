import { describe, it, expect, vi, beforeEach } from "vitest";
import { getLastFolder, setLastFolder } from "../../src/components/dlna/session";

describe("dlna session memory", () => {
  beforeEach(() => sessionStorage.clear());

  it("remembers last folder per server", () => {
    setLastFolder("a", "f1");
    setLastFolder("b", "f2");
    expect(getLastFolder("a")).toBe("f1");
    expect(getLastFolder("b")).toBe("f2");
    expect(getLastFolder("c")).toBeNull();
  });

  it("forgets the folder when the root is stored", () => {
    setLastFolder("a", "f1");
    setLastFolder("a", "0");
    expect(getLastFolder("a")).toBeNull();
  });

  it("survives sessionStorage errors", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(() => setLastFolder("a", "f1")).not.toThrow();
    expect(getLastFolder("a")).toBeNull();
    vi.restoreAllMocks();
  });
});
