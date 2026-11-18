import { expect, test } from "@playwright/test";

const device = {
  device_id: "test-device-1",
  name: "Test Speaker",
  ip: "192.0.2.10",
  model: "SoundTouch 30",
  mac_address: "AA:BB:CC:DD:EE:01",
  firmware_version: "1.0.0",
  last_seen: "2026-11-18T00:00:00Z",
  setup_status: "COMPLETED",
  ssh_permanent: false,
  setup_completed_at: null,
};

test.use({ forcedColors: "active" });

test("shuffle and repeat stay readable and focusable in forced colors", async ({ page }) => {
  // Catch-all first: later routes take precedence over it.
  await page.route("**/api/**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/devices", (route) => route.fulfill({ json: { devices: [device] } }));
  await page.route("**/api/devices/*/now-playing", (route) =>
    route.fulfill({
      json: {
        source: "BLUETOOTH",
        state: "PLAY_STATE",
        online: true,
        skip_enabled: true,
        shuffle_setting: "SHUFFLE_ON",
        repeat_setting: "REPEAT_ONE",
      },
    })
  );

  await page.goto("/");

  const shuffle = page.locator('[data-test="dv-SHUFFLE"]');
  const repeat = page.locator('[data-test="dv-REPEAT"]');
  await expect(shuffle).toHaveAttribute("aria-pressed", "true");
  await expect(repeat).toHaveAttribute("aria-pressed", "true");
  await expect(repeat.locator(".tp-badge")).toHaveText("1");

  await repeat.focus();
  const outline = await repeat.evaluate((el) => {
    const style = getComputedStyle(el);
    return { style: style.outlineStyle, width: style.outlineWidth };
  });
  expect(outline.style).not.toBe("none");
  expect(outline.width).not.toBe("0px");
});
