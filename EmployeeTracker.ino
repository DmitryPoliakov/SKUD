#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <time.h>
#include <ArduinoJson.h>

// Wi-Fi настройки
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Google Apps Script URL
const char* googleScriptURL = "YOUR_GOOGLE_SCRIPT_URL";

// OneWire настройки
#define ONE_WIRE_PIN 4
OneWire ds(ONE_WIRE_PIN);

// NTP настройки
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 10800; // GMT+3 (Москва)
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  
  // Подключение к Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  // Настройка времени
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Time synchronized");
}

void loop() {
  byte addr[8];
  if (ds.search(addr)) {
    String serial = "";
    for (byte i = 0; i < 8; i++) {
      if (addr[i] < 16) serial += "0";
      serial += String(addr[i], HEX);
    }
    serial.toUpperCase();
    
    // Получение текущего времени
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
      Serial.println("Failed to obtain time");
      return;
    }
    char timeStr[20];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M", &timeinfo);

    // Отправка данных
    sendToGoogleSheets(serial, timeStr);
    
    ds.reset_search();
  }
  delay(100);
}

void sendToGoogleSheets(String serial, String time) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(googleScriptURL);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<100> doc;
    doc["serial"] = serial;
    doc["time"] = time;
    String payload;
    serializeJson(doc, payload);

    int httpCode = http.POST(payload);
    if (httpCode > 0) {
      String response = http.getString();
      Serial.println("HTTP Response: " + response);
    } else {
      Serial.println("HTTP Error: " + String(httpCode));
    }
    http.end();
  } else {
    Serial.println("WiFi disconnected");
  }
}