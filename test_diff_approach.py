#!/usr/bin/env python3
"""
NTAG213 write without IRQ, using manual polling, with retries and LED feedback
"""

import RPi.GPIO as GPIO
import time
from pirc522 import RFID

# Configuration
LED_PIN = 18


# Initialize RFID reader without IRQ
rdr = RFID(pin_irq=None)
GPIO.setmode(GPIO.BCM)
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


def write_ntag213(tag_data, max_retries=3):
    """Write string to NTAG213 starting at page 4"""
    data_bytes = [ord(c) for c in tag_data]
    pages = [data_bytes[i : i + 4] for i in range(0, len(data_bytes), 4)]
    for i in range(len(pages)):
        if len(pages[i]) < 4:
            pages[i] += [0x00] * (4 - len(pages[i]))

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Write Attempt {attempt}/{max_retries} ---")
        print("Place NTAG213 near the reader...")
        uid = poll_for_tag()
        print("Tag UID:", uid)

        success = True
        # Write each page
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

        # Verification
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
