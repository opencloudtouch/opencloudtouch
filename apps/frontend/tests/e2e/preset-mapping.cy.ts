/**
 * E2E Tests: Preset Mapping (Iteration 3)
 * Tests preset assignment workflow: Search station → Assign to preset → Verify persistence
 *
 * Prerequisites:
 * - Backend running with OCT_MOCK_MODE=true
 * - MockDiscoveryAdapter returns 3 predefined devices
 * - RadioBrowser API available (real or mocked)
 */
describe('Preset Mapping (Iteration 3)', () => {
  const apiUrl = Cypress.env('apiUrl')
  let deviceId: string

  beforeEach(() => {
    // Clear devices and presets before each test
    cy.request('DELETE', `${apiUrl}/devices`)

    // Discover devices (MockDiscoveryAdapter returns 3 devices)
    cy.visit('/welcome')
    cy.get('[data-test="discover-button"]').click()
    cy.waitForDevices()

    // Get first device ID for preset tests
    cy.request(`${apiUrl}/devices`).then((response) => {
      deviceId = response.body.devices[0].device_id
      // Clear any existing presets for this device
      cy.request('GET', `${apiUrl}/presets/${deviceId}`).then((presetsResp) => {
        presetsResp.body.forEach((preset: { preset_number: number }) => {
          cy.request('DELETE', `${apiUrl}/presets/${deviceId}/${preset.preset_number}`)
        })
      })
    })
  })

  describe('Happy Path - Assign Station to Preset', () => {
    it('should assign radio station to preset 1 and persist', () => {
      // Navigate to radio search page (assumes /radio route exists)
      cy.visit('/radio')

      // Search for a station (assumes search input exists)
      cy.get('[data-test="radio-search-input"]').type('Jazz')
      cy.get('[data-test="search-button"]').click()

      // Wait for search results
      cy.get('[data-test="station-card"]', { timeout: 10000 }).should('have.length.greaterThan', 0)

      // Select first station
      cy.get('[data-test="station-card"]').first().within(() => {
        // Get station details for verification later
        cy.get('[data-test="station-name"]').invoke('text').as('stationName')
        cy.get('[data-test="station-uuid"]').invoke('attr', 'data-uuid').as('stationUuid')

        // Click "Assign to Preset" button
        cy.get('[data-test="assign-preset-button"]').click()
      })

      // Preset selection modal should appear
      cy.get('[data-test="preset-modal"]').should('be.visible')

      // Select preset 1
      cy.get('[data-test="preset-button-1"]').click()

      // Confirm assignment
      cy.get('[data-test="confirm-assign-button"]').click()

      // Success message should appear
      cy.get('[data-test="success-message"]').should('contain', 'Preset 1 assigned')

      // Verify preset was saved via API
      cy.get('@stationName').then((stationName) => {
        cy.get('@stationUuid').then((stationUuid) => {
          cy.request(`${apiUrl}/presets/${deviceId}`).then((response) => {
            expect(response.status).to.eq(200)
            expect(response.body).to.have.length(1)
            expect(response.body[0]).to.deep.include({
              device_id: deviceId,
              preset_number: 1,
              station_uuid: stationUuid,
              station_name: stationName,
            })
          })
        })
      })
    })

    it('should assign different stations to multiple presets', () => {
      // Assign to preset 1
      cy.visit('/radio')
      cy.get('[data-test="radio-search-input"]').type('Classical')
      cy.get('[data-test="search-button"]').click()
      cy.get('[data-test="station-card"]', { timeout: 10000 }).first().within(() => {
        cy.get('[data-test="assign-preset-button"]').click()
      })
      cy.get('[data-test="preset-button-1"]').click()
      cy.get('[data-test="confirm-assign-button"]').click()
      cy.get('[data-test="success-message"]').should('be.visible')

      // Assign to preset 3
      cy.get('[data-test="radio-search-input"]').clear().type('Rock')
      cy.get('[data-test="search-button"]').click()
      cy.get('[data-test="station-card"]', { timeout: 10000 }).eq(1).within(() => {
        // Use second station to ensure different from first
        cy.get('[data-test="assign-preset-button"]').click()
      })
      cy.get('[data-test="preset-button-3"]').click()
      cy.get('[data-test="confirm-assign-button"]').click()
      cy.get('[data-test="success-message"]').should('be.visible')

      // Verify both presets exist
      cy.request(`${apiUrl}/presets/${deviceId}`).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body).to.have.length(2)

        const presetNumbers = response.body.map((p: { preset_number: number }) => p.preset_number)
        expect(presetNumbers).to.include.members([1, 3])
      })
    })

    it('should overwrite existing preset when reassigning', () => {
      // First assignment
      cy.visit('/radio')
      cy.get('[data-test="radio-search-input"]').type('News')
      cy.get('[data-test="search-button"]').click()
      cy.get('[data-test="station-card"]', { timeout: 10000 }).first().within(() => {
        cy.get('[data-test="station-name"]').invoke('text').as('firstStationName')
        cy.get('[data-test="assign-preset-button"]').click()
      })
      cy.get('[data-test="preset-button-2"]').click()
      cy.get('[data-test="confirm-assign-button"]').click()
      cy.get('[data-test="success-message"]').should('be.visible')

      // Second assignment to same preset (should overwrite)
      cy.get('[data-test="radio-search-input"]').clear().type('Electronic')
      cy.get('[data-test="search-button"]').click()
      cy.get('[data-test="station-card"]', { timeout: 10000 }).eq(1).within(() => {
        cy.get('[data-test="station-name"]').invoke('text').as('secondStationName')
        cy.get('[data-test="assign-preset-button"]').click()
      })
      cy.get('[data-test="preset-button-2"]').click()
      cy.get('[data-test="confirm-assign-button"]').click()
      cy.get('[data-test="success-message"]').should('be.visible')

      // Verify only second station is on preset 2
      cy.get('@firstStationName').then((firstStation) => {
        cy.get('@secondStationName').then((secondStation) => {
          cy.request(`${apiUrl}/presets/${deviceId}`).then((response) => {
            expect(response.status).to.eq(200)
            const preset2 = response.body.find((p: { preset_number: number }) => p.preset_number === 2)
            expect(preset2).to.exist
            expect(preset2.station_name).to.eq(secondStation)
            expect(preset2.station_name).to.not.eq(firstStation) // Overwritten
          })
        })
      })
    })
  })

  describe('Error Handling', () => {
    it('should validate preset number (1-6 only)', () => {
      // Directly test API endpoint with invalid preset number
      cy.request({
        method: 'POST',
        url: `${apiUrl}/presets/set`,
        failOnStatusCode: false,
        body: {
          device_id: deviceId,
          preset_number: 7, // Invalid (must be 1-6)
          station_uuid: 'test-uuid',
          station_name: 'Test Station',
          station_url: 'http://test.com/stream',
        }
      }).then((response) => {
        expect(response.status).to.eq(422) // Validation error
      })
    })

    it('should handle backend errors gracefully', () => {
      // Mock a backend error by requesting with invalid data
      cy.request({
        method: 'POST',
        url: `${apiUrl}/presets/set`,
        failOnStatusCode: false,
        body: {
          device_id: deviceId,
          preset_number: 1,
          // Missing required fields → should fail
        }
      }).then((response) => {
        expect(response.status).to.be.greaterThan(399) // 4xx or 5xx error
      })
    })
  })

  describe('Preset Deletion', () => {
    it('should delete assigned preset', () => {
      // Assign a preset first
      cy.visit('/radio')
      cy.get('[data-test="radio-search-input"]').type('Pop')
      cy.get('[data-test="search-button"]').click()
      cy.get('[data-test="station-card"]', { timeout: 10000 }).first().within(() => {
        cy.get('[data-test="assign-preset-button"]').click()
      })
      cy.get('[data-test="preset-button-4"]').click()
      cy.get('[data-test="confirm-assign-button"]').click()
      cy.get('[data-test="success-message"]').should('be.visible')

      // Verify preset exists
      cy.request(`${apiUrl}/presets/${deviceId}`).its('body').should('have.length', 1)

      // Delete preset via API (UI deletion can be added later)
      cy.request('DELETE', `${apiUrl}/presets/${deviceId}/4`)

      // Verify preset deleted
      cy.request(`${apiUrl}/presets/${deviceId}`).its('body').should('have.length', 0)
    })
  })

  describe('Multi-Device Presets', () => {
    it('should manage presets independently for different devices', () => {
      // Get second device ID
      cy.request(`${apiUrl}/devices`).then((response) => {
        const device1Id = response.body.devices[0].device_id
        const device2Id = response.body.devices[1].device_id

        // Assign preset 1 to device 1
        cy.request('POST', `${apiUrl}/presets/set`, {
          device_id: device1Id,
          preset_number: 1,
          station_uuid: 'station-a',
          station_name: 'Station A',
          station_url: 'http://a.com/stream',
        })

        // Assign preset 1 to device 2 (different station)
        cy.request('POST', `${apiUrl}/presets/set`, {
          device_id: device2Id,
          preset_number: 1,
          station_uuid: 'station-b',
          station_name: 'Station B',
          station_url: 'http://b.com/stream',
        })

        // Verify both devices have different preset 1
        cy.request(`${apiUrl}/presets/${device1Id}`).then((resp1) => {
          cy.request(`${apiUrl}/presets/${device2Id}`).then((resp2) => {
            expect(resp1.body[0].station_name).to.eq('Station A')
            expect(resp2.body[0].station_name).to.eq('Station B')
            expect(resp1.body[0].station_uuid).to.not.eq(resp2.body[0].station_uuid)
          })
        })
      })
    })
  })
})
