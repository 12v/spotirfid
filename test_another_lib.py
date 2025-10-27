from pirc522 import RFID
import time
import RPi.GPIO as GPIO

rdr = RFID()
led_pin = 18
GPIO.setup(led_pin, GPIO.OUT)

try:
    print("Place tag near reader")
    rdr.wait_for_tag()
    (error, data) = rdr.request()
    if not error:
        (error, uid) = rdr.anticoll()
        if not error:
            print("Tag UID:", uid)
            # Start writing user data (page 4 onwards)
            user_data = [ord(c) for c in "TEST_DATA"]
            pages = [user_data[i : i + 4] for i in range(0, len(user_data), 4)]
            for i, page in enumerate(pages):
                if len(page) < 4:
                    page += [0x00] * (4 - len(page))
                rdr.write(4 + i, page)
            print("Write complete")
            GPIO.output(led_pin, GPIO.HIGH)
finally:
    GPIO.cleanup()
