#!/usr/bin/env python3
"""
Simple test script to write and read tag data with reset and diagnostics.
"""

from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import time

reader = SimpleMFRC522()
LED_PIN = 18
GPIO.setup(LED_PIN, GPIO.OUT)

try:
    test_data = "spotify:album:test123"

    print("Waiting for tag...")
    id, text = reader.read()
    print(f"Tag ID: {id}")
    print(f"Current text: '{text}'")

    # Wait a bit for reader to settle
    time.sleep(1)

    print(f"\nWriting: '{test_data}'")
    reader.write(test_data)
    print("Write command sent")

    # Wait longer before reading back
    time.sleep(2)

    print("Reading back...")
    id, text = reader.read()
    print(f"Tag ID: {id}")
    print(f"Read text: '{text}'")

    text_stripped = text.strip() if isinstance(text, str) else text
    if text_stripped == test_data:
        print("✓ SUCCESS: Data matches!")
        GPIO.output(LED_PIN, GPIO.HIGH)
    else:
        print(f"✗ FAILED: Expected '{test_data}', got '{text_stripped}'")
        print(f"  Length: {len(text_stripped)}")
        print(f"  Repr: {repr(text_stripped)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        reader.cleanup()
    except Exception:
        pass
    GPIO.cleanup()
