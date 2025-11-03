#!/usr/bin/env python3
"""
Generate a high-entropy reader ID for a new SpotiRFID deployment.
"""

import secrets

if __name__ == "__main__":
    reader_id = secrets.token_urlsafe(32)
    print("Generated Reader ID:")
    print(reader_id)
    print("\nAdd this to your Pi's .env file:")
    print(f"READER_ID={reader_id}")
