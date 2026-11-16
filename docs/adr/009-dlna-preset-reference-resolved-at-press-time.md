# ADR 009 — A DLNA preset stores a reference and resolves it at press time (cache-only)

**Date**: 2026-11-16  
**Status**: Accepted  
**Deciders**: OpenCloudTouch maintainers

---

## Context

A preset button programs the speaker with an Orion location; on press the speaker asks OpenCloudTouch for the stream URL and fetches the audio itself. Media server resource URLs contain the server IP address and often a session token, and the IP changes (DHCP). Object ids can change as well.

## Options considered

1. **Store the resource URL** in the preset. Simple, but it breaks on every IP change and puts tokens into the database, the speaker and the logs.
2. **Store a reference** (media server UDN + object id) and resolve it on press (chosen).
3. Store a reference and rediscover the network on every press. Robust, but an SSDP scan takes seconds and the speaker gives up waiting.

## Decision

Option 2 with a cache-only lookup: the press uses only the discovery cache and a 3 s budget; a cache miss fails fast (503) and schedules one background discovery (also run once at startup). The reference is built by one module (`core/dlna_reference.py`); the request can never supply a URL; resource and cover URLs must be `http(s)` on the host of the media server's control URL. The `presets` table is reused (`source='DLNA'`, `station_url='dlna://...'`), so no migration is needed.

## Consequences

- The first press after a restart or a server IP change may fail once; this is documented.
- Servers that renumber object ids after a rescan need the preset assigned again; no fuzzy matching.
- Every reader of `station_url` must know DLNA presets (parser, Marge, playlist, stream proxy, descriptor, ICY lookup); a test per consumer guards this.
- A folder plays only its first audio item; a queue needs a different mechanism (separate spike).
- The Orion location length (1024 characters) and the speaker's patience for the press (3 s) are conservative defaults pending hardware verification.
