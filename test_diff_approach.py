#!/usr/bin/env python3
"""
Detailed NTAG213 write test with retries and verification
"""

import RPi.GPIO as GPIO
import time
from mfrc522 import MFRC522

LED_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

reader = MFRC522()


def write_ntag213(tag_data, max_retries=3):
    """
    Write string tag_data to NTAG213 starting at page 4
    """
    # Convert string to list of bytes, pad each 4-byte page
    data_bytes = [ord(c) for c in tag_data]
    pages = [data_bytes[i : i + 4] for i in range(0, len(data_bytes), 4)]
    for i in range(len(pages)):
        if len(pages[i]) < 4:
            pages[i] += [0x00] * (4 - len(pages[i]))  # pad last page

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Write Attempt {attempt}/{max_retries} ---")
        print("Place NTAG213 near the reader...")
        while True:
            (status, TagType) = reader.MFRC522_Request(reader.PICC_REQIDL)
            if status == reader.MI_OK:
                print("Tag detected")
                (status, uid) = reader.MFRC522_Anticoll()
                if status == reader.MI_OK:
                    print("Tag UID:", uid)
                    break
            time.sleep(0.2)

        success = True
        # Write page by page
        for idx, page_data in enumerate(pages):
            page_num = 4 + idx
            print(f"Writing page {page_num}: {page_data}")
            status = reader.MFRC522_Write(page_num, page_data)
            if status != reader.MI_OK:
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
            status, page = reader.MFRC522_Read(page_num)
            if status != reader.MI_OK:
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
