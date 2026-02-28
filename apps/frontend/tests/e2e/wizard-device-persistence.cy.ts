/**
 * E2E Test: Wizard Device Persistence
 *
 * Tests the device selection persistence when navigating between:
 * - Preset page (device selection via swiper/arrows)
 * - Setup Wizard (via Setup button)
 * - Back to Preset page (via back button)
 *
 * Requirements:
 * 1. Correct device shown in wizard header
 * 2. Correct device IP used for SSH checks
 * 3. Device selection persists when returning to preset page
 */

describe('Wizard Device Persistence', () => {
  const apiUrl = Cypress.env('apiUrl') || 'http://localhost:7778/api';

  beforeEach(() => {
    // Mock device discovery with multiple devices
    cy.intercept('GET', '/api/devices', {
      statusCode: 200,
      body: {
        devices: [
          {
            device_id: 'DEVICE_TV',
            name: 'TV',
            model: 'SoundTouch 300',
            ip: '192.168.178.83',
            mac: '00:11:22:33:44:55',
            type: 'soundtouch',
          },
          {
            device_id: 'DEVICE_KITCHEN',
            name: 'Küche',
            model: 'SoundTouch 10',
            ip: '192.168.178.84',
            mac: '00:11:22:33:44:66',
            type: 'soundtouch',
          },
          {
            device_id: 'DEVICE_BEDROOM',
            name: 'Schlafzimmer',
            model: 'SoundTouch 20',
            ip: '192.168.178.85',
            mac: '00:11:22:33:44:77',
            type: 'soundtouch',
          },
        ],
      },
    }).as('getDevices');

    // Mock device presets (empty)
    cy.intercept('GET', '/api/presets/device/*', {
      statusCode: 200,
      body: [],
    }).as('getPresets');

    // Visit preset page
    cy.visit('/');
    cy.wait('@getDevices');
  });

  // BUG-14: Wizard-Header zeigt falsches Gerät (URL-Param ?device= vs ?deviceId=)
  it('BUG-14: should show correct device in wizard header when navigating from preset page', () => {
    // Initial state: First device (TV) shown
    cy.get('[data-test="device-swiper"]').should('contain', 'TV');

    // Navigate to second device (Küche) using swiper
    cy.get('[data-test="device-swiper"]').within(() => {
      cy.get('button[aria-label="Nächstes Gerät"]').click();
    });

    // Verify Küche is now selected
    cy.get('[data-test="device-swiper"]').should('contain', 'Küche');
    cy.get('[data-test="device-swiper"]').should('contain', 'SoundTouch 10');

    // Click setup button
    cy.get('[data-test="setup-button"]').click();

    // Wizard starts in mode-selection screen; click Manuell to enter manual mode
    // (DeviceInfoHeader is only rendered when mode !== "select")
    cy.url().should('include', '/setup-wizard?deviceId=DEVICE_KITCHEN');
    cy.contains('button', 'Manuell').click();

    // Header must now show the correct device
    cy.get('.device-info-header').should('contain', 'Küche');
    cy.get('.device-info-header').should('contain', 'SoundTouch 10');
    cy.get('.device-info-header').should('contain', '192.168.178.84');
  });

  it('should use correct device IP for SSH port checks', () => {
    // Navigate to Küche
    cy.get('[data-test="device-swiper"]').within(() => {
      cy.get('button[aria-label="Nächstes Gerät"]').click();
    });

    // BUG-19/BUG-25: intercept check-ports and assert device_ip is sent
    cy.intercept('POST', '**/setup/wizard/check-ports', (req) => {
      expect(req.body.device_ip).to.equal('192.168.178.84',
        'BUG-19: check-ports must send device_ip, not device_id');
      expect(req.body).not.to.have.property('device_id',
        'BUG-19: device_id must NOT be sent to check-ports');
      req.reply({
        statusCode: 200,
        body: { success: true, has_ssh: true, has_telnet: false, message: 'SSH ok' },
      });
    }).as('checkPorts');

    // Start wizard
    cy.get('[data-test="setup-button"]').click();

    // Manual mode: Step 1 (USB Preparation) requires USB-ready checkbox before Weiter
    cy.contains('button', 'Manuell').click();

    // Check the "USB-Stick ist bereit" checkbox (last checkbox in Step 1)
    // to enable the Weiter button
    cy.get('input[type="checkbox"]').last().check();

    // Navigate to Step 2 (Power Cycle = Step3PowerCycle, which has port check)
    cy.contains('button', /weiter/i, { timeout: 5000 }).click();

    // Trigger port check in Step 2 (Step3PowerCycle)
    cy.contains('button', /jetzt prüfen/i, { timeout: 5000 }).click();

    // Verify API was called with correct device IP
    cy.wait('@checkPorts');
  });

  it('should persist device selection when returning from wizard', () => {
    // Navigate to third device (Schlafzimmer)
    cy.get('[data-test="device-swiper"]').within(() => {
      cy.get('button[aria-label="Nächstes Gerät"]').click(); // TV -> Küche
      cy.get('button[aria-label="Nächstes Gerät"]').click(); // Küche -> Schlafzimmer
    });

    cy.get('[data-test="device-swiper"]').should('contain', 'Schlafzimmer');

    // Start wizard
    cy.get('[data-test="setup-button"]').click();
    cy.url().should('include', '/setup-wizard?deviceId=DEVICE_BEDROOM');

    // Select Manual Mode
    cy.contains('button', 'Manuell').click();

    // Click back button on first step
    cy.contains('button', 'Zurück').click();

    // Should be back on preset page
    cy.url().should('match', /\/(presets)?\?device=DEVICE_BEDROOM$/);

    // Device should still be Schlafzimmer
    cy.get('[data-test="device-swiper"]').should('contain', 'Schlafzimmer');
    cy.get('[data-test="device-swiper"]').should('contain', 'SoundTouch 20');
  });

  // BUG-29: Pfeiltasten-Navigation bricht wenn ?device= URL-Param gesetzt ist
  it('BUG-29: should handle device selection via arrow buttons and persist to wizard', () => {
    // Use DeviceSwiper navigation button (← →) to switch device.
    // BUG-29: Before the fix, the useEffect-dependency on ?device= URL-param
    // overrode the user's manual selection back to the URL device on every re-render.
    cy.get('[data-test="device-swiper"]').within(() => {
      cy.get('button[aria-label="Nächstes Gerät"]').click(); // TV -> Küche
    });

    cy.get('[data-test="device-swiper"]').should('contain', 'Küche');

    // Start wizard – DeviceInfoHeader only visible after mode selection
    cy.get('[data-test="setup-button"]').click();
    cy.contains('button', 'Manuell').click();

    // Wizard header must show the device selected via arrow button, not the URL default
    cy.get('.device-info-header').should('contain', 'Küche');
    cy.get('.device-info-header').should('contain', '192.168.178.84');

    // Go back
    cy.contains('button', 'Zurück').click();

    // Device swiper must still show Küche (not reset to TV)
    cy.get('[data-test="device-swiper"]').should('contain', 'Küche');
  });

  it('should show correct device when accessing wizard via direct URL', () => {
    // Directly visit wizard with specific device
    cy.visit('/setup-wizard?deviceId=DEVICE_KITCHEN');

    // Wait for devices to load
    cy.wait('@getDevices');

    // Wizard starts in mode-selection; click Manuell to enter manual mode
    cy.contains('button', 'Manuell').click();

    // Header must show the correct device after mode selection
    cy.get('.device-info-header').should('contain', 'Küche');
    cy.get('.device-info-header').should('contain', '192.168.178.84');

    // Go back to presets
    cy.contains('button', 'Zurück').click();

    // Should preserve device selection
    cy.url().should('include', 'device=DEVICE_KITCHEN');
    cy.get('[data-test="device-swiper"]').should('contain', 'Küche');
  });

  it('should handle invalid deviceId gracefully', () => {
    // Visit wizard with non-existent device
    cy.visit('/setup-wizard?deviceId=INVALID_DEVICE');
    cy.wait('@getDevices');

    // Wizard starts in mode-selection screen; enter manual mode
    cy.contains('button', 'Manuell').click();

    // Should fall back to first device (TV)
    cy.get('.device-info-header').should('contain', 'TV');
  });
});
