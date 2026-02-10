#!/usr/bin/env python3
"""Test SSDP multicast discovery from within container."""
import socket
import sys

print("Testing SSDP Multicast Discovery...", file=sys.stderr)
print(f"Container IP: binding to 0.0.0.0", file=sys.stderr)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
s.settimeout(10)

msg = b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 5\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n'
print(f"Sending M-SEARCH to 239.255.255.250:1900...", file=sys.stderr)
s.sendto(msg, ('239.255.255.250', 1900))

responses = []
try:
    while True:
        data, addr = s.recvfrom(4096)
        responses.append(addr)
        print(f"✅ Response from {addr[0]}", file=sys.stderr)
except socket.timeout:
    print(f"Timeout after 10s", file=sys.stderr)

print(f"\n{'='*50}")
print(f"RESULT: {len(responses)} devices found")
print(f"{'='*50}")

if len(responses) == 0:
    print("❌ SSDP MULTICAST BLOCKED")
    sys.exit(1)
else:
    print(f"✅ SSDP MULTICAST WORKING")
    sys.exit(0)
