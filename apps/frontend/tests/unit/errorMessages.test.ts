/**
 * Tests for toUserMessage / extractRawMessage utility
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toUserMessage } from "../../src/utils/errorMessages";

// Mock i18next to return the key as the translated string
vi.mock("../../src/i18n", () => ({
  i18next: {
    t: (key: string) => key,
  },
}));

describe("toUserMessage — extractRawMessage input types", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("handles a plain string error", () => {
    expect(toUserMessage("failed to fetch")).toBe("errors.networkFailed");
  });

  it("handles an Error instance", () => {
    expect(toUserMessage(new Error("network error"))).toBe("errors.networkFailed");
  });

  it("handles an object with a message property", () => {
    expect(toUserMessage({ message: "HTTP 404 not found" })).toBe("errors.notFound");
  });

  it("handles null (stringified)", () => {
    const result = toUserMessage(null);
    expect(result).toBe("errors.unknown");
  });

  it("handles a number (stringified)", () => {
    const result = toUserMessage(42);
    expect(result).toBe("errors.unknown");
  });

  it("falls back to errors.unknown for unrecognised message", () => {
    expect(toUserMessage("some completely unknown error xyz")).toBe("errors.unknown");
  });
});

describe("toUserMessage — network / connectivity patterns", () => {
  it("maps 'Failed to fetch' to errors.networkFailed", () => {
    expect(toUserMessage("Failed to fetch")).toBe("errors.networkFailed");
  });

  it("maps 'network error' to errors.networkFailed", () => {
    expect(toUserMessage("network error")).toBe("errors.networkFailed");
  });

  it("maps 'net::ERR_CONNECTION_REFUSED' to errors.networkFailed", () => {
    expect(toUserMessage("net::ERR_CONNECTION_REFUSED")).toBe("errors.networkFailed");
  });

  it("maps 'Request timed out' to errors.timeout", () => {
    expect(toUserMessage("Request timed out")).toBe("errors.timeout");
  });

  it("maps 'ETIMEDOUT' to errors.timeout", () => {
    expect(toUserMessage("ETIMEDOUT")).toBe("errors.timeout");
  });

  it("maps 'ECONNREFUSED' to errors.connectionRefused", () => {
    expect(toUserMessage("ECONNREFUSED")).toBe("errors.connectionRefused");
  });
});

describe("toUserMessage — HTTP status patterns", () => {
  it("maps 'HTTP 400' to errors.badRequest", () => {
    expect(toUserMessage("HTTP 400 Bad Request")).toBe("errors.badRequest");
  });

  it("maps 'HTTP 422' to errors.badRequest", () => {
    expect(toUserMessage("HTTP 422 Unprocessable Entity")).toBe("errors.badRequest");
  });

  it("maps 'HTTP 401' to errors.unauthorized", () => {
    expect(toUserMessage("HTTP 401 Unauthorized")).toBe("errors.unauthorized");
  });

  it("maps 'HTTP 403' to errors.forbidden", () => {
    expect(toUserMessage("HTTP 403 Forbidden")).toBe("errors.forbidden");
  });

  it("maps 'HTTP 404' to errors.notFound", () => {
    expect(toUserMessage("HTTP 404 Not Found")).toBe("errors.notFound");
  });

  it("maps 'HTTP 409' to errors.conflict", () => {
    expect(toUserMessage("HTTP 409 Conflict")).toBe("errors.conflict");
  });

  it("maps 'HTTP 500' to errors.serverError", () => {
    expect(toUserMessage("HTTP 500 Internal Server Error")).toBe("errors.serverError");
  });

  it("maps 'HTTP 503' to errors.serverError", () => {
    expect(toUserMessage("HTTP 503 Service Unavailable")).toBe("errors.serverError");
  });
});

describe("toUserMessage — preset patterns", () => {
  it("maps 'failed to load presets' to errors.presetsLoadFailed", () => {
    expect(toUserMessage("failed to load presets")).toBe("errors.presetsLoadFailed");
  });

  it("maps 'failed to sync presets' to errors.presetsSyncFailed", () => {
    expect(toUserMessage("failed to sync presets")).toBe("errors.presetsSyncFailed");
  });

  it("maps 'failed to save preset' to errors.presetSaveFailed", () => {
    expect(toUserMessage("failed to save preset")).toBe("errors.presetSaveFailed");
  });

  it("maps 'failed to clear preset' to errors.presetClearFailed", () => {
    expect(toUserMessage("failed to clear preset")).toBe("errors.presetClearFailed");
  });

  it("maps 'failed to play preset' to errors.presetPlayFailed", () => {
    expect(toUserMessage("failed to play preset")).toBe("errors.presetPlayFailed");
  });
});

describe("toUserMessage — settings / device patterns", () => {
  it("maps 'already exists' to errors.alreadyExists", () => {
    expect(toUserMessage("already exists")).toBe("errors.alreadyExists");
  });

  it("maps 'duplicate' to errors.alreadyExists", () => {
    expect(toUserMessage("duplicate entry")).toBe("errors.alreadyExists");
  });

  it("maps 'invalid ip' to errors.invalidIp", () => {
    expect(toUserMessage("invalid ip address")).toBe("errors.invalidIp");
  });

  it("maps 'no devices' to errors.noDevices", () => {
    expect(toUserMessage("no devices found")).toBe("errors.noDevices");
  });
});

describe("toUserMessage — SSH / wizard patterns", () => {
  it("maps 'ssh failed' to errors.sshFailed", () => {
    expect(toUserMessage("ssh failed to connect")).toBe("errors.sshFailed");
  });

  it("maps 'ssh error' to errors.sshFailed", () => {
    expect(toUserMessage("ssh error: authentication")).toBe("errors.sshFailed");
  });

  it("maps 'port check failed' to errors.portCheckFailed", () => {
    expect(toUserMessage("port check failed")).toBe("errors.portCheckFailed");
  });

  it("maps 'backup failed' to errors.backupFailed", () => {
    expect(toUserMessage("backup failed")).toBe("errors.backupFailed");
  });

  it("maps 'config modification failed' to errors.configFailed", () => {
    expect(toUserMessage("config modification failed")).toBe("errors.configFailed");
  });

  it("maps 'hosts modification failed' to errors.hostsFailed", () => {
    expect(toUserMessage("hosts modification failed")).toBe("errors.hostsFailed");
  });
});
