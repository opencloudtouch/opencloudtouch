#!/usr/bin/env python3
"""Direct SSDP test to debug network connectivity."""

import socket
import logging

logging.basicConfig(level=logging.DEBUG)

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.settimeout(5)

msg = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 3\r\n"
    "ST: ssdp:all\r\n"
    "\r\n"
).encode("utf-8")

print("Sending SSDP M-SEARCH...")
try:
    sock.sendto(msg, (SSDP_ADDR, SSDP_PORT))
    print("Sent successfully")
except Exception as e:
    print(f"Send failed: {e}")
    exit(1)

print("Waiting for responses (5s timeout)...")
count = 0
try:
    while True:
        data, addr = sock.recvfrom(8192)
        count += 1
        response = data.decode("utf-8", errors="ignore")
        print(f"\n=== Response {count} from {addr[0]} ===")
        # Check for Bose manufacturer
        if "bose" in response.lower():
            print("*** BOSE DEVICE FOUND ***")
        # Show first 500 chars of response
        print(response[:500])
except socket.timeout:
    print(f"\nTimeout - received {count} responses total")
except Exception as e:
    print(f"Error: {e}")
finally:
    sock.close()
