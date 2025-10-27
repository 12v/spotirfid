#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from pirc522 import RFID

LED_PIN = 18
rdr = RFID(pin_irq=None)
GPIO.setup(LED_PIN, GPIO.OUT)


def poll_for_tag():
    """Wait for tag and return UID"""
    while True:
        error, tag_type = rdr.request()
        if not error:
            error, uid = rdr.anticoll()
            if not error:
                return uid
        time.sleep(0.2)


def write_pages_one_by_one(test_data="TEST"):
    """Attempt to write to each page until a write succeeds"""
    data_bytes = [ord(c) for c in test_data]
    if len(data_bytes) < 4:
        data_bytes += [0x00] * (4 - len(data_bytes))
    elif len(data_bytes) > 4:
        data_bytes = data_bytes[:4]

    print("Place NTAG213 near the reader...")
    uid = poll_for_tag()
    print("Tag UID:", uid)

    # NTAG213 user memory pages 4–39
    for page in range(4, 40):
        print(f"\nAttempting to write to page {page}: {data_bytes}")
        error = rdr.write(page, data_bytes)
        if error:
            print(f"✗ Failed to write page {page}")
            continue

        # Verification
        error, read_back = rdr.read(page)
        if error:
            print(f"✗ Failed to read back page {page}")
            continue

        if read_back[: len(data_bytes)] == data_bytes:
            print(f"✓ Success writing page {page}")
            GPIO.output(LED_PIN, GPIO.HIGH)
            return page
        else:
            print(f"✗ Verification failed on page {page}")

    print("✗ Could not write to any page")
    return None


try:
    write_pages_one_by_one("ABCD")  # example test data
finally:
    GPIO.cleanup()
