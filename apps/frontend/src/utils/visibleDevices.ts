/**
 * The device list as the user sees it: a stereo pair is one device, so the speaker that is not the
 * master of its pair is hidden. The API still lists both (setup, zones and the health check need each one).
 */
export function visibleDevices<
  T extends { stereo_role?: string | null; stereo_master?: boolean | null },
>(devices: readonly T[]): T[] {
  return devices.filter((d) => !d.stereo_role || d.stereo_master);
}
