/**
 * E2E Test: Restore Wizard — Happy Path Tests
 *
 * Tests cover:
 * - T059: Clean restore happy path (choice → execution → verification → completion)
 * - T060: Backup restore happy path (choice → scan → execution → verification → completion)
 */

const FRONTEND_BASE = "http://localhost:4173";

const MOCK_DEVICE = {
  device_id: "DEVICE_RESTORE_01",
  name: "Living Room",
  model: "SoundTouch 30",
  ip: "192.168.1.100",
  mac: "A4:15:88:11:22:33",
  type: "soundtouch",
};

function setupBaseMocks() {
  cy.intercept("GET", "/api/devices", {
    statusCode: 200,
    body: { devices: [MOCK_DEVICE] },
  }).as("getDevices");

  cy.intercept("GET", "/api/setup/wizard/server-info", {
    statusCode: 200,
    body: { server_url: "http://192.168.1.50:7778", server_ip: "192.168.1.50" },
  }).as("serverInfo");
}

describe("Restore Wizard — Clean Restore Happy Path (T059)", () => {
  beforeEach(() => {
    setupBaseMocks();

    cy.intercept("POST", "/api/setup/wizard/restore-wizard", {
      statusCode: 200,
      body: {
        success: true,
        restore_type: "clean",
        steps: [
          { name: "pre_snapshot", status: "completed", message: "Pre-restore snapshot saved", error: null, duration_seconds: 3.2 },
          { name: "config", status: "completed", message: "Config files restored", error: null, duration_seconds: 2.0 },
          { name: "presets", status: "completed", message: "Presets cleared", error: null, duration_seconds: 1.0 },
          { name: "hosts", status: "completed", message: "OCT block removed from /etc/hosts", error: null, duration_seconds: 0.8 },
          { name: "remote_services", status: "completed", message: "/mnt/nv/remote_services deleted", error: null, duration_seconds: 0.3 },
        ],
        total_duration_seconds: 7.3,
        snapshot_skipped: false,
        device_rebooted: false,
      },
    }).as("executeRestore");

    cy.intercept("GET", "/api/devices", (req) => {
      // After restore, device comes back online
      req.reply({
        statusCode: 200,
        body: { devices: [MOCK_DEVICE] },
      });
    });
  });

  it("completes clean restore from choice screen to completion", () => {
    cy.visit(`${FRONTEND_BASE}/setup-wizard?deviceId=${MOCK_DEVICE.device_id}`);
    cy.wait("@getDevices");

    // Step 1: Choose Restore Wizard
    cy.contains("Restore Wizard").click();

    // Step 2: Choose Clean Restore
    cy.contains("Clean Restore").click();

    // Step 3: Execution starts automatically
    cy.wait("@executeRestore");
    cy.contains("All steps completed successfully").should("be.visible");

    // Step 4: Continue to verification
    cy.contains("Continue").click();

    // Step 5: Device comes back → manually confirm
    cy.contains("Device is back").click();

    // Step 6: Completion
    cy.contains("Restore Complete").should("be.visible");
    cy.contains("Config files restored").should("be.visible");
    cy.contains("Done").should("be.visible");
  });
});

describe("Restore Wizard — Backup Restore Happy Path (T060)", () => {
  beforeEach(() => {
    setupBaseMocks();

    cy.intercept("POST", "/api/setup/wizard/scan-backups", {
      statusCode: 200,
      body: {
        usb_mounted: true,
        backup_dir: "/media/sda1/oct-backup",
        selected_set: {
          device_id: "DEVICE_RESTORE_01",
          backup_date: "20260101",
          is_legacy: false,
          is_match: true,
          files: [
            {
              filename: "soundtouch-DEVICE_RESTORE_01-20260101-rootfs.tgz",
              volume_type: "rootfs",
              file_path: "/media/sda1/oct-backup/soundtouch-DEVICE_RESTORE_01-20260101-rootfs.tgz",
              validation_status: "valid",
              validation_message: "",
            },
            {
              filename: "soundtouch-DEVICE_RESTORE_01-20260101-nv.tgz",
              volume_type: "persistent",
              file_path: "/media/sda1/oct-backup/soundtouch-DEVICE_RESTORE_01-20260101-nv.tgz",
              validation_status: "valid",
              validation_message: "",
            },
          ],
        },
        all_sets: [],
        error: null,
      },
    }).as("scanBackups");

    cy.intercept("POST", "/api/setup/wizard/restore-wizard", {
      statusCode: 200,
      body: {
        success: true,
        restore_type: "backup",
        steps: [
          { name: "pre_snapshot", status: "completed", message: "Pre-restore snapshot saved", error: null, duration_seconds: 3.0 },
          { name: "config", status: "completed", message: "Config restored from backup", error: null, duration_seconds: 4.5 },
          { name: "presets", status: "completed", message: "Presets restored from backup", error: null, duration_seconds: 1.2 },
          { name: "hosts", status: "completed", message: "OCT block removed from /etc/hosts", error: null, duration_seconds: 0.9 },
          { name: "remote_services", status: "completed", message: "/mnt/nv/remote_services deleted", error: null, duration_seconds: 0.3 },
        ],
        total_duration_seconds: 9.9,
        snapshot_skipped: false,
        device_rebooted: false,
      },
    }).as("executeRestore");
  });

  it("completes backup restore from scan to completion", () => {
    cy.visit(`${FRONTEND_BASE}/setup-wizard?deviceId=${MOCK_DEVICE.device_id}`);
    cy.wait("@getDevices");

    // Step 1: Choose Restore Wizard
    cy.contains("Restore Wizard").click();

    // Step 2: Choose Backup Restore
    cy.contains("Restore from Backup").click();

    // Step 3: Backup scan runs automatically
    cy.wait("@scanBackups");
    cy.contains("Backup found").should("be.visible");
    cy.contains("rootfs").should("be.visible");

    // Select backup
    cy.contains("Use This Backup").click();

    // Step 4: Execution runs
    cy.wait("@executeRestore");
    cy.contains("All steps completed successfully").should("be.visible");

    // Continue to verification
    cy.contains("Continue").click();

    // Device back → manual confirm
    cy.contains("Device is back").click();

    // Completion screen
    cy.contains("Restore Complete").should("be.visible");
    cy.contains("Config restored from backup").should("be.visible");
  });
});
