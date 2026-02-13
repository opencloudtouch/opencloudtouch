import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import EmptyState from '../src/components/EmptyState'
import { ToastProvider } from '../src/contexts/ToastContext'
import { QueryWrapper } from './utils/reactQueryTestUtils'

// Mock fetch
global.fetch = vi.fn();

beforeEach(() => {
  vi.mocked(fetch).mockResolvedValue({
    ok: true,
    json: async () => ({ ips: [] })
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

const renderWithRouter = (component) => {
  return render(
    <QueryWrapper>
      <BrowserRouter>
        <ToastProvider>
          {component}
        </ToastProvider>
      </BrowserRouter>
    </QueryWrapper>
  )
}

describe('EmptyState Component', () => {
  it('renders welcome message', async () => {
    renderWithRouter(<EmptyState />)
    await waitFor(() => {
      expect(screen.getByText(/Willkommen bei OpenCloudTouch/i)).toBeInTheDocument()
    });
  })

  it('renders setup steps', async () => {
    renderWithRouter(<EmptyState />)
    await waitFor(() => {
      expect(screen.getByText(/Geräte einschalten/i)).toBeInTheDocument()
    });
    expect(screen.getByRole('heading', { name: /Geräte suchen/i })).toBeInTheDocument()
    expect(screen.getByText(/Presets verwalten/i)).toBeInTheDocument()
  })

  it('renders discover button', async () => {
    renderWithRouter(<EmptyState />)
    await waitFor(() => {
      const button = screen.getByRole('button', { name: /Jetzt Geräte suchen/i })
      expect(button).toBeInTheDocument()
    });
  })

  it('renders help section', async () => {
    renderWithRouter(<EmptyState />)
    await waitFor(() => {
      // Text appears in both description and help section - just check it exists
      const helpTexts = screen.queryAllByText(/Keine Geräte gefunden?/i)
      expect(helpTexts.length).toBeGreaterThan(0)
    });
  })
})
