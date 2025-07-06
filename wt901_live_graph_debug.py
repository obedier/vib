#!/usr/bin/env python3
"""
WT901BLE68 BLE Service Discovery
Debug script to find the correct service and characteristic UUIDs
"""

import asyncio
from bleak import BleakScanner, BleakClient

# Default device MAC address for Allora yacht
DEFAULT_DEVICE_MAC = "CC726E53-F6B5-6245-D962-948F091FCBFA"

async def discover_services():
    """Discover all services and characteristics of the WT901BLE68"""
    print(f"Connecting to {DEFAULT_DEVICE_MAC}...")
    
    try:
        async with BleakClient(DEFAULT_DEVICE_MAC) as client:
            print(f"Connected! Device: {client.address}")
            # Try to get services (compatible with different bleak versions)
            services = getattr(client, 'services', None)
            if services is None or len(list(services)) == 0:
                await client.get_services()
                services = getattr(client, 'services', None)
            if services is None or len(list(services)) == 0:
                print("No services found!")
                return
            services_list = list(services)
            print(f"\nFound {len(services_list)} services:")
            for i, service in enumerate(services_list):
                print(f"\nService {i+1}: {service.uuid}")
                print(f"  Description: {getattr(service, 'description', '')}")
                characteristics = getattr(service, 'characteristics', [])
                print(f"  Characteristics ({len(characteristics)}):")
                for j, char in enumerate(characteristics):
                    print(f"    {j+1}. UUID: {char.uuid}")
                    print(f"       Properties: {getattr(char, 'properties', [])}")
                    print(f"       Handle: {getattr(char, 'handle', None)}")
                    if getattr(char, 'description', None):
                        print(f"       Description: {char.description}")
                    if "notify" in getattr(char, 'properties', []):
                        print(f"       *** NOTIFY CHARACTERISTIC ***")
                        print(f"       This is likely the data stream!")
                    print()
            print("\n=== Common WT901 Service Patterns ===")
            for service in services_list:
                if "ffe0" in service.uuid.lower():
                    print(f"Found FFE0 service: {service.uuid}")
                    for char in getattr(service, 'characteristics', []):
                        if "ffe1" in char.uuid.lower():
                            print(f"  Found FFE1 characteristic: {char.uuid}")
                            print(f"  Properties: {getattr(char, 'properties', [])}")
                if "1800" in service.uuid.lower():
                    print(f"Found Generic Access service: {service.uuid}")
                if "1801" in service.uuid.lower():
                    print(f"Found Generic Attribute service: {service.uuid}")
                if "180f" in service.uuid.lower():
                    print(f"Found Battery service: {service.uuid}")
    except Exception as e:
        print(f"Connection failed: {e}")

async def main():
    """Main function"""
    print("=== WT901BLE68 Service Discovery ===")
    print("This will help identify the correct BLE service and characteristic UUIDs")
    await discover_services()

if __name__ == "__main__":
    asyncio.run(main()) 