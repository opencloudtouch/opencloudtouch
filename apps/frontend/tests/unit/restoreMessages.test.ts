/**
 * Restore/backup messages come from the backend as English text plus a stable code (and parameters).
 * The UI must translate by code, fall back to the English text for unknown codes, and every code the
 * backend can send must exist in every locale.
 */
import { describe, it, expect, afterEach } from "vitest";
import { i18next } from "../../src/i18n";
import {
  translateStepLabel,
  translateStepMessage,
  translateValidationMessage,
} from "../../src/utils/restoreMessages";
import en from "../../src/i18n/locales/en.json";
import de from "../../src/i18n/locales/de.json";
import fr from "../../src/i18n/locales/fr.json";
import itLocale from "../../src/i18n/locales/it.json";
import es from "../../src/i18n/locales/es.json";
import nl from "../../src/i18n/locales/nl.json";
import ptBR from "../../src/i18n/locales/pt-BR.json";
import ja from "../../src/i18n/locales/ja.json";
import pl from "../../src/i18n/locales/pl.json";
import sv from "../../src/i18n/locales/sv.json";

// Codes the backend emits (setup/restore_service.py). Keep in sync when a new message is added there.
const STEP_NAMES = [
  "pre_snapshot",
  "config",
  "presets",
  "hosts",
  "ntp",
  "remote_services",
  "reboot",
];
const MESSAGE_CODES = [
  "snapshot_saved",
  "snapshot_unavailable",
  "snapshot_failed",
  "config_restored",
  "config_restore_failed",
  "presets_clean",
  "presets_restored",
  "presets_restore_failed",
  "hosts_read_failed",
  "hosts_clean",
  "hosts_restored",
  "hosts_restore_failed",
  "ntp_no_backup",
  "ntp_copy_failed",
  "ntp_restored",
  "ntp_restore_failed",
  "remote_services_deleted",
  "remote_services_failed",
  "reboot_sent",
  "reboot_failed",
];
const VALIDATION_CODES = [
  "archive_corrupt",
  "archive_empty",
  "archive_unverified",
  "archive_path_missing",
];

const LOCALES = { en, de, fr, it: itLocale, es, nl, "pt-BR": ptBR, ja, pl, sv } as const;

describe("restore message translation", () => {
  afterEach(async () => {
    await i18next.changeLanguage("en");
  });

  const t = i18next.t.bind(i18next);

  it("translates a step message by code and fills the parameters", async () => {
    await i18next.changeLanguage("de");
    const text = translateStepMessage(t, {
      message: "Presets restored at /mnt/nv/Presets.xml",
      message_code: "presets_restored",
      message_params: { path: "/mnt/nv/Presets.xml" },
    });
    expect(text).toBe("Presets wiederhergestellt unter /mnt/nv/Presets.xml");
  });

  it("keeps technical error text from the device as a parameter, not translated", async () => {
    await i18next.changeLanguage("de");
    const text = translateStepMessage(t, {
      message: "Reboot failed: Connection lost",
      message_code: "reboot_failed",
      message_params: { error: "Connection lost" },
    });
    expect(text).toBe("Neustart fehlgeschlagen: Connection lost");
  });

  it("falls back to the English backend text for an unknown code", async () => {
    await i18next.changeLanguage("de");
    expect(
      translateStepMessage(t, { message: "Something new", message_code: "brand_new_code" })
    ).toBe("Something new");
  });

  it("returns the backend text when no code is sent (older backend)", async () => {
    await i18next.changeLanguage("de");
    expect(translateStepMessage(t, { message: "Plain text" })).toBe("Plain text");
  });

  it("translates step labels and falls back to the given fallback / the raw name", async () => {
    await i18next.changeLanguage("de");
    expect(translateStepLabel(t, "remote_services")).toBe("SSH-Dauerhaftigkeit");
    expect(translateStepLabel(t, "unknown_step", "Fallback")).toBe("Fallback");
    expect(translateStepLabel(t, "unknown_step")).toBe("unknown_step");
  });

  it("translates validation messages by code with parameters", async () => {
    await i18next.changeLanguage("de");
    const text = translateValidationMessage(t, {
      validation_message: "Expected paths starting with mnt/update/ not found in archive",
      validation_code: "archive_path_missing",
      validation_params: { expected: "mnt/update/" },
    });
    expect(text).toBe("Erwartete Pfade mit mnt/update/ wurden im Archiv nicht gefunden");
  });

  it.each(Object.entries(LOCALES))("%s has a translation for every backend code", (_name, locale) => {
    const restore = locale.restore as unknown as {
      step_labels: Record<string, string>;
      messages: Record<string, string>;
      validation: Record<string, string>;
    };
    for (const name of STEP_NAMES) expect(restore.step_labels[name], name).toBeTruthy();
    for (const code of MESSAGE_CODES) expect(restore.messages[code], code).toBeTruthy();
    for (const code of VALIDATION_CODES) expect(restore.validation[code], code).toBeTruthy();
  });

  it.each(Object.entries(LOCALES))(
    "%s keeps the {{placeholders}} of the English message",
    (_name, locale) => {
      const reference = en.restore.messages as Record<string, string>;
      const messages = locale.restore.messages as Record<string, string>;
      for (const code of MESSAGE_CODES) {
        const wanted = (reference[code]?.match(/\{\{\w+\}\}/g) ?? []).sort();
        const actual = (messages[code]?.match(/\{\{\w+\}\}/g) ?? []).sort();
        expect(actual, code).toEqual(wanted);
      }
    }
  );
});
