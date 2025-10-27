#!/usr/bin/env python3
"""
Detailed write test with exception handling and retries.
"""

from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import time

reader = SimpleMFRC522()
LED_PIN = 18
GPIO.setup(LED_PIN, GPIO.OUT)

try:
    test_data = "TEST_DATA"
    max_retries = 3

    print("Place tag on reader...")
    id, text = reader.read()
    print(f"Tag ID: {id}")
    print(f"Initial text: '{text}'")

    # Try writing multiple times
    for attempt in range(max_retries):
        print(f"\n--- Write Attempt {attempt + 1}/{max_retries} ---")
        try:
            print(f"Writing: '{test_data}'")
            result = reader.write(test_data)
            print(f"Write returned: {result}")
            print("Write succeeded (no exception)")

            # Immediate read without delay
            print("Reading immediately...")
            id, text = reader.read()
            print(f"Read: '{text}'")

            if text.strip() == test_data:
                print("✓ SUCCESS on attempt", attempt + 1)
                GPIO.output(LED_PIN, GPIO.HIGH)
                break
            else:
                print(f"✗ Verification failed, got: '{text}'")
                time.sleep(1)

        except Exception as e:
            print(f"✗ Exception on write: {type(e).__name__}: {e}")
            time.sleep(1)

except Exception as e:
    print(f"Fatal error: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        reader.cleanup()
    except Exception:
        pass
    GPIO.cleanup()
