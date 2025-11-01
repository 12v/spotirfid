#!/usr/bin/env python3

import time
import requests
from mfrc522 import SimpleMFRC522
import sys
import os
from dotenv import load_dotenv
import RPi.GPIO as GPIO

sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

WORKER_URL = os.getenv("WORKER_URL")
READER_ID = os.getenv("READER_ID")

if not WORKER_URL or not READER_ID:
    print("ERROR: WORKER_URL and READER_ID must be set in .env")
    sys.exit(1)

MASTER_TAG_ID = "MASTER_TAG"
LED_PIN = 18

reader = SimpleMFRC522()
GPIO.setup(LED_PIN, GPIO.OUT)


def flash_led(times, delay):
    """Flash LED feedback."""
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(delay)


def call_worker(tag_id, is_write_mode):
    """Call Cloudflare Worker with tag info."""
    try:
        response = requests.post(
            f"{WORKER_URL}/api/scan",
            json={"readerId": READER_ID, "tagId": tag_id, "isWriteMode": is_write_mode},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Worker call failed: {e}")
        return {"success": False, "action": "error", "message": str(e)}


def main_loop():
    print("Starting RFID -> Spotify bridge (Worker mode)")
    write_mode = False

    try:
        while True:
            print("Ready to scan, write_mode =", write_mode)
            tag_id, text = reader.read()
            uid_str = str(tag_id)
            print(f"Tag: {uid_str}, text: {text}")

            if text == MASTER_TAG_ID:
                print("Master tag - entering write mode")
                write_mode = True
                GPIO.output(LED_PIN, GPIO.HIGH)
            else:
                GPIO.output(LED_PIN, GPIO.LOW)
                result = call_worker(uid_str, write_mode)
                print(f"Result: {result['message']}")
                write_mode = False
                if result["success"]:
                    flash_led(2, 0.1)

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("Exiting")
    finally:
        reader.cleanup()


if __name__ == "__main__":
    main_loop()
