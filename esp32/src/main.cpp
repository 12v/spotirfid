#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include <MFRC522.h>

// ===== STRUCTS =====
struct Config
{
    String wifi_ssid;
    String wifi_pass;
    String worker_url;
    String reader_id;
    String master_tag_id;
    int led_pin;
    int rst_pin, ss_pin, sck_pin, mosi_pin, miso_pin;
};

Config config;
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
    config.rst_pin = doc["rfid"]["rst"].as<int>();
    config.ss_pin = doc["rfid"]["ss"].as<int>();
    config.sck_pin = doc["rfid"]["sck"].as<int>();
    config.mosi_pin = doc["rfid"]["mosi"].as<int>();
    config.miso_pin = doc["rfid"]["miso"].as<int>();

    Serial.println("Loaded config:");
    Serial.println("  WiFi SSID: " + config.wifi_ssid);
    Serial.println("  Worker URL: " + config.worker_url);
    Serial.println("  Reader ID: " + config.reader_id);
    Serial.printf("  RFID pins: SS=%d, RST=%d\n", config.ss_pin, config.rst_pin);
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

String readTagText()
{
    MFRC522::PICC_Type piccType = rfid->PICC_GetType(rfid->uid.sak);

    // MIFARE Ultralight/NTAG
    if (piccType == MFRC522::PICC_TYPE_MIFARE_UL)
    {
        byte page = 4;
        byte buffer[18];
        byte size = sizeof(buffer);

        MFRC522::StatusCode status = rfid->MIFARE_Read(page, buffer, &size);
        if (status != MFRC522::STATUS_OK)
        {
            return "";
        }

        String data = "";
        for (byte i = 0; i < 16; i++)
        {
            if (buffer[i] >= 32 && buffer[i] <= 126)
            {
                data += (char)buffer[i];
            }
            else if (buffer[i] == 0)
            {
                break;
            }
        }
        return data;
    }

    // MIFARE Classic
    if (piccType == MFRC522::PICC_TYPE_MIFARE_MINI ||
        piccType == MFRC522::PICC_TYPE_MIFARE_1K ||
        piccType == MFRC522::PICC_TYPE_MIFARE_4K)
    {
        byte block = 4;
        byte buffer[18];
        byte size = sizeof(buffer);

        MFRC522::StatusCode status = rfid->PCD_Authenticate(
            MFRC522::PICC_CMD_MF_AUTH_KEY_A,
            block,
            &key,
            &rfid->uid);

        if (status != MFRC522::STATUS_OK)
        {
            return "";
        }

        status = rfid->MIFARE_Read(block, buffer, &size);
        if (status != MFRC522::STATUS_OK)
        {
            return "";
        }

        String data = "";
        for (byte i = 0; i < 16; i++)
        {
            if (buffer[i] >= 32 && buffer[i] <= 126)
            {
                data += (char)buffer[i];
            }
            else if (buffer[i] == 0)
            {
                break;
            }
        }
        return data;
    }

    return "";
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
        Serial.println("Using defaults or check SPIFFS upload.");
    }

    pinMode(config.led_pin, OUTPUT);

    connectWiFi();

    // Setup SPI for RFID
    SPI.begin(config.sck_pin, config.miso_pin, config.mosi_pin, config.ss_pin);
    rfid = new MFRC522(config.ss_pin, config.rst_pin);
    rfid->PCD_Init();

    // Set default MIFARE key
    for (byte i = 0; i < 6; i++)
    {
        key.keyByte[i] = 0xFF;
    }

    Serial.println("RFID -> Cloudflare Worker ready.");
}

// ===== MAIN LOOP =====
void loop()
{
    if (!rfid->PICC_IsNewCardPresent() || !rfid->PICC_ReadCardSerial())
    {
        delay(50);
        return;
    }

    String tagId = uidToString(&rfid->uid);
    Serial.println("Tag detected: " + tagId);

    // Read tag text to check if it's the master tag
    String tagText = readTagText();
    if (tagText.length() > 0)
    {
        Serial.println("Tag text: " + tagText);
    }

    if (tagText == config.master_tag_id)
    {
        Serial.println("Master tag detected -> write mode");
        writeMode = true;
        digitalWrite(config.led_pin, HIGH);
    }
    else
    {
        digitalWrite(config.led_pin, LOW);
        callWorker(tagId, writeMode);
        writeMode = false;
    }

    rfid->PICC_HaltA();
    rfid->PCD_StopCrypto1();
    delay(1000);
}
