#!/usr/bin/env python3
"""
NTAG213 write with retries, verification, and LED feedback
Using pi-rc522 without IRQ pin (polling mode)
"""

import RPi.GPIO as GPIO
import time
from pirc522 import RFID

# Configuration
LED_PIN = 18
GPIO.setup(LED_PIN, GPIO.OUT)

# Initialize RFID reader without IRQ pin
rdr = RFID(pin_irq=None)


def write_ntag213(tag_data, max_retries=3):
    """
    Write a string to NTAG213 starting at page 4
    """
    # Convert string to bytes and split into 4-byte pages
    data_bytes = [ord(c) for c in tag_data]
    pages = [data_bytes[i : i + 4] for i in range(0, len(data_bytes), 4)]
    for i in range(len(pages)):
        if len(pages[i]) < 4:
            pages[i] += [0x00] * (4 - len(pages[i]))  # pad last page

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Write Attempt {attempt}/{max_retries} ---")
        print("Place NTAG213 near the reader...")

        # Poll until a tag is detected
        while True:
            rdr.wait_for_tag()
            (error, tag_type) = rdr.request()
            if not error:
                (error, uid) = rdr.anticoll()
                if not error:
                    print("Tag UID:", uid)
                    break
            time.sleep(0.2)

        success = True

        # Write page-by-page
        for idx, page_data in enumerate(pages):
            page_num = 4 + idx
            print(f"Writing page {page_num}: {page_data}")
            error = rdr.write(page_num, page_data)
            if error:
                print(f"✗ Failed writing page {page_num}")
                success = False
                break
            time.sleep(0.05)

        if not success:
            print("Retrying...")
            continue

        # Verification: read back each page
        read_back = []
        for idx in range(len(pages)):
            page_num = 4 + idx
            error, page = rdr.read(page_num)
            if error:
                print(f"✗ Failed reading page {page_num}")
                success = False
                break
            read_back.extend(page)

        read_text = "".join([chr(b) for b in read_back]).rstrip("\x00")
        print("Read back:", read_text)

        if read_text == tag_data:
            print("✓ SUCCESS: Data verified")
            GPIO.output(LED_PIN, GPIO.HIGH)
            return True
        else:
            print("✗ Verification failed, retrying...")
            time.sleep(1)

    print("✗ All attempts failed")
    return False


try:
    write_ntag213("TEST_DATA")
finally:
    GPIO.cleanup()
