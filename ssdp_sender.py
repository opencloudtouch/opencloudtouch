#!/usr/bin/env python3
"""
SSDP M-SEARCH Sender - Sends real SSDP discovery requests.
Usage: python ssdp_sender.py
"""
import socket
import sys

# SSDP settings
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 1900

# Different search targets to try
SEARCH_TARGETS = [
    "ssdp:all",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "urn:schemas-upnp-org:device:Basic:1",
    "urn:dial-multiscreen-org:service:dial:1",
]

print("=" * 70)
print("SSDP M-SEARCH SENDER")
print("=" * 70)
print(f"Target: {MULTICAST_GROUP}:{MULTICAST_PORT}")
print("=" * 70 + "\n")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    for i, st in enumerate(SEARCH_TARGETS, 1):
        print(f"\n{i}. Sending M-SEARCH with ST: {st}")
        print("-" * 70)

        # Construct SSDP M-SEARCH message
        msg = (
            f"M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {MULTICAST_GROUP}:{MULTICAST_PORT}\r\n"
            f'MAN: "ssdp:discover"\r\n'
            f"MX: 3\r\n"
            f"ST: {st}\r\n"
            f"\r\n"
        ).encode('utf-8')

        print(f"Message ({len(msg)} bytes):")
        print(msg.decode('utf-8'))

        # Send
        sock.sendto(msg, (MULTICAST_GROUP, MULTICAST_PORT))
        print(f"✅ Sent to {MULTICAST_GROUP}:{MULTICAST_PORT}")

    print("\n" + "=" * 70)
    print(f"✅ Sent {len(SEARCH_TARGETS)} M-SEARCH requests")
    print("=" * 70)
    print("\n💡 Start multicast_receiver.py to see if devices respond!")

    sock.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
