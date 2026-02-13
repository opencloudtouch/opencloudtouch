/**
 * Tests for App.jsx Error Handling
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../../src/App';
import { QueryWrapper } from '../utils/reactQueryTestUtils';

const renderWithProviders = (component) => {
  return render(<QueryWrapper>{component}</QueryWrapper>)
}

describe('App Error Handling', () => {
  beforeEach(() => {
    // Reset fetch mock before each test
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should display error state when API fetch fails', async () => {
    // Arrange: Mock fetch to fail
    global.fetch.mockRejectedValueOnce(new Error('Network error'));

    // Act: Render app
    renderWithProviders(<App />);

    // Assert: Should show error message
    await waitFor(() => {
      expect(screen.getByText(/Fehler beim Laden der Geräte/i)).toBeInTheDocument();
    });
  });

  it('should display error state when API returns non-OK status', async () => {
    // Arrange: Mock 500 error
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    // Act: Render app
    renderWithProviders(<App />);

    // Assert: Should show error message
    await waitFor(() => {
      expect(screen.getByText(/Fehler beim Laden der Geräte/i)).toBeInTheDocument();
    });
  });

  it('should show retry button in error state', async () => {
    // Arrange: Mock fetch to fail
    global.fetch.mockRejectedValueOnce(new Error('Network error'));

    // Act: Render app
    renderWithProviders(<App />);

    // Assert: Should have retry button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeInTheDocument();
    });
  });

  it('should retry fetching devices when retry button clicked', async () => {
    // Arrange: Mock fetch to fail once, then succeed
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          devices: [
            { device_id: '123', name: 'Test Device', ip: '192.168.1.100' },
          ],
        }),
      });

    // Act: Render app and click retry
    renderWithProviders(<App />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeInTheDocument();
    });

    const retryButton = screen.getByRole('button', { name: /erneut versuchen/i });
    await userEvent.click(retryButton);

    // Assert: Should load devices successfully
    await waitFor(() => {
      expect(screen.queryByText(/Fehler beim Laden der Geräte/i)).not.toBeInTheDocument();
    });

    // Check navigation is rendered (uses data-test, not data-testid)
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('should clear error state after successful retry', async () => {
    // Arrange: Mock fetch to fail once, then succeed
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ devices: [] }),
      });

    // Act: Render app
    renderWithProviders(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Fehler beim Laden der Geräte/i)).toBeInTheDocument();
    });

    // Act: Retry
    const retryButton = screen.getByRole('button', { name: /erneut versuchen/i });
    await userEvent.click(retryButton);

    // Assert: Error message should be gone
    await waitFor(() => {
      expect(screen.queryByText(/Fehler beim Laden der Geräte/i)).not.toBeInTheDocument();
    });
  });

  it('should show loading state during retry', async () => {
    // Arrange: Mock fetch to fail once, then delay success
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockImplementationOnce(() =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => ({ devices: [] }),
              }),
            100
          )
        )
      );

    // Act: Render app and click retry
    renderWithProviders(<App />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeInTheDocument();
    });

    const retryButton = screen.getByRole('button', { name: /erneut versuchen/i });
    await userEvent.click(retryButton);

    // Assert: Should show loading state
    expect(screen.getByText(/OpenCloudTouch wird geladen/i)).toBeInTheDocument();

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText(/OpenCloudTouch wird geladen/i)).not.toBeInTheDocument();
    });
  });
});
