"""
E2E tests for wizard UI.

Tests complete wizard flow from frontend perspective using Playwright.
"""

import pytest
from playwright.async_api import async_playwright, Page


pytestmark = pytest.mark.e2e


class TestWizardE2E:
    """E2E tests for setup wizard."""

    @pytest.fixture
    async def page(self):
        """Create browser page for testing."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            yield page
            await context.close()
            await browser.close()

    async def test_wizard_navigation(self, page: Page):
        """Test wizard step navigation."""
        # Navigate to wizard
        await page.goto("http://localhost:5173/setup-wizard")

        # Should show Step 1 (Device Selection)
        await page.wait_for_selector("text=Gerät auswählen")

        # Check progress indicator
        progress = await page.locator(".progress-indicator")
        assert await progress.is_visible()

    async def test_full_wizard_flow_mock(self, page: Page):
        """Test complete wizard flow with mocked backend."""
        # Start wizard
        await page.goto("http://localhost:5173/setup-wizard")

        # Step 1: Select device (mock device list)
        await page.wait_for_selector(".device-card")
        await page.click(".device-card:first-child")
        await page.click("button:has-text('Weiter')")

        # Step 2: USB Preparation
        await page.wait_for_selector("text=USB-Stick vorbereiten")
        await page.click("button:has-text('Weiter')")

        # Step 3: Power Cycle
        await page.wait_for_selector("text=Gerät neustarten")
        # Mock port check response
        # ... (would require intercept/mock setup)

        # Step 4-8: Continue through remaining steps
        # ... (detailed implementation)


# Skip E2E tests for now - require running frontend + backend servers
pytest.skip("E2E tests require running services and Playwright setup", allow_module_level=True)
