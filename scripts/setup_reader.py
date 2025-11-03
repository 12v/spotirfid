#!/usr/bin/env python3
"""
Configure a new reader in Cloudflare Workers KV.
Requires wrangler CLI to be installed and authenticated.
"""

import json
import subprocess
import sys


def main():
    print("SpotiRFID Reader Setup")
    print("=" * 50)

    reader_id = input("Reader ID (from generate_reader_id.py): ").strip()
    if not reader_id:
        print("Error: Reader ID is required")
        sys.exit(1)

    refresh_token = input("Spotify Refresh Token: ").strip()
    if not refresh_token:
        print("Error: Refresh Token is required")
        sys.exit(1)

    target_device = input("Target Spotify Device Name: ").strip()
    if not target_device:
        print("Error: Target Device is required")
        sys.exit(1)

    reader_name = input("Reader Name (optional, e.g., 'Bedroom Pi'): ").strip()

    config = {
        "refreshToken": refresh_token,
        "targetDevice": target_device
    }

    if reader_name:
        config["name"] = reader_name

    config_json = json.dumps(config)

    print("\nConfiguration:")
    print(json.dumps(config, indent=2))
    print(f"\nReader ID: {reader_id}")

    confirm = input("\nUpload to Workers KV? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Aborted")
        sys.exit(0)

    cmd = [
        "npx",
        "wrangler",
        "kv:key",
        "put",
        "--binding",
        "READER_CONFIG",
        reader_id,
        config_json
    ]

    result = subprocess.run(cmd, cwd="worker", capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)

    print("\n✓ Reader configured successfully!")
    print("\nNext steps:")
    print("1. Add to your Pi's .env file:")
    print(f"   READER_ID={reader_id}")
    print("2. Run script.py on your Pi")


if __name__ == "__main__":
    main()
