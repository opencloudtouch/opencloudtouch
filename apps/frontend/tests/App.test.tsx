import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../src/App'
import { QueryWrapper } from './utils/reactQueryTestUtils'

// Mock fetch globally
global.fetch = vi.fn()

const renderWithProviders = (component) => {
  return render(<QueryWrapper>{component}</QueryWrapper>)
}

describe('App Component', () => {
  beforeEach(() => {
    fetch.mockClear()
  })

  it('shows empty state when no devices found', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [] })
    })

    renderWithProviders(<App />)

    await waitFor(() => {
      expect(screen.getByText(/Willkommen bei OpenCloudTouch/i)).toBeInTheDocument()
    })
  })

  it('fetches devices on mount', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [{ id: '1', device_id: '1', name: 'Test Device' }] })
    })

    renderWithProviders(<App />)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/devices')
    })
  })

  it('renders navigation when devices exist', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ devices: [{ id: '1', device_id: '1', name: 'Test Device' }] })
    })

    renderWithProviders(<App />)

    await waitFor(() => {
      // Navigation should be visible
      const nav = screen.getByRole('navigation')
      expect(nav).toBeInTheDocument()
    })
  })
})
