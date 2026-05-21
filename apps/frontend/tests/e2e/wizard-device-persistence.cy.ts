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

/** Force German locale — CI defaults to English (navigator.language='en') */
function visitDe(url: string, options?: Partial<Cypress.VisitOptions>) {
  cy.visit(url, {
    ...options,
    onBeforeLoad(win) {
      win.localStorage.setItem('oct-lang', 'de');
      options?.onBeforeLoad?.(win);
    },
  });
}

describe('Wizard Device Persistence', () => {
  const apiUrl = Cypress.expose('apiUrl') || 'http://localhost:7778/api';

  beforeEach(() => {
    // Mock device discovery with multiple devices — matches actual API contract {count, devices: [...]}
    cy.intercept('GET', '/api/devices', {
      statusCode: 200,
      body: {
        count: 3,
        devices: [
          {
            device_id: 'DEVICE_TV',
            name: 'TV',
            model: 'SoundTouch 300',
            ip: '192.168.1.83',
            mac_address: '00:11:22:33:44:55',
            firmware_version: '29.0.3',
            last_seen: new Date().toISOString(),
          },
          {
            device_id: 'DEVICE_KITCHEN',
            name: 'Küche',
            model: 'SoundTouch 10',
            ip: '192.168.1.84',
            mac_address: '00:11:22:33:44:66',
            firmware_version: '28.1.0',
            last_seen: new Date().toISOString(),
          },
          {
            device_id: 'DEVICE_BEDROOM',
            name: 'Schlafzimmer',
            model: 'SoundTouch 20',
            ip: '192.168.1.85',
            mac_address: '00:11:22:33:44:77',
            firmware_version: '28.0.0',
            last_seen: new Date().toISOString(),
          },
        ],
      },
    }).as('getDevices');

    // Mock device presets (empty) — URL pattern matches /api/presets/{device_id}
    cy.intercept('GET', '/api/presets/*', {
      statusCode: 200,
      body: [],
    }).as('getPresets');

    // Mock additional endpoints the app calls on load
    cy.intercept('GET', '/api/settings/manual-ips', { statusCode: 200, body: [] });
    cy.intercept('GET', '/api/devices/discover/stream*', {
      statusCode: 200,
      body: 'data: done\n\n',
      headers: { 'Content-Type': 'text/event-stream' },
    });

    // Intercept preset sync (not intercepted → hits real backend → causes timing issues)
    cy.intercept('POST', '/api/presets/**', { statusCode: 200, body: { message: 'Synced', synced: 0 } });
    cy.intercept('POST', '/api/devices/sync', { statusCode: 200, body: { discovered: 0, synced: 0, failed: 0 } });

    // Visit preset page
    visitDe('/');
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

    // Navigate through WizardChoice to Setup path
    cy.url().should('include', '/setup-wizard?deviceId=DEVICE_KITCHEN');
    cy.reload();
    cy.wait('@getDevices');
    cy.contains('Setup-Assistent').click();

    // Header must now show the correct device
    cy.get('.device-info-header', { timeout: 10000 }).should('contain', 'Küche');
    cy.get('.device-info-header').should('contain', 'SoundTouch 10');
    cy.get('.device-info-header').should('contain', '192.168.1.84');
  });

  it('should use correct device IP for SSH port checks', () => {
    // Navigate to Küche and wait for it to appear (ensures React has settled before setup click)
    cy.get('[data-test="device-swiper"]').within(() => {
      cy.get('button[aria-label="Nächstes Gerät"]').click();
    });
    cy.get('[data-test="device-swiper"]').should('contain', 'Küche');

    // BUG-19/BUG-25: intercept check-ports and assert device_ip is sent
    cy.intercept('POST', '**/setup/wizard/check-ports', (req) => {
      expect(req.body.device_ip).to.equal('192.168.1.84',
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

    // Navigate through WizardChoice to Setup path
    cy.url().should('include', '/setup-wizard?deviceId=DEVICE_KITCHEN');
    cy.reload();
    cy.wait('@getDevices');
    cy.get('.setup-wizard-page-v2', { timeout: 8000 }).should('exist');
    cy.contains('Setup-Assistent').click();

    // Check the "USB-Stick ist bereit" checkbox (last checkbox in Step 1)
    // to enable the Weiter button
    cy.get('input[type="checkbox"]').last().check({ force: true });

    // Navigate to Step 2 (Power Cycle = Step3PowerCycle, which has port check)
    cy.contains('button', /weiter/i, { timeout: 5000 }).click({ force: true });

    // Trigger port check in Step 2 (Step3PowerCycle)
    cy.contains('button', /jetzt pr\u00fcfen/i, { timeout: 5000 }).click({ force: true });

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
    // Navigate through WizardChoice to Setup path
    cy.url().should('include', '/setup-wizard?deviceId=DEVICE_BEDROOM');
    cy.reload();
    cy.wait('@getDevices');
    cy.get('.setup-wizard-page-v2', { timeout: 8000 }).should('exist');
    cy.contains('Setup-Assistent').click();

    // Click back button on first step
    cy.contains('button', 'Zurück').click({ force: true });

    // Should be back on preset page - reload to bypass v7_startTransition on back navigation
    cy.url().should('match', /\/(presets)?\?device=DEVICE_BEDROOM$/);
    cy.reload();
    cy.wait('@getDevices');

    // Device should still be Schlafzimmer
    cy.get('[data-test="device-swiper"]', { timeout: 10000 }).should('contain', 'Schlafzimmer');
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

    // Start wizard – navigate through WizardChoice to Setup path
    cy.get('[data-test="setup-button"]').click();
    // Reload to bypass v7_startTransition SPA deferred rendering
    cy.url().should('include', '/setup-wizard?deviceId=DEVICE_KITCHEN');
    cy.reload();
    cy.wait('@getDevices');
    cy.get('.setup-wizard-page-v2', { timeout: 8000 }).should('exist');
    cy.contains('Setup-Assistent').click();

    // Wizard header must show the device selected via arrow button, not the URL default
    cy.get('.device-info-header').should('contain', 'Küche');
    cy.get('.device-info-header').should('contain', '192.168.1.84');

    // Go back - reload to bypass v7_startTransition on back navigation
    cy.contains('button', 'Zurück').click({ force: true });
    cy.url().should('include', '?device=DEVICE_KITCHEN');
    cy.reload();
    cy.wait('@getDevices');

    // Device swiper must still show Küche (not reset to TV)
    cy.get('[data-test="device-swiper"]', { timeout: 10000 }).should('contain', 'Küche');
  });

  it('should show correct device when accessing wizard via direct URL', () => {
    // Directly visit wizard with specific device
    visitDe('/setup-wizard?deviceId=DEVICE_KITCHEN');

    // Wait for devices to load
    cy.wait('@getDevices');
    cy.get('.setup-wizard-page-v2', { timeout: 8000 }).should('exist');
    cy.contains('Setup-Assistent').click();

    // Header must show the correct device
    cy.get('.device-info-header').should('contain', 'Küche');
    cy.get('.device-info-header').should('contain', '192.168.1.84');

    // Go back to presets - reload to bypass v7_startTransition on back navigation
    cy.contains('button', 'Zurück').click({ force: true });
    cy.url().should('include', 'device=DEVICE_KITCHEN');
    cy.reload();
    cy.wait('@getDevices');

    // Should preserve device selection
    cy.get('[data-test="device-swiper"]', { timeout: 10000 }).should('contain', 'Küche');
  });

  it('should handle invalid deviceId gracefully', () => {
    // Visit wizard with non-existent device
    visitDe('/setup-wizard?deviceId=INVALID_DEVICE');
    cy.wait('@getDevices');
    cy.get('.setup-wizard-page-v2', { timeout: 8000 }).should('exist');

    // Should fall back to first device (TV)
    cy.get('.device-info-header').should('contain', 'TV');
  });
});
