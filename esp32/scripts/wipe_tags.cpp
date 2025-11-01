#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 9
#define SS_PIN 10
#define SCK_PIN 8
#define MOSI_PIN 7
#define MISO_PIN 6
#define LED_PIN 2

MFRC522 rfid(SS_PIN, RST_PIN);
MFRC522::MIFARE_Key key;

String uidToString(MFRC522::Uid *uid) {
    String s = "";
    for (byte i = 0; i < uid->size; i++) {
        s += String(uid->uidByte[i] < 0x10 ? "0" : "");
        s += String(uid->uidByte[i], HEX);
    }
    s.toUpperCase();
    return s;
}

void wipeTag() {
    String uid = uidToString(&rfid.uid);
    Serial.println("\n=== WIPING TAG ===");
    Serial.println("UID: " + uid);

    MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
    Serial.print("Card type: ");
    Serial.println(rfid.PICC_GetTypeName(piccType));

    // MIFARE Ultralight/NTAG - wipe pages 4-7 (16 bytes)
    if (piccType == MFRC522::PICC_TYPE_MIFARE_UL) {
        byte page = 4;
        byte buffer[4] = {0, 0, 0, 0};

        for (byte p = 0; p < 4; p++) {
            MFRC522::StatusCode status = rfid.MIFARE_Ultralight_Write(page + p, buffer, 4);
            if (status != MFRC522::STATUS_OK) {
                Serial.println("Wipe failed at page " + String(page + p) + ": " + String(rfid.GetStatusCodeName(status)));
                return;
            }
        }

        Serial.println("Wipe successful!");
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        delay(100);
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        return;
    }

    // MIFARE Classic - wipe block 4
    if (piccType == MFRC522::PICC_TYPE_MIFARE_MINI ||
        piccType == MFRC522::PICC_TYPE_MIFARE_1K ||
        piccType == MFRC522::PICC_TYPE_MIFARE_4K) {

        byte block = 4;
        byte buffer[16] = {0};

        MFRC522::StatusCode status = rfid.PCD_Authenticate(
            MFRC522::PICC_CMD_MF_AUTH_KEY_A,
            block,
            &key,
            &rfid.uid
        );

        if (status != MFRC522::STATUS_OK) {
            Serial.println("Auth failed: " + String(rfid.GetStatusCodeName(status)));
            return;
        }

        status = rfid.MIFARE_Write(block, buffer, 16);
        if (status != MFRC522::STATUS_OK) {
            Serial.println("Wipe failed: " + String(rfid.GetStatusCodeName(status)));
            return;
        }

        Serial.println("Wipe successful!");
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        delay(100);
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        return;
    }

    Serial.println("Unsupported card type for wiping");
}

void readTag() {
    String uid = uidToString(&rfid.uid);
    Serial.println("\n=== TAG DETECTED ===");
    Serial.println("UID: " + uid);

    MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
    Serial.print("Card type: ");
    Serial.println(rfid.PICC_GetTypeName(piccType));

    // MIFARE Ultralight/NTAG
    if (piccType == MFRC522::PICC_TYPE_MIFARE_UL) {
        byte page = 4;
        byte buffer[18];
        byte size = sizeof(buffer);

        MFRC522::StatusCode status = rfid.MIFARE_Read(page, buffer, &size);
        if (status != MFRC522::STATUS_OK) {
            Serial.println("Read failed: " + String(rfid.GetStatusCodeName(status)));
            return;
        }

        Serial.print("Data (Page 4-7): ");
        String data = "";
        for (byte i = 0; i < 16; i++) {
            if (buffer[i] >= 32 && buffer[i] <= 126) {
                data += (char)buffer[i];
            }
        }

        if (data.length() > 0) {
            Serial.println(data);
        } else {
            Serial.println("(empty)");
        }
        return;
    }

    // MIFARE Classic
    if (piccType == MFRC522::PICC_TYPE_MIFARE_MINI ||
        piccType == MFRC522::PICC_TYPE_MIFARE_1K ||
        piccType == MFRC522::PICC_TYPE_MIFARE_4K) {

        byte block = 4;
        byte buffer[18];
        byte size = sizeof(buffer);

        MFRC522::StatusCode status = rfid.PCD_Authenticate(
            MFRC522::PICC_CMD_MF_AUTH_KEY_A,
            block,
            &key,
            &rfid.uid
        );

        if (status != MFRC522::STATUS_OK) {
            Serial.println("Auth failed: " + String(rfid.GetStatusCodeName(status)));
            return;
        }

        status = rfid.MIFARE_Read(block, buffer, &size);
        if (status != MFRC522::STATUS_OK) {
            Serial.println("Read failed: " + String(rfid.GetStatusCodeName(status)));
            return;
        }

        Serial.print("Data (Block 4): ");
        String data = "";
        for (byte i = 0; i < 16; i++) {
            if (buffer[i] >= 32 && buffer[i] <= 126) {
                data += (char)buffer[i];
            }
        }

        if (data.length() > 0) {
            Serial.println(data);
        } else {
            Serial.println("(empty)");
        }
        return;
    }

    Serial.println("Unsupported card type");
}

void setup() {
    Serial.begin(115200);
    while (!Serial) {
        delay(10);
    }
    delay(1000);

    pinMode(LED_PIN, OUTPUT);

    SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);
    rfid.PCD_Init();

    for (byte i = 0; i < 6; i++) {
        key.keyByte[i] = 0xFF;
    }

    Serial.println("\n\n=== RFID Tag Wiper ===");
    Serial.println("Scan a tag to:");
    Serial.println("1. Read its current data");
    Serial.println("2. Wipe all data (fill with zeros)");
    Serial.println("3. Read it back to verify");
    Serial.println("\nWaiting for tag...");
}

void loop() {
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        delay(50);
        return;
    }

    // Step 1: Read before wipe
    Serial.println("\n========== STEP 1: READ BEFORE WIPE ==========");
    readTag();

    delay(500);

    // Step 2: Wipe
    Serial.println("\n========== STEP 2: WIPING TAG ==========");
    wipeTag();

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();

    // Step 3: Verify wipe
    Serial.println("\n========== STEP 3: VERIFICATION READ ==========");
    Serial.println("LIFT the tag, then place it back on the reader...");

    delay(1000);

    while (rfid.PICC_IsNewCardPresent()) {
        delay(100);
    }

    Serial.println("Tag removed. Waiting for tag to be placed back...");

    while (true) {
        if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
            readTag();
            break;
        }
        delay(100);
    }

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();

    Serial.println("\n========================================");
    Serial.println("Wipe complete! Scan another tag to wipe.");
    Serial.println("========================================\n");

    delay(2000);
}
