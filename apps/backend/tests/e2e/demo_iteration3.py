#!/usr/bin/env python3
"""
E2E Demo Script for Iteration 3: Preset Management

Demonstrates:
- Setting radio presets via API (POST /api/presets/set)
- Getting presets for devices (GET /api/presets/{device_id})
- Station descriptor endpoint (GET /stations/preset/{device_id}/{preset_number}.json)
- Clearing presets (DELETE /api/presets/{device_id}/{preset_number})
- Full preset management workflow

Usage:
  python e2e/demo_iteration3.py              # Mock mode (CI-friendly)
  python e2e/demo_iteration3.py --real       # Real API + RadioBrowser

Prerequisites:
  - Backend running on http://localhost:7777
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, List

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx


class PresetDemoRunner:
    """Demo runner for Iteration 3 preset functionality."""

    def __init__(self, base_url: str = "http://localhost:7777"):
        """Initialize demo runner."""
        self.base_url = base_url
        self.device_id = "demo-soundtouch-001"
        self.results: List[Dict] = []

    def log(self, message: str, level: str = "INFO") -> None:
        """Log message to console."""
        symbols = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "STEP": "→"}
        symbol = symbols.get(level, "  ")
        print(f"{symbol}  {message}")

    def add_result(self, test: str, passed: bool, details: str = "") -> None:
        """Add test result."""
        self.results.append({"test": test, "passed": passed, "details": details})
        status = "✅ PASS" if passed else "❌ FAIL"
        self.log(f"{test}: {status} {details}", "SUCCESS" if passed else "ERROR")

    async def run(self) -> bool:
        """
        Run the demo.

        Returns:
            True if all tests passed, False otherwise
        """
        self.log("=" * 60)
        self.log("Iteration 3 Demo: Preset Management")
        self.log("=" * 60)

        async with httpx.AsyncClient() as client:
            # Step 1: Set Preset 1
            self.log("\nStep 1: Setting Preset 1 (Rock Radio)", "STEP")
            try:
                response = await client.post(
                    f"{self.base_url}/api/presets/set",
                    json={
                        "device_id": self.device_id,
                        "preset_number": 1,
                        "station_uuid": "960761d5-0601-11e8-ae97-52543be04c81",
                        "station_name": "Absolut Relax",
                        "station_url": "http://streamlive.syndicast.fr/HautDeFrance-Picardie/all/absoluthautsdefrance-relax.mp3",
                        "station_homepage": "https://www.absolut-radio.fr",
                        "station_favicon": "https://www.absolut-radio.fr/favicon.png",
                    },
                )
                passed = response.status_code == 201
                self.add_result(
                    "Set Preset 1",
                    passed,
                    f"Status: {response.status_code}",
                )
            except Exception as e:
                self.add_result("Set Preset 1", False, str(e))

            # Step 2: Set Preset 3
            self.log("\nStep 2: Setting Preset 3 (Jazz Station)", "STEP")
            try:
                response = await client.post(
                    f"{self.base_url}/api/presets/set",
                    json={
                        "device_id": self.device_id,
                        "preset_number": 3,
                        "station_uuid": "9607621a-0601-11e8-ae97-52543be04c81",
                        "station_name": "Radio Swiss Jazz",
                        "station_url": "http://stream.srg-ssr.ch/m/rsj/mp3_128",
                        "station_homepage": "https://www.radioswissjazz.ch",
                        "station_favicon": "https://www.radioswissjazz.ch/favicon.ico",
                    },
                )
                passed = response.status_code == 201
                self.add_result(
                    "Set Preset 3",
                    passed,
                    f"Status: {response.status_code}",
                )
            except Exception as e:
                self.add_result("Set Preset 3", False, str(e))

            # Step 3: Get all presets for device
            self.log("\nStep 3: Getting all presets for device", "STEP")
            try:
                response = await client.get(
                    f"{self.base_url}/api/presets/{self.device_id}"
                )
                passed = response.status_code == 200
                data = response.json() if passed else []
                preset_count = len(data)
                self.add_result(
                    "Get Device Presets",
                    passed and preset_count == 2,
                    f"Found {preset_count} presets",
                )

                if passed:
                    for preset in data:
                        self.log(
                            f"  Preset {preset['preset_number']}: "
                            f"{preset['station_name']}"
                        )
            except Exception as e:
                self.add_result("Get Device Presets", False, str(e))

            # Step 4: Get specific preset
            self.log("\nStep 4: Getting Preset 1 details", "STEP")
            try:
                response = await client.get(
                    f"{self.base_url}/api/presets/{self.device_id}/1"
                )
                passed = response.status_code == 200
                data = response.json() if passed else {}
                self.add_result(
                    "Get Preset 1",
                    passed,
                    f"Station: {data.get('station_name', 'N/A')}",
                )
            except Exception as e:
                self.add_result("Get Preset 1", False, str(e))

            # Step 5: Get station descriptor (what SoundTouch device fetches)
            self.log("\nStep 5: Getting Station Descriptor (SoundTouch format)", "STEP")
            try:
                response = await client.get(
                    f"{self.base_url}/stations/preset/{self.device_id}/1.json"
                )
                passed = response.status_code == 200
                data = response.json() if passed else {}
                self.add_result(
                    "Station Descriptor",
                    passed and "streamUrl" in data,
                    f"Stream URL: {data.get('streamUrl', 'N/A')[:50]}...",
                )

                if passed:
                    self.log(f"  Station Name: {data.get('stationName')}")
                    self.log(f"  Stream URL: {data.get('streamUrl')}")
                    self.log(f"  Homepage: {data.get('homepage')}")
            except Exception as e:
                self.add_result("Station Descriptor", False, str(e))

            # Step 6: Update existing preset
            self.log("\nStep 6: Updating Preset 1 (overwrite)", "STEP")
            try:
                response = await client.post(
                    f"{self.base_url}/api/presets/set",
                    json={
                        "device_id": self.device_id,
                        "preset_number": 1,
                        "station_uuid": "9607627c-0601-11e8-ae97-52543be04c81",
                        "station_name": "Bayern 3",
                        "station_url": "http://streams.br.de/bayern3_2.m3u",
                        "station_homepage": "https://www.br.de/radio/bayern3/",
                    },
                )
                passed = response.status_code == 201
                self.add_result(
                    "Update Preset 1",
                    passed,
                    f"Status: {response.status_code}",
                )

                # Verify update
                response = await client.get(
                    f"{self.base_url}/api/presets/{self.device_id}/1"
                )
                if response.status_code == 200:
                    data = response.json()
                    is_updated = data.get("station_name") == "Bayern 3"
                    self.add_result(
                        "Verify Update",
                        is_updated,
                        f"New station: {data.get('station_name')}",
                    )
            except Exception as e:
                self.add_result("Update Preset", False, str(e))

            # Step 7: Clear specific preset
            self.log("\nStep 7: Clearing Preset 3", "STEP")
            try:
                response = await client.delete(
                    f"{self.base_url}/api/presets/{self.device_id}/3"
                )
                passed = response.status_code == 200
                self.add_result(
                    "Clear Preset 3",
                    passed,
                    f"Status: {response.status_code}",
                )

                # Verify deletion
                response = await client.get(
                    f"{self.base_url}/api/presets/{self.device_id}/3"
                )
                is_deleted = response.status_code == 404
                self.add_result(
                    "Verify Deletion",
                    is_deleted,
                    f"Status: {response.status_code} (expected 404)",
                )
            except Exception as e:
                self.add_result("Clear Preset", False, str(e))

            # Step 8: Verify final state
            self.log("\nStep 8: Verifying final state (should have 1 preset)", "STEP")
            try:
                response = await client.get(
                    f"{self.base_url}/api/presets/{self.device_id}"
                )
                data = response.json() if response.status_code == 200 else []
                passed = len(data) == 1
                self.add_result(
                    "Final State",
                    passed,
                    f"Preset count: {len(data)} (expected 1)",
                )
            except Exception as e:
                self.add_result("Final State", False, str(e))

        # Print summary
        self.log("\n" + "=" * 60)
        self.log("Demo Summary")
        self.log("=" * 60)

        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        success_rate = (passed_count / total_count * 100) if total_count > 0 else 0

        for result in self.results:
            status = "✅" if result["passed"] else "❌"
            self.log(f"{status} {result['test']}")

        self.log(
            f"\nTotal: {passed_count}/{total_count} tests passed ({success_rate:.1f}%)"
        )

        all_passed = passed_count == total_count
        if all_passed:
            self.log("\n🎉 All tests PASSED! Iteration 3 complete!", "SUCCESS")
        else:
            self.log(f"\n⚠️  {total_count - passed_count} tests FAILED", "ERROR")

        return all_passed


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Iteration 3 E2E Demo")
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real backend (default: mock mode)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:7777",
        help="Backend URL (default: http://localhost:7777)",
    )
    args = parser.parse_args()

    runner = PresetDemoRunner(base_url=args.url)
    success = await runner.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
