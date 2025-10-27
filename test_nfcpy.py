#!/usr/bin/env python3
"""
Test script using nfcpy with MFRC522 SPI reader for NFC 213 tags.
"""

import nfc
from ndef import NdefMessage, TextRecord

def test_write():
    clf = None
    try:
        print("Connecting to MFRC522 reader...")
        clf = nfc.ContactlessFrontend('usb')

        print("Waiting for NFC tag...")
        tag = clf.connect(rdwr={'on-connect': lambda tag: tag})

        if not tag:
            print("No tag detected")
            return

        print(f"\nTag detected:")
        print(f"  Type: {tag.type}")
        print(f"  ID: {tag.identifier.hex()}")

        # Try to write simple text
        test_text = "spotify:album:test123"
        print(f"\nWriting: '{test_text}'")

        # Create NDEF message with text record
        message = NdefMessage(TextRecord(test_text))
        tag.ndef.message = message

        print("✓ Write succeeded")

        # Read back to verify
        print("\nReading back...")
        if tag.ndef.message:
            for record in tag.ndef.message:
                print(f"  Record type: {record.type}")
                if hasattr(record, 'text'):
                    print(f"  Text: '{record.text}'")
        else:
            print("  No NDEF message found")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if clf:
            clf.close()

if __name__ == "__main__":
    test_write()
