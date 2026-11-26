const key = (serverId: string) => `oct.dlna.folder.${serverId}`;

/** Last folder opened on this server in this tab's session, or null. */
export function getLastFolder(serverId: string): string | null {
  try {
    return sessionStorage.getItem(key(serverId));
  } catch {
    return null;
  }
}

/** Remembers the folder for this session; the root ("0") clears the memory. */
export function setLastFolder(serverId: string, objectId: string): void {
  try {
    if (objectId === "0") sessionStorage.removeItem(key(serverId));
    else sessionStorage.setItem(key(serverId), objectId);
  } catch {
    // storage unavailable: the folder is simply not remembered
  }
}
