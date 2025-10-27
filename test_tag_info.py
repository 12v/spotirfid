#!/usr/bin/env python3
"""
Diagnostic script to check tag properties and auth status.
"""

from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import time

reader = SimpleMFRC522()
LED_PIN = 18
GPIO.setup(LED_PIN, GPIO.OUT)

try:
    print("Place tag on reader...")
    id, text = reader.read()

    print(f"\nTag Information:")
    print(f"  ID: {id}")
    print(f"  ID type: {type(id)}")
    print(f"  Current text: '{text}'")
    print(f"  Text length: {len(text)}")
    print(f"  Text type: {type(text)}")
    print(f"  Text repr: {repr(text)}")

    # Try reading multiple times to see if it's consistent
    print("\nReading again...")
    time.sleep(0.5)
    id2, text2 = reader.read()
    print(f"  ID: {id2}")
    print(f"  Text: '{text2}'")
    print(f"  Consistent: {id == id2 and text == text2}")

    # Check if text is truly empty or just whitespace
    if text:
        print(f"\nTag has data: {repr(text)}")
    else:
        print("\nTag appears empty")

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
