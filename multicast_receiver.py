#!/usr/bin/env python3
"""
Multicast Receiver - Listens for multicast packets.
Usage: python multicast_receiver.py
"""
import socket
import struct
import sys
from datetime import datetime

# SSDP Multicast settings
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 1900

print("=" * 70)
print("MULTICAST RECEIVER")
print("=" * 70)
print(f"Multicast Group: {MULTICAST_GROUP}")
print(f"Port:            {MULTICAST_PORT}")
print("=" * 70)
print("\nStarting receiver...\n")

try:
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Allow multiple sockets to bind to same address
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to the multicast port (must bind to INADDR_ANY to receive multicast)
    sock.bind(("", MULTICAST_PORT))
    print(f"✅ Bound to 0.0.0.0:{MULTICAST_PORT}")

    # Join multicast group
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    print(f"✅ Joined multicast group {MULTICAST_GROUP}")

    print("\n" + "=" * 70)
    print("LISTENING FOR MULTICAST PACKETS... (Ctrl+C to stop)")
    print("=" * 70 + "\n")

    packet_count = 0
    sources = set()

    while True:
        try:
            data, addr = sock.recvfrom(8192)
            packet_count += 1
            sources.add(addr[0])
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            print(f"\n📦 Packet #{packet_count} at {timestamp}")
            print(f"   From:    {addr[0]}:{addr[1]}")
            print(f"   Size:    {len(data)} bytes")

            # Try to decode as text
            try:
                text = data.decode('utf-8', errors='replace')
                # Show first 200 chars
                preview = text[:200].replace('\r', '').replace('\n', ' ')
                print(f"   Preview: {preview}...")
            except:
                print(f"   Data:    {data[:50]}...")

            print(f"\n   📊 Total: {packet_count} packets from {len(sources)} unique sources")
            print("   " + "-" * 66)

        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"Total packets received: {packet_count}")
            print(f"Unique sources:         {len(sources)}")
            if sources:
                print(f"Source IPs:             {', '.join(sorted(sources))}")
            print("=" * 70)
            sys.exit(0)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
