#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from pirc522 import RFID

LED_PIN = 18
rdr = RFID(pin_irq=None)
GPIO.setup(LED_PIN, GPIO.OUT)


def poll_for_tag():
    """Poll continuously until a tag is detected and return its UID"""
    while True:
        error, tag_type = rdr.request()
        if not error:
            error, uid = rdr.anticoll()
            if not error:
                return uid
        time.sleep(0.2)


def dump_tag():
    """Dump all NTAG213 pages and print lock status"""
    print("Place NTAG213 near the reader...")
    uid = poll_for_tag()
    print("Tag UID:", uid)
    print("\n--- Tag Memory Dump ---")

    for page in range(0, 40):
        error, data = rdr.read(page)
        if error:
            print(f"Page {page}: ✗ Failed to read")
            continue

        # NTAG213 lock bytes are on page 2 (bytes 2-3) and page 3 (CC)
        lock_info = ""
        if page == 2:
            lock_info = f" | Lock bytes: {data[2:4]}"
        elif page == 3:
            lock_info = f" | CC bytes: {data}"

        print(f"Page {page:02d}: {data}{lock_info}")


try:
    dump_tag()
finally:
    GPIO.cleanup()
