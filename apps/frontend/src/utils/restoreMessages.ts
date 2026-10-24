/**
 * Translation of backend restore/backup messages.
 *
 * The backend sends an English `message` plus a stable `message_code` (and parameters such as a path).
 * The UI translates by code and falls back to the English text for unknown codes, so a newer backend
 * never shows an empty line in an older frontend.
 */
import type { TFunction } from "i18next";

interface TranslatableStep {
  message: string;
  message_code?: string | null;
  message_params?: Record<string, string>;
}

interface TranslatableValidation {
  validation_message: string;
  validation_code?: string | null;
  validation_params?: Record<string, string>;
}

/** Label of a restore step (`pre_snapshot`, `config`, ...). Unknown names are shown as they are. */
export function translateStepLabel(t: TFunction, name: string, fallback?: string): string {
  return t(`restore.step_labels.${name}`, { defaultValue: fallback ?? name });
}

export function translateStepMessage(t: TFunction, step: TranslatableStep): string {
  if (!step.message_code) return step.message;
  return t(`restore.messages.${step.message_code}`, {
    ...step.message_params,
    defaultValue: step.message,
  });
}

export function translateValidationMessage(t: TFunction, file: TranslatableValidation): string {
  if (!file.validation_code) return file.validation_message;
  return t(`restore.validation.${file.validation_code}`, {
    ...file.validation_params,
    defaultValue: file.validation_message,
  });
}
