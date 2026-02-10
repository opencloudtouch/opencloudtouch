#!/usr/bin/env python3
"""Test SSDP multicast discovery directly in WSL2."""
import socket
import struct
import sys

print("=" * 60)
print("SSDP Multicast Test in WSL2")
print("=" * 60)

# Create socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Join multicast group (CRITICAL!)
mreq = struct.pack("4sl", socket.inet_aton("239.255.255.250"), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
print("✅ Joined multicast group 239.255.255.250")

# Bind to SSDP port to receive responses
sock.bind(("", 1900))
print("✅ Bound to port 1900")

sock.settimeout(10)

# Send M-SEARCH
msg = b"M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 3\r\nST: ssdp:all\r\n\r\n"
sock.sendto(msg, ("239.255.255.250", 1900))
print("✅ Sent M-SEARCH to 239.255.255.250:1900")
print("\nWaiting 10s for responses...\n")

count = 0
devices = set()
try:
    while True:
        data, addr = sock.recvfrom(8192)
        count += 1
        devices.add(addr[0])
        print(f"  [{count}] Response from {addr[0]}")
except socket.timeout:
    print("\n⏱️  Timeout after 10s")

print("\n" + "=" * 60)
print(f"RESULT: {len(devices)} unique device(s) found")
print(f"        {count} total responses")
print("=" * 60)

if len(devices) == 0:
    print("\n❌ SSDP MULTICAST BLOCKED IN WSL2!")
    sys.exit(1)
else:
    print(f"\n✅ SSDP MULTICAST WORKING! Found: {', '.join(sorted(devices))}")
    sys.exit(0)
