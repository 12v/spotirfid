#!/usr/bin/env python3
"""
NTAG213 write with lock status debug, automatic writable page detection, retries, and LED feedback
"""

import RPi.GPIO as GPIO
import time
from pirc522 import RFID

# Configuration
LED_PIN = 18
MAX_RETRIES = 3

# Initialize RFID reader without IRQ
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


def debug_lock_status():
    """Read and display pages 2 and 3 to show lock bytes"""
    for page in range(2, 4):
        error, data = rdr.read(page)
        if error:
            print(f"✗ Failed reading page {page}")
            continue
        print(f"Page {page}: {data} | Lock bytes: {data[2:4]}")


def first_writable_page():
    """Find the first writable page on NTAG213 (skip reserved pages 0-3)"""
    for page in range(4, 40):  # NTAG213 user memory ends at page 39
        error, data = rdr.read(page)
        if not error:
            # Skip pages that appear fully locked (heuristic)
            if data != [0x00, 0x00, 0x00, 0x00]:
                return page
    raise RuntimeError("No writable page found")


def write_ntag213(tag_data):
    """Write string to NTAG213 starting at the first writable page"""
    data_bytes = [ord(c) for c in tag_data]
    pages = [data_bytes[i : i + 4] for i in range(0, len(data_bytes), 4)]
    for i in range(len(pages)):
        if len(pages[i]) < 4:
            pages[i] += [0x00] * (4 - len(pages[i]))

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- Write Attempt {attempt}/{MAX_RETRIES} ---")
        print("Place NTAG213 near the reader...")
        uid = poll_for_tag()
        print("Tag UID:", uid)

        # Debug lock status
        debug_lock_status()

        try:
            start_page = first_writable_page()
            print(f"Starting at page {start_page}")
        except RuntimeError as e:
            print("✗", e)
            return False

        success = True
        # Write each page
        for idx, page_data in enumerate(pages):
            page_num = start_page + idx
            print(f"Writing page {page_num}: {page_data}")
            error = rdr.write(page_num, page_data)
            if error:
                print(f"✗ Failed writing page {page_num}")
                success = False
                break
            time.sleep(0.1)

        if not success:
            print("Retrying...")
            time.sleep(1)
            continue

        # Verification
        read_back = []
        for idx in range(len(pages)):
            page_num = start_page + idx
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
