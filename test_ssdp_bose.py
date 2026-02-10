#!/usr/bin/env python3
"""Test SSDP with Bose-specific search target."""
import socket
import struct
import sys

search_targets = [
    "ssdp:all",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "urn:schemas-upnp-org:device:Basic:1",
]

for st in search_targets:
    print(f"\n{'=' * 70}")
    print(f"Testing with ST: {st}")
    print('=' * 70)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    mreq = struct.pack("4sl", socket.inet_aton("239.255.255.250"), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.bind(("", 1900))
    sock.settimeout(5)

    msg = f"M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 3\r\nST: {st}\r\n\r\n".encode()
    sock.sendto(msg, ("239.255.255.250", 1900))
    print(f"Sent M-SEARCH...")

    devices = {}
    try:
        while True:
            data, addr = sock.recvfrom(8192)
            response = data.decode('utf-8', errors='ignore')

            # Extract manufacturer from response
            manufacturer = "Unknown"
            for line in response.split('\r\n'):
                if 'bose' in line.lower():
                    manufacturer = "Bose"
                    break

            if addr[0] not in devices:
                devices[addr[0]] = manufacturer
                print(f"  ✅ {addr[0]} ({manufacturer})")
    except socket.timeout:
        pass

    sock.close()

    bose_count = sum(1 for v in devices.values() if v == "Bose")
    print(f"\n📊 Total: {len(devices)} devices ({bose_count} Bose)")

print(f"\n{'=' * 70}")
print("DONE")
print('=' * 70)
