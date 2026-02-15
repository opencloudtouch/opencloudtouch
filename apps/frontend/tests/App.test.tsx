import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../src/App'
import { QueryWrapper } from './utils/reactQueryTestUtils'

// Mock fetch globally
global.fetch = vi.fn()

// Helper to mock multiple endpoints
const mockFetchResponses = (devices = [], manualIps = []) => {
  fetch.mockImplementation((url) => {
    if (url.includes('/api/devices')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ devices })
      });
    }
    if (url.includes('/api/settings/manual-ips')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ ips: manualIps })
      });
    }
    if (url.includes('/api/presets')) {
      return Promise.resolve({
        ok: true,
        json: async () => []
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({})
    });
  });
};

const renderWithProviders = (component) => {
  return render(<QueryWrapper>{component}</QueryWrapper>)
}

describe('App Component', () => {
  beforeEach(() => {
    fetch.mockClear()
  })

  it('shows empty state when no devices found', async () => {
    mockFetchResponses([]);

    renderWithProviders(<App />)

    await waitFor(() => {
      expect(screen.getByText(/Willkommen bei OpenCloudTouch/i)).toBeInTheDocument()
    })
  })

  it('fetches devices on mount', async () => {
    mockFetchResponses([{ id: '1', device_id: '1', name: 'Test Device' }]);

    renderWithProviders(<App />)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/devices')
    })
  })

  it('renders navigation when devices exist', async () => {
    mockFetchResponses([{ id: '1', device_id: '1', name: 'Test Device' }]);

    renderWithProviders(<App />)

    await waitFor(() => {
      // Navigation should be visible
      const nav = screen.getByRole('navigation')
      expect(nav).toBeInTheDocument()
    })
  })
})
