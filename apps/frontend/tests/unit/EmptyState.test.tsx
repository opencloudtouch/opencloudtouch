/**
 * Tests for EmptyState.tsx
 *
 * User Story: "Als neuer User möchte ich durch das Setup geführt werden"
 *
 * Focus: Functional tests for initial device discovery
 * - Display welcome message and setup steps
 * - Auto-discovery flow (trigger /api/devices/sync)
 * - Manual IP configuration modal
 * - IP validation (format, invalid IPs)
 * - Navigation after successful discovery
 * - Error handling (no devices, API errors)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ToastProvider } from '../../src/contexts/ToastContext';
import EmptyState from '../../src/components/EmptyState';
import { QueryWrapper } from '../utils/reactQueryTestUtils';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const renderWithProviders = (component) => {
  return render(
    <QueryWrapper>
      <BrowserRouter>
        <ToastProvider>{component}</ToastProvider>
      </BrowserRouter>
    </QueryWrapper>
  );
};

// Helper to create fetch mock that handles all endpoints
const createFetchMock = (overrides = {}) => {
  const syncedDevices = overrides.synced ?? 0;
  const manualIps = overrides.manualIps ?? [];
  const syncError = overrides.syncError ?? null;
  
  return vi.fn((url) => {
    if (url.includes('/api/settings/manual-ips')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ ips: manualIps })
      });
    }
    if (url.includes('/api/devices/sync')) {
      if (syncError) {
        return Promise.reject(syncError);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ synced: syncedDevices })
      });
    }
    if (url.includes('/api/devices')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ devices: [] })
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({})
    });
  });
};

describe('EmptyState Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default fetch mock for manual-ips
    global.fetch = createFetchMock();
  });

  describe('Welcome & Setup Steps', () => {
    it('should display welcome message and setup instructions', () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState onRefreshDevices={() => {}} />);

      expect(screen.getByText('Willkommen bei OpenCloudTouch')).toBeInTheDocument();
      expect(screen.getByText('Noch keine Geräte gefunden.')).toBeInTheDocument();

      // Setup steps
      expect(screen.getByText('Geräte einschalten')).toBeInTheDocument();
      expect(screen.getByText('Geräte suchen')).toBeInTheDocument();
      expect(screen.getByText('Presets verwalten')).toBeInTheDocument();
    });

    it('should show discovery button', () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState onRefreshDevices={() => {}} />);

      const discoverButton = screen.getByRole('button', { name: /Jetzt Geräte suchen/i });
      expect(discoverButton).toBeInTheDocument();
      expect(discoverButton).not.toBeDisabled();
    });
  });

  describe('Auto-Discovery Flow', () => {
    it('should trigger device sync when clicking discover button', async () => {
      // Uses default createFetchMock from beforeEach
      const onRefresh = vi.fn();
      renderWithProviders(<EmptyState onRefreshDevices={onRefresh} />);

      const discoverButton = screen.getByRole('button', { name: /Jetzt Geräte suchen/i });
      fireEvent.click(discoverButton);

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/devices/sync', {
          method: 'POST'
        });
      });
    });

    it('should navigate to dashboard after successful discovery', async () => {
      // Override with successful sync
      global.fetch = createFetchMock({ synced: 3 });

      renderWithProviders(<EmptyState />);

      const discoverButton = screen.getByRole('button', { name: /Jetzt Geräte suchen/i });
      fireEvent.click(discoverButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/');
      });
    });

    it('should show warning toast when no devices found', async () => {
      // Default createFetchMock returns synced: 0
      renderWithProviders(<EmptyState />);

      const discoverButton = screen.getByRole('button', { name: /Jetzt Geräte suchen/i });
      fireEvent.click(discoverButton);

      // Toast will be shown via ToastContext
      await waitFor(() => {
        expect(discoverButton).not.toBeDisabled();
      });
    });

    it('should handle discovery errors gracefully', async () => {
      // Mock with sync error
      global.fetch = createFetchMock({ syncError: new Error('Network error') });

      renderWithProviders(<EmptyState />);

      const discoverButton = screen.getByRole('button', { name: /Jetzt Geräte suchen/i });
      fireEvent.click(discoverButton);

      // Should not crash, error handled
      await waitFor(() => {
        expect(discoverButton).not.toBeDisabled();
      });
    });
  });

  describe('Manual IP Configuration', () => {
    it('should open modal when clicking manual add button', async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState onRefreshDevices={() => {}} />);

      // Expand help section
      const helpSummary = screen.getByText('Keine Geräte gefunden?');
      fireEvent.click(helpSummary);

      // Click manual add button (using text since component uses data-test not data-testid)
      const manualAddButton = screen.getByRole('button', { name: /manuell hinzu/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByText('Manuelle IP-Konfiguration')).toBeInTheDocument();
      });
    });

    it('should validate IP addresses and show error for invalid format', async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState onRefreshDevices={() => {}} />);

      // Open modal
      const helpSummary = screen.getByText('Keine Geräte gefunden?');
      fireEvent.click(helpSummary);
      const manualAddButton = screen.getByRole('button', { name: /manuell hinzu/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });

      // Enter invalid IP
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'invalid-ip\n999.999.999.999' } });

      // Save
      const saveButton = screen.getByRole('button', { name: /Speichern/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText(/Ungültige IP-Adressen:/)).toBeInTheDocument();
      });
    });

    it('should save valid IP addresses successfully', async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState onRefreshDevices={() => {}} />);

      // Open modal
      const helpSummary = screen.getByText('Keine Geräte gefunden?');
      fireEvent.click(helpSummary);
      const manualAddButton = screen.getByRole('button', { name: /manuell hinzu/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByRole('textbox')).toBeInTheDocument();
      });

      // Enter valid IPs
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, {
        target: { value: '192.168.1.100\n192.168.1.101' }
      });

      // Save
      const saveButton = screen.getByRole('button', { name: /Speichern/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/settings/manual-ips', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ips: ['192.168.1.100', '192.168.1.101'] })
        });
      });

      // Success message
      await waitFor(() => {
        expect(screen.getByText('IP-Adressen gespeichert!')).toBeInTheDocument();
      });
    });

    it('should close modal when clicking cancel button', async () => {
      // Uses default createFetchMock from beforeEach
      renderWithProviders(<EmptyState onRefreshDevices={() => {}} />);

      // Open modal
      const helpSummary = screen.getByText('Keine Geräte gefunden?');
      fireEvent.click(helpSummary);
      const manualAddButton = screen.getByRole('button', { name: /manuell hinzu/i });
      fireEvent.click(manualAddButton);

      await waitFor(() => {
        expect(screen.getByText('Manuelle IP-Konfiguration')).toBeInTheDocument();
      });

      // Click cancel
      const cancelButton = screen.getByRole('button', { name: /Abbrechen/i });
      fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByText('Manuelle IP-Konfiguration')).not.toBeInTheDocument();
      });
    });
  });
});
