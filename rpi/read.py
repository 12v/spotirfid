#!/usr/bin/env python3

from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

reader = SimpleMFRC522()

print("Hold an RFID tag near the reader...")

try:
    while True:
        id, text = reader.read()
        print(f"Tag UID: {id}")
        if text:
            print(f"Tag Text: {text}")
        print("--- Place another tag ---\n")

except KeyboardInterrupt:
    print("Exiting...")

finally:
    reader.cleanup()
    GPIO.cleanup()
