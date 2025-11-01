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

void readTag() {
    String uid = uidToString(&rfid.uid);
    Serial.println("\n=== TAG DETECTED ===");
    Serial.println("UID: " + uid);

    // Detect card type
    MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
    Serial.print("Card type: ");
    Serial.println(rfid.PICC_GetTypeName(piccType));

    // MIFARE Ultralight/NTAG - read page 4 (no auth needed)
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
            Serial.println("(empty or binary data)");
            Serial.print("Hex: ");
            for (byte i = 0; i < 16; i++) {
                if (buffer[i] < 0x10) Serial.print("0");
                Serial.print(buffer[i], HEX);
                Serial.print(" ");
            }
            Serial.println();
        }
        return;
    }

    // MIFARE Classic - needs authentication
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
            Serial.println("(Tag may be using non-default keys)");
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
            Serial.println("(empty or binary data)");
            Serial.print("Hex: ");
            for (byte i = 0; i < 16; i++) {
                if (buffer[i] < 0x10) Serial.print("0");
                Serial.print(buffer[i], HEX);
                Serial.print(" ");
            }
            Serial.println();
        }
        return;
    }

    Serial.println("Unsupported card type");
}

void writeTag(String text) {
    String uid = uidToString(&rfid.uid);
    Serial.println("\n=== WRITING TO TAG ===");
    Serial.println("UID: " + uid);
    Serial.println("Text: " + text);

    MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);

    // MIFARE Ultralight/NTAG - write to page 4 (4 bytes per page)
    if (piccType == MFRC522::PICC_TYPE_MIFARE_UL) {
        byte page = 4;
        byte buffer[4];

        // Write up to 16 bytes (4 pages)
        for (byte p = 0; p < 4; p++) {
            for (byte i = 0; i < 4; i++) {
                byte textIndex = (p * 4) + i;
                buffer[i] = (textIndex < text.length()) ? text[textIndex] : 0;
            }

            MFRC522::StatusCode status = rfid.MIFARE_Ultralight_Write(page + p, buffer, 4);
            if (status != MFRC522::STATUS_OK) {
                Serial.println("Write failed at page " + String(page + p) + ": " + String(rfid.GetStatusCodeName(status)));
                return;
            }
        }

        Serial.println("Write successful!");
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        return;
    }

    // MIFARE Classic
    if (piccType == MFRC522::PICC_TYPE_MIFARE_MINI ||
        piccType == MFRC522::PICC_TYPE_MIFARE_1K ||
        piccType == MFRC522::PICC_TYPE_MIFARE_4K) {

        byte block = 4;
        byte buffer[16];

        // Clear buffer and copy text
        for (byte i = 0; i < 16; i++) {
            buffer[i] = 0;
        }
        for (byte i = 0; i < text.length() && i < 16; i++) {
            buffer[i] = text[i];
        }

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
            Serial.println("Write failed: " + String(rfid.GetStatusCodeName(status)));
            return;
        }

        Serial.println("Write successful!");
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        return;
    }

    Serial.println("Unsupported card type for writing");
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

    // Set default key (factory default is FFFFFFFFFFFFh)
    for (byte i = 0; i < 6; i++) {
        key.keyByte[i] = 0xFF;
    }

    Serial.println("\n\n=== RFID Read/Write Test ===");
    Serial.println("Scan a tag to:");
    Serial.println("1. Read its UID and data");
    Serial.println("2. Write 'MASTER_TAG' to it");
    Serial.println("3. Read it back to verify");
    Serial.println("\nWaiting for tag...");
}

void loop() {
    // Check for RFID tag
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        delay(50);
        return;
    }

    // Step 1: Read initial state
    Serial.println("\n========== STEP 1: INITIAL READ ==========");
    readTag();

    delay(500);

    // Step 2: Write MASTER_TAG
    Serial.println("\n========== STEP 2: WRITING 'MASTER_TAG' ==========");
    writeTag("MASTER_TAG");

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();

    // Step 3: Read back to verify
    Serial.println("\n========== STEP 3: VERIFICATION READ ==========");
    Serial.println("LIFT the tag, then place it back on the reader...");

    delay(1000);

    // Wait for card to be removed
    while (rfid.PICC_IsNewCardPresent()) {
        delay(100);
    }

    Serial.println("Tag removed. Waiting for tag to be placed back...");

    // Wait for card to be placed back
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
    Serial.println("Test complete! Scan another tag to test again.");
    Serial.println("========================================\n");

    delay(2000);
}
