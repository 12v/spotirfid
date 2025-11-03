#!/usr/bin/env python3
"""
One-time script to write the master tag identifier.
Run this once to program a tag as the master tag.
"""

from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
import time

MASTER_IDENTIFIER = "MASTER_TAG"
LED_PIN = 18

reader = SimpleMFRC522()
GPIO.setup(LED_PIN, GPIO.OUT)


def flash_led(times=1, delay=0.2):
    """Flash LED a certain number of times."""
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(delay)


try:
    print("Place master tag on reader...")
    id, text = reader.read()

    print(f"Writing '{MASTER_IDENTIFIER}' to tag {id}...")
    reader.write(MASTER_IDENTIFIER)

    print("✓ Master tag written successfully")
    flash_led(3, 0.1)

except Exception as e:
    print(f"Error: {e}")
finally:
    try:
        reader.cleanup()
    except Exception:
        pass
    GPIO.cleanup()
