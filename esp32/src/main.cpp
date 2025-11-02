#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include <MFRC522.h>
#include "rfid_tag.h"

// ===== STRUCTS =====
struct Config
{
    String wifi_ssid;
    String wifi_pass;
    String worker_url;
    String reader_id;
    String master_tag_id;
    int led_pin;
};

Config config;
RFIDPins rfidPins;
MFRC522 *rfid = nullptr;
MFRC522::MIFARE_Key key;
bool writeMode = false;

// ===== LOAD CONFIG =====
bool loadConfig()
{
    if (!SPIFFS.begin(true))
    {
        Serial.println("SPIFFS mount failed!");
        return false;
    }

    File file = SPIFFS.open("/config.json");
    if (!file)
    {
        Serial.println("Failed to open config.json");
        return false;
    }

    StaticJsonDocument<1024> doc;
    DeserializationError err = deserializeJson(doc, file);
    if (err)
    {
        Serial.print("JSON parse error: ");
        Serial.println(err.f_str());
        file.close();
        return false;
    }
    file.close();

    config.wifi_ssid = doc["wifi"]["ssid"].as<String>();
    config.wifi_pass = doc["wifi"]["password"].as<String>();
    config.worker_url = doc["worker"]["url"].as<String>();
    config.reader_id = doc["worker"]["readerId"].as<String>();
    config.master_tag_id = doc["masterTagId"].as<String>();
    config.led_pin = doc["ledPin"].as<int>();

    if (!parseRFIDConfig(doc["rfid"], rfidPins))
    {
        Serial.println("Failed to parse RFID config");
        file.close();
        return false;
    }

    Serial.println("Loaded config:");
    Serial.println("  WiFi SSID: " + config.wifi_ssid);
    Serial.println("  Worker URL: " + config.worker_url);
    Serial.println("  Reader ID: " + config.reader_id);
    return true;
}

// ===== HELPERS =====
void flashLED(int times, int delayMs)
{
    for (int i = 0; i < times; i++)
    {
        digitalWrite(config.led_pin, HIGH);
        delay(delayMs);
        digitalWrite(config.led_pin, LOW);
        delay(delayMs);
    }
}

void connectWiFi()
{
    WiFi.begin(config.wifi_ssid.c_str(), config.wifi_pass.c_str());
    Serial.print("Connecting to Wi-Fi");
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
        if (++retries > 40)
        {
            Serial.println("\nWi-Fi failed!");
            return;
        }
    }
    Serial.println("\nConnected!");
    Serial.println(WiFi.localIP());
}


void callWorker(String tagId, bool isWriteMode)
{
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("No Wi-Fi, skipping worker call.");
        return;
    }

    HTTPClient http;
    http.begin(config.worker_url);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> body;
    body["readerId"] = config.reader_id;
    body["tagId"] = tagId;
    body["isWriteMode"] = isWriteMode;

    String json;
    serializeJson(body, json);
    Serial.println("POST: " + json);

    int code = http.POST(json);
    if (code > 0)
    {
        String resp = http.getString();
        Serial.printf("Response [%d]: %s\n", code, resp.c_str());
        if (code == 200)
            flashLED(2, 100);
    }
    else
    {
        Serial.printf("HTTP error: %s\n", http.errorToString(code).c_str());
    }
    http.end();
}

// ===== SETUP =====
void setup()
{
    Serial.begin(115200);

    if (!loadConfig())
    {
        Serial.println("Failed to load config!");
        abort();
    }

    pinMode(config.led_pin, OUTPUT);

    connectWiFi();

    rfid = createAndInitRFID(&key, rfidPins);

    Serial.println("RFID -> Cloudflare Worker ready.");
}

// ===== MAIN LOOP =====
void loop()
{
    CardData card;
    if (!readCard(rfid, &key, card))
    {
        delay(50);
        return;
    }

    if (card.text == config.master_tag_id)
    {
        Serial.println("Master tag detected -> write mode");
        writeMode = true;
        digitalWrite(config.led_pin, HIGH);
    }
    else
    {
        digitalWrite(config.led_pin, LOW);
        callWorker(card.id, writeMode);
        writeMode = false;
    }

    delay(1000);
}
