#include <Arduino.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include "rfid_tag.h"

MFRC522 *rfid = nullptr;
MFRC522::MIFARE_Key key;
String masterTagId;
bool writeMasterNext = false;

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=== RFID Tag Module Test ===\n");

    if (!SPIFFS.begin(true))
    {
        Serial.println("SPIFFS mount failed!");
        abort();
    }

    File file = SPIFFS.open("/config.json");
    if (!file)
    {
        Serial.println("Failed to open config.json");
        abort();
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, file);
    if (err)
    {
        Serial.println("JSON parse error");
        file.close();
        abort();
    }
    file.close();

    RFIDPins pins;
    if (!parseRFIDConfig(doc["rfid"], pins))
    {
        Serial.println("Failed to parse RFID config");
        abort();
    }

    masterTagId = doc["masterTagId"].as<String>();

    rfid = createAndInitRFID(&key, pins);
    Serial.println("RFID initialized successfully\n");
    Serial.println("Master Tag ID: " + masterTagId);
    Serial.println("\nTest will alternate between:");
    Serial.println("- Writing test data (TEST_xxxx)");
    Serial.println("- Writing master tag ID (" + masterTagId + ")");
    Serial.println("\nReady to scan cards...\n");
}

void loop()
{
    CardData card;
    if (!readCardKeepActive(rfid, &key, card))
    {
        delay(50);
        return;
    }

    Serial.println("\n========== STEP 1: INITIAL READ ==========");
    Serial.println("ID: " + card.id);
    Serial.println("Text: " + (card.text.length() > 0 ? card.text : "(empty)"));

    Serial.println("\n========== STEP 2: WRITING DATA ==========");
    String textToWrite;
    if (writeMasterNext)
    {
        textToWrite = masterTagId;
        Serial.print("Will write MASTER TAG: \"");
        Serial.print(textToWrite);
        Serial.println("\"");
    }
    else
    {
        textToWrite = "TEST_" + String(millis() / 1000);
        Serial.print("Will write TEST DATA: \"");
        Serial.print(textToWrite);
        Serial.println("\"");
    }
    Serial.println("Keep card on reader...\n");

    if (!writeTagText(rfid, &key, textToWrite))
    {
        Serial.println("Write failed!");
        delay(2000);
        return;
    }

    writeMasterNext = !writeMasterNext;

    Serial.println("\n========== STEP 3: VERIFICATION READ ==========");
    Serial.println("Remove and re-present the tag...\n");

    delay(1000);

    waitForCardRemoval(rfid);

    Serial.println("Tag removed. Waiting for tag...");

    while (true)
    {
        if (readCard(rfid, &key, card))
        {
            Serial.println("ID: " + card.id);
            Serial.println("Text: " + (card.text.length() > 0 ? card.text : "(empty)"));

            if (card.text == textToWrite)
            {
                Serial.println("\n*** WRITE VERIFICATION SUCCESS ***");
            }
            else
            {
                Serial.println("\n*** WRITE VERIFICATION FAILED ***");
                Serial.println("Expected: " + textToWrite);
                Serial.println("Got: " + card.text);
            }
            break;
        }
        delay(100);
    }

    Serial.println("\n========================================");
    Serial.println("Test complete! Scan another tag.");
    Serial.println("========================================\n");

    delay(2000);
}
