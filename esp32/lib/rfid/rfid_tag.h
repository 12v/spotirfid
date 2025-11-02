#ifndef RFID_TAG_H
#define RFID_TAG_H

#include <Arduino.h>
#include <MFRC522.h>
#include <ArduinoJson.h>

struct RFIDPins
{
    int rst;
    int ss;
    int sck;
    int mosi;
    int miso;
};

struct CardData
{
    String id;
    String text;
};

bool parseRFIDConfig(JsonObject rfidConfig, RFIDPins &pins);
MFRC522* createAndInitRFID(MFRC522::MIFARE_Key *key, const RFIDPins &pins);
bool readCard(MFRC522 *rfid, MFRC522::MIFARE_Key *key, CardData &card);
bool readCardKeepActive(MFRC522 *rfid, MFRC522::MIFARE_Key *key, CardData &card);
bool writeTagText(MFRC522 *rfid, MFRC522::MIFARE_Key *key, const String &text);
void waitForCardRemoval(MFRC522 *rfid);

#endif
