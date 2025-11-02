#include "rfid_tag.h"
#include <SPI.h>

bool parseRFIDConfig(JsonObject rfidConfig, RFIDPins &pins)
{
    if (!rfidConfig)
    {
        return false;
    }

    pins.rst = rfidConfig["rst"].as<int>();
    pins.ss = rfidConfig["ss"].as<int>();
    pins.sck = rfidConfig["sck"].as<int>();
    pins.mosi = rfidConfig["mosi"].as<int>();
    pins.miso = rfidConfig["miso"].as<int>();

    return true;
}

MFRC522* createAndInitRFID(MFRC522::MIFARE_Key *key, const RFIDPins &pins)
{
    Serial.printf("Initializing RFID (SS=%d, RST=%d, SCK=%d, MOSI=%d, MISO=%d)\n",
                  pins.ss, pins.rst, pins.sck, pins.mosi, pins.miso);

    SPI.begin(pins.sck, pins.miso, pins.mosi, pins.ss);

    MFRC522 *rfid = new MFRC522(pins.ss, pins.rst);
    rfid->PCD_Init();

    for (byte i = 0; i < 6; i++)
    {
        key->keyByte[i] = 0xFF;
    }

    return rfid;
}

void releaseCard(MFRC522 *rfid)
{
    rfid->PICC_HaltA();
    rfid->PCD_StopCrypto1();
    delay(50); // Give card time to reset after halt
}

void waitForCardRemoval(MFRC522 *rfid)
{
    int attempts = 0;
    while (rfid->PICC_IsNewCardPresent())
    {
        delay(100);
        attempts++;
        if (attempts > 50) // 5 seconds timeout
        {
            Serial.println("Warning: Card still appears present after 5 seconds, forcing continue");
            break;
        }
    }
    if (attempts < 50)
    {
        Serial.println("Card removal detected");
    }
}

String readTagText(MFRC522 *rfid, MFRC522::MIFARE_Key *key)
{
    MFRC522::PICC_Type piccType = rfid->PICC_GetType(rfid->uid.sak);

    // MIFARE Ultralight/NTAG - Read 48 bytes (pages 4-15)
    if (piccType == MFRC522::PICC_TYPE_MIFARE_UL)
    {
        String data = "";

        // Read 12 pages (4 bytes each = 48 bytes total)
        // MIFARE_Read returns 4 pages at a time
        for (byte startPage = 4; startPage < 16; startPage += 4)
        {
            byte buffer[18];
            byte size = sizeof(buffer);

            MFRC522::StatusCode status = rfid->MIFARE_Read(startPage, buffer, &size);
            if (status != MFRC522::STATUS_OK)
            {
                return data; // Return what we've read so far
            }

            // Process 16 bytes (4 pages worth)
            for (byte i = 0; i < 16; i++)
            {
                if (buffer[i] == 0)
                {
                    return data; // Null terminator found
                }
                if (buffer[i] >= 32 && buffer[i] <= 126)
                {
                    data += (char)buffer[i];
                }
            }
        }
        return data;
    }

    // MIFARE Classic - Read 48 bytes (blocks 4-6)
    // Sector 1 has blocks 4-7, but block 7 is sector trailer (auth keys), so use 4-6
    if (piccType == MFRC522::PICC_TYPE_MIFARE_MINI ||
        piccType == MFRC522::PICC_TYPE_MIFARE_1K ||
        piccType == MFRC522::PICC_TYPE_MIFARE_4K)
    {
        String data = "";

        // Read blocks 4, 5, 6 (16 bytes each = 48 bytes total)
        for (byte block = 4; block <= 6; block++)
        {
            byte buffer[18];
            byte size = sizeof(buffer);

            MFRC522::StatusCode status = rfid->PCD_Authenticate(
                MFRC522::PICC_CMD_MF_AUTH_KEY_A,
                block,
                key,
                &rfid->uid);

            if (status != MFRC522::STATUS_OK)
            {
                return data; // Return what we've read so far
            }

            status = rfid->MIFARE_Read(block, buffer, &size);
            if (status != MFRC522::STATUS_OK)
            {
                return data; // Return what we've read so far
            }

            // Process 16 bytes
            for (byte i = 0; i < 16; i++)
            {
                if (buffer[i] == 0)
                {
                    return data; // Null terminator found
                }
                if (buffer[i] >= 32 && buffer[i] <= 126)
                {
                    data += (char)buffer[i];
                }
            }
        }
        return data;
    }

    return "";
}

bool readCardKeepActive(MFRC522 *rfid, MFRC522::MIFARE_Key *key, CardData &card)
{
    if (!rfid->PICC_IsNewCardPresent() || !rfid->PICC_ReadCardSerial())
    {
        return false;
    }

    card.id = "";
    for (byte i = 0; i < rfid->uid.size; i++)
    {
        card.id += String(rfid->uid.uidByte[i] < 0x10 ? "0" : "");
        card.id += String(rfid->uid.uidByte[i], HEX);
    }
    card.id.toUpperCase();

    Serial.println("Tag detected: " + card.id);

    card.text = readTagText(rfid, key);
    if (card.text.length() > 0)
    {
        Serial.println("Tag text: " + card.text);
    }

    return true;
}

bool readCard(MFRC522 *rfid, MFRC522::MIFARE_Key *key, CardData &card)
{
    bool result = readCardKeepActive(rfid, key, card);
    if (result)
    {
        releaseCard(rfid);
    }
    return result;
}

bool writeTagText(MFRC522 *rfid, MFRC522::MIFARE_Key *key, const String &text)
{
    MFRC522::PICC_Type piccType = rfid->PICC_GetType(rfid->uid.sak);
    Serial.print("Card type: ");
    Serial.println(rfid->PICC_GetTypeName(piccType));
    Serial.print("About to write: \"");
    Serial.print(text);
    Serial.println("\"");

    byte buffer[48] = {0}; // Increased to 48 bytes
    byte len = text.length() > 48 ? 48 : text.length();
    for (byte i = 0; i < len; i++)
    {
        buffer[i] = text[i];
    }

    // MIFARE Ultralight/NTAG - Write 48 bytes (pages 4-15)
    if (piccType == MFRC522::PICC_TYPE_MIFARE_UL)
    {
        Serial.print("Writing ");
        Serial.print(len);
        Serial.println(" bytes to Ultralight card (pages 4-15)");

        // Write 12 pages (4 bytes each = 48 bytes total)
        for (byte p = 0; p < 12; p++)
        {
            byte page = 4 + p;
            Serial.print("Writing page ");
            Serial.print(page);
            Serial.print(" with data: ");
            for (byte i = 0; i < 4; i++)
            {
                Serial.print(buffer[(p * 4) + i] < 0x10 ? "0" : "");
                Serial.print(buffer[(p * 4) + i], HEX);
                Serial.print(" ");
            }
            Serial.println();

            MFRC522::StatusCode status = rfid->MIFARE_Ultralight_Write(page, buffer + (p * 4), 4);
            if (status != MFRC522::STATUS_OK)
            {
                Serial.print("Write failed at page ");
                Serial.print(page);
                Serial.print(": ");
                Serial.println(rfid->GetStatusCodeName(status));
                releaseCard(rfid);
                return false;
            }
            Serial.print("Page ");
            Serial.print(page);
            Serial.println(" written successfully");
        }
        Serial.println("Write successful");
        releaseCard(rfid);
        delay(200); // Give Ultralight card time to reset after release
        return true;
    }

    // MIFARE Classic - Write 48 bytes (blocks 4-6)
    if (piccType == MFRC522::PICC_TYPE_MIFARE_MINI ||
        piccType == MFRC522::PICC_TYPE_MIFARE_1K ||
        piccType == MFRC522::PICC_TYPE_MIFARE_4K)
    {
        Serial.print("Writing ");
        Serial.print(len);
        Serial.println(" bytes to Classic card (blocks 4-6)");

        // Write blocks 4, 5, 6 (16 bytes each = 48 bytes total)
        for (byte b = 0; b < 3; b++)
        {
            byte block = 4 + b;

            MFRC522::StatusCode status = rfid->PCD_Authenticate(
                MFRC522::PICC_CMD_MF_AUTH_KEY_A,
                block,
                key,
                &rfid->uid);

            if (status != MFRC522::STATUS_OK)
            {
                Serial.print("Auth failed for block ");
                Serial.println(block);
                releaseCard(rfid);
                return false;
            }

            status = rfid->MIFARE_Write(block, buffer + (b * 16), 16);
            if (status != MFRC522::STATUS_OK)
            {
                Serial.print("Write failed at block ");
                Serial.println(block);
                releaseCard(rfid);
                return false;
            }

            Serial.print("Block ");
            Serial.print(block);
            Serial.println(" written successfully");
        }

        Serial.println("Write successful");
        releaseCard(rfid);
        return true;
    }

    Serial.println("Unsupported card type for writing");
    releaseCard(rfid);
    return false;
}

String uidToString(MFRC522::Uid *uid)
{
    String s = "";
    for (byte i = 0; i < uid->size; i++)
    {
        s += String(uid->uidByte[i] < 0x10 ? "0" : "");
        s += String(uid->uidByte[i], HEX);
    }
    s.toUpperCase();
    return s;
}
