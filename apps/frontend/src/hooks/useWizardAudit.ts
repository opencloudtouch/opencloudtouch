/**
 * Hook for wizard audit logging.
 *
 * Sends every user action, step transition, and device state change
 * to the backend audit trail. Fire-and-forget — errors are logged
 * but never block the wizard flow.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface AuditEntry {
  device_id: string;
  category: string;
  event: string;
  step?: number;
  detail?: string;
  timestamp?: string;
}

/**
 * Send a single audit entry to the backend.
 * Fire-and-forget — does not throw on failure.
 */
async function sendAuditEntry(entry: AuditEntry): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/wizard/audit-log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...entry,
        timestamp: entry.timestamp ?? new Date().toISOString(),
      }),
    });
  } catch {
    console.warn("[WizardAudit] Failed to send audit entry:", entry.event);
  }
}

/**
 * Send a batch of audit entries.
 * Fire-and-forget — does not throw on failure.
 */
async function sendAuditBatch(entries: AuditEntry[]): Promise<void> {
  if (entries.length === 0) return;
  try {
    await fetch(`${API_BASE}/api/wizard/audit-log/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entries: entries.map((e) => ({
          ...e,
          timestamp: e.timestamp ?? new Date().toISOString(),
        })),
      }),
    });
  } catch {
    console.warn("[WizardAudit] Failed to send batch:", entries.length);
  }
}

/**
 * Create a wizard audit logger bound to a specific device.
 *
 * Usage:
 *   const audit = createWizardAudit(device.device_id);
 *   audit.log("user_action", "button_click:next", 3);
 *   audit.logDetail("dropdown", "platform_change", 1, { value: "windows" });
 */
export function createWizardAudit(deviceId: string) {
  const log = (category: string, event: string, step?: number, detail?: string) => {
    sendAuditEntry({ device_id: deviceId, category, event, step, detail });
  };

  const logDetail = (
    category: string,
    event: string,
    step?: number,
    data?: Record<string, unknown>
  ) => {
    log(category, event, step, data ? JSON.stringify(data) : undefined);
  };

  const logBatch = (entries: Omit<AuditEntry, "device_id">[]) => {
    sendAuditBatch(entries.map((e) => ({ ...e, device_id: deviceId })));
  };

  return { log, logDetail, logBatch };
}

export type WizardAuditLogger = ReturnType<typeof createWizardAudit>;
