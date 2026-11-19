/**
 * Remembers the device the user was last working with, so that every way back to the
 * Devices page (navigation bar, wizards, sub pages) lands on that device instead of the first one.
 */
const KEY = "oct:lastDevice";

export function getLastDeviceId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setLastDeviceId(deviceId: string | null | undefined): void {
  if (!deviceId) return;
  try {
    window.localStorage.setItem(KEY, deviceId);
  } catch {
    // storage unavailable (private mode): remembering is best effort
  }
}

/** URL device first, then the last device, then the first device of the list. */
export function pickDevice<T extends { device_id: string }>(
  devices: readonly T[],
  urlDeviceId: string | null | undefined
): T | undefined {
  const byId = (id: string | null | undefined) =>
    id ? devices.find((d) => d.device_id === id) : undefined;
  return byId(urlDeviceId) ?? byId(getLastDeviceId()) ?? devices[0];
}
