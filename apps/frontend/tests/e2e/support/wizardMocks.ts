/**
 * Shared mock data and helpers for the wizard E2E specs (responsive layout and accessibility).
 * The device list and the wizard endpoints are mocked with cy.intercept, so results do not depend on the
 * database or on real devices.
 */

// 12 devices: exercises the swiper dots, which used to overflow with many devices.
export const DEVICES = Array.from({ length: 12 }, (_, i) => ({
  id: i + 1,
  device_id: `AABBCC0000${String(i).padStart(2, "0")}`,
  name: i === 0 ? "Wohnzimmer" : `Lautsprecher ${i + 1}`,
  model: "SoundTouch 20",
  ip: `192.168.1.${100 + i}`,
  mac_address: `AABBCC0000${String(i).padStart(2, "0")}`,
  firmware_version: "27.0.6",
  setup_status: "configured",
}));
export const DEVICE = DEVICES[0];

export const SCAN_RESULT = {
  usb_mounted: true,
  backup_dir: "/media/sda1/backups",
  all_sets: [],
  error: null,
  selected_set: {
    device_id: DEVICE.device_id,
    backup_date: "20261020",
    is_legacy: false,
    is_match: true,
    files: [
      {
        filename: `soundtouch-${DEVICE.device_id}-20261020-nv.tgz`,
        volume_type: "persistent",
        file_path: "/media/sda1/backups/nv.tgz",
        size_bytes: 10240,
        device_id: DEVICE.device_id,
        backup_date: "20261020",
        is_pre_restore: false,
        validation_status: "ok",
        validation_message: "",
      },
      {
        filename: `soundtouch-${DEVICE.device_id}-20261020-rootfs.tgz`,
        volume_type: "rootfs",
        file_path: "/media/sda1/backups/rootfs.tgz",
        size_bytes: 60000000,
        device_id: DEVICE.device_id,
        backup_date: "20261020",
        is_pre_restore: false,
        validation_status: "warning",
        validation_message: "Expected paths starting with opt/Bose/ not found in archive",
        validation_code: "archive_path_missing",
        validation_params: { expected: "opt/Bose/" },
      },
    ],
  },
};

export const RESTORE_RESULT = {
  success: true,
  restore_type: "backup",
  pre_restore_snapshot: null,
  snapshot_skipped: false,
  device_rebooted: true,
  total_duration_seconds: 12.5,
  steps: [
    { name: "pre_snapshot", status: "completed", message: "Pre-restore snapshot saved", message_code: "snapshot_saved", error: null, duration_seconds: 1.2 },
    { name: "config", status: "completed", message: "Config files restored", message_code: "config_restored", error: null, duration_seconds: 2.1 },
    { name: "presets", status: "completed", message: "Presets restored at /mnt/nv/BoseApp-Persistence/1/Presets.xml", message_code: "presets_restored", message_params: { path: "/mnt/nv/BoseApp-Persistence/1/Presets.xml" }, error: null, duration_seconds: 0.4 },
    { name: "hosts", status: "skipped", message: "No OCT block found in /etc/hosts (already clean)", message_code: "hosts_clean", error: null, duration_seconds: 0 },
    { name: "ntp", status: "failed", message: "NTP restore failed: Permission denied", message_code: "ntp_restore_failed", message_params: { error: "Permission denied" }, error: "Permission denied", duration_seconds: 0.3 },
  ],
};

export function mockApi() {
  cy.intercept("GET", "/api/devices", { statusCode: 200, body: { count: DEVICES.length, devices: DEVICES } });
}

export function visitDe(path: string) {
  cy.visit(path, {
    onBeforeLoad(win) {
      // CI defaults to English; German strings are longer and stress the layout harder.
      win.localStorage.setItem("oct-lang", "de");
    },
  });
}

export const HOSTS_OK = {
  success: true,
  action: "modified",
  message: "Hosts modified",
  backup_path: "/media/sda1/backups/hosts_backup_20261020_101500.bak",
  diff: "+ 192.168.1.100 streaming.bose.com\n+ 192.168.1.100 bmx.bose.com\n+ 192.168.1.100 api.bosesoundtouch.com",
};

export const FINALIZE_OK = {
  success: true,
  uuid: "3784726",
  had_uuid: false,
  uuid_was_collision: false,
  sources_written: true,
  sources_backup_path: "/mnt/nv/Sources.xml.bak",
  system_config_written: true,
  message: "ok",
};

export function check(name: string, passed: boolean, details: Record<string, unknown> = {}) {
  return { name, passed, message: passed ? `${name} ok` : `${name} failed`, details };
}

export const VERIFY_ALL_PASSED = {
  success: true,
  passed_count: 10,
  failed_count: 0,
  message: "ok",
  checks: [
    check("uuid_in_db", true),
    check("sources_complete", true),
    check("config_files_present", true),
    check("config_files_identical", true),
    check("config_bmx_url", true, { bmx_url: "http://192.168.178.11:7778" }),
    check("hosts_oct_block", true),
    check("hosts_domains_complete", true),
    check("hosts_ip_correct", true),
    check("system_config_uuid_match", true),
    check("ntp_server_correct", true, { ntp_server: "pool.ntp.org" }),
  ],
};

export const VERIFY_SOME_FAILED = {
  ...VERIFY_ALL_PASSED,
  success: false,
  passed_count: 8,
  failed_count: 2,
  checks: VERIFY_ALL_PASSED.checks.map((c) =>
    c.name === "hosts_domains_complete"
      ? check(c.name, false, { missing: ["bmx.bose.com", "api.bosesoundtouch.com"] })
      : c.name === "hosts_ip_correct"
        ? check(c.name, false)
        : c,
  ),
};

export function mockSetupWizardApi() {
  mockApi();
  cy.intercept("POST", "/api/setup/wizard/validate-hostname", { statusCode: 200, body: { resolvable: true, matches_expected: true, oct_reachable: true } });
  cy.intercept("POST", "/api/setup/wizard/finalize", { statusCode: 200, body: FINALIZE_OK });
  cy.intercept("POST", "/api/setup/wizard/reboot-device", { statusCode: 200, body: { success: true, message: "rebooting" } });
  cy.intercept("POST", "/api/setup/wizard/verify-redirect", {
    statusCode: 200,
    body: { success: true, resolved_ip: "192.168.1.100", expected_ip: "192.168.1.100", matches_expected: true, message: "ok" },
  });
}
