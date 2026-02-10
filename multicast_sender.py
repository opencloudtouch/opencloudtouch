#!/usr/bin/env python3
"""
Multicast Sender - Sends test multicast packets.
Usage: python multicast_sender.py [message] [count]
"""
import socket
import sys
import time
from datetime import datetime

# SSDP Multicast settings
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 1900

# Parse arguments
message = sys.argv[1] if len(sys.argv) > 1 else "HELLO FROM MULTICAST SENDER"
count = int(sys.argv[2]) if len(sys.argv) > 2 else 5

print("=" * 70)
print("MULTICAST SENDER")
print("=" * 70)
print(f"Multicast Group: {MULTICAST_GROUP}")
print(f"Port:            {MULTICAST_PORT}")
print(f"Message:         {message}")
print(f"Packets to send: {count}")
print("=" * 70 + "\n")

try:
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Set multicast TTL (time-to-live)
    # 1 = same subnet, 2 = same site, >2 = multiple sites
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    print("✅ Socket created")
    print(f"✅ Multicast TTL set to 2\n")

    print("Sending packets...\n")

    for i in range(1, count + 1):
        # Create test message
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_message = f"[{timestamp}] Packet #{i}: {message}"
        data = full_message.encode('utf-8')

        # Send to multicast group
        sock.sendto(data, (MULTICAST_GROUP, MULTICAST_PORT))

        print(f"📤 Sent packet #{i}/{count} ({len(data)} bytes)")

        # Wait 1 second between packets
        if i < count:
            time.sleep(1)

    print("\n" + "=" * 70)
    print(f"✅ Successfully sent {count} packets to {MULTICAST_GROUP}:{MULTICAST_PORT}")
    print("=" * 70)

    sock.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
