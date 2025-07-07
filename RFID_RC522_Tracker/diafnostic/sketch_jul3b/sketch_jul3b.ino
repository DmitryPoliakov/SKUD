/*
 * SKUD - Система контроля и учета доступа с поддержкой разных RFID считывателей
 * 
 * Поддерживаемые считыватели:
 * 1. RC522 - для карт Mifare (13.56 МГц)
 * 2. RDM6300 - для карт/брелоков EM4100/EM4102 (125 кГц)
 * 
 * Схема подключения RC522 (13.56 МГц) к ESP32-C3-MINI-1:
 * +-----------+----------------+
 * | RC522     | ESP32-C3       |
 * +-----------+----------------+
 * | SDA (SS)  | GPIO6 (D4)     |
 * | SCK       | GPIO8 (D8)     |
 * | MOSI      | GPIO10 (D10)   |
 * | MISO      | GPIO9 (D9)     |
 * | GND       | GND            |
 * | RST       | GPIO7 (D5)     |
 * | 3.3V      | 3V3            |
 * +-----------+----------------+
 * 
 * Схема подключения RDM6300 (125 кГц) к ESP32-C3-MINI-1:
 * +-----------+----------------+
 * | RDM6300   | ESP32-C3       |
 * +-----------+----------------+
 * | TX        | GPIO21         | (RX для Serial1 на ESP32-C3)
 * | RX        | не подключать  |
 * | GND       | GND            |
 * | VCC       | 5V             |
 * +-----------+----------------+
 * 
 * Перед использованием:
 * 1. Выберите используемый считыватель, установив соответствующие дефайны:
 *    - USE_RC522 = 1 для RC522 (13.56 МГц)
 *    - USE_RDM6300 = 1 для RDM6300 (125 кГц)
 * 2. Установите необходимые библиотеки:
 *    - MFRC522 для RC522
 * 3. Настройте WiFi и URL для отправки данных
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include <ArduinoJson.h>

// Выбор считывателя
#define USE_RC522 1    // 1 - использовать RC522 (13.56 МГц, карты Mifare)
#define USE_RDM6300 0  // 1 - использовать RDM6300 (125 кГц, таблеточки EM4100)

// Настройки режима работы
#define LOCAL_MODE 0  // 1 - локальный режим без отправки данных, 0 - отправка данных на сервер

// Подключаем нужные библиотеки
#if USE_RC522
#include <SPI.h>
#include <MFRC522.h>
#endif

// WiFi settings
const char* primary_ssid = "treestene";
const char* primary_password = "89028701826";
const char* backup_ssid = "TP-link";
const char* backup_password = "4722027";

// Google Apps Script URL
const char* googleScriptURL = "https://script.google.com/macros/s/AKfycbxVU1KidIsEnyTDBiUBUnjohuHShCYouPN7THvdABB3BvdxVCle6W6xVDjyHgub_Ouu/exec";

// Определения для RC522
#if USE_RC522
#define RST_PIN 7
#define SS_PIN 6
MFRC522 rfid(SS_PIN, RST_PIN);
#endif

// Определения для RDM6300
#if USE_RDM6300
#define RDM6300_RX_PIN 21  // Используем GPIO21 (RX для Serial1 на ESP32-C3)
#define RDM6300_SERIAL Serial1
const int DATA_LENGTH = 14;
byte tagData[DATA_LENGTH];
int dataIndex = 0;
unsigned long lastTagTime = 0;

struct RDM6300_Tag {
  unsigned long tagID = 0;
  bool isValid = false;
};
#endif

// Светодиоды (изменены пины для избежания конфликтов)
#define GREEN_LED_PIN 4
#define RED_LED_PIN 5

// NTP settings
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 18000; // GMT+5 (Уральское время)
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("СКУД система запущена");

  // Настраиваем пины для светодиодов
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);

  // Тестируем светодиоды при запуске
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, HIGH);
  delay(500);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);

#if USE_RC522
  SPI.begin(8, 9, 10, 6); // SCK, MISO, MOSI, SS
  rfid.PCD_Init();
  Serial.println("RC522 инициализирован");
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("RFID reader version: 0x");
  Serial.println(v, HEX);
#endif

#if USE_RDM6300
  RDM6300_SERIAL.begin(9600, SERIAL_8N1, RDM6300_RX_PIN, -1); // RX on GPIO21, TX not used
  while (RDM6300_SERIAL.available()) RDM6300_SERIAL.read(); // Clear buffer
  Serial.println("RDM6300 инициализирован на пине GPIO" + String(RDM6300_RX_PIN));
#endif

  // WiFi подключение
  Serial.println("Подключаюсь к основной WiFi сети: " + String(primary_ssid));
  WiFi.begin(primary_ssid, primary_password);
  int timeout_counter = 0;
  while (WiFi.status() != WL_CONNECTED && timeout_counter < 60) {
    delay(500);
    Serial.print(".");
    timeout_counter++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Не удалось подключиться к основной сети. Пробую резервную: " + String(backup_ssid));
    WiFi.disconnect();
    delay(1000);
    WiFi.begin(backup_ssid, backup_password);
    timeout_counter = 0;
    while (WiFi.status() != WL_CONNECTED && timeout_counter < 60) {
      delay(500);
      Serial.print(".");
      timeout_counter++;
    }
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Connected to WiFi");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    Serial.println("Time synchronized");
  } else {
    Serial.println("Не удалось подключиться ни к одной сети WiFi!");
  }
}

void loop() {
  String serial = "";
  bool cardDetected = false;
  String cardType = "";

#if USE_RC522
  static unsigned long lastDebugTime = 0;
  if (millis() - lastDebugTime > 5000) {
    lastDebugTime = millis();
    Serial.println("Checking RC522 status...");
  }

  cardDetected = rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial();
  if (cardDetected) {
    serial = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
      if (rfid.uid.uidByte[i] < 0x10) serial += "0";
      serial += String(rfid.uid.uidByte[i], HEX);
    }
    serial.toUpperCase();
    cardType = "MIFARE";
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    Serial.println("RC522 card read: " + serial);
  }
#endif

#if USE_RDM6300
  static unsigned long lastRDM6300Read = 0;
  if (millis() - lastRDM6300Read > 1000) {
    RDM6300_Tag tag = readRDM6300();
    if (tag.isValid) {
      lastRDM6300Read = millis();
      cardDetected = true;
      serial = String(tag.tagID, HEX);
      while (serial.length() < 8) serial = "0" + serial;
      serial.toUpperCase();
      cardType = "EM4100";
      Serial.println("RDM6300 card read: " + serial);
    }
  }
#endif

  if (cardDetected && serial.length() > 0) {
    struct tm timeinfo;
    if (WiFi.status() != WL_CONNECTED || !getLocalTime(&timeinfo)) {
      Serial.println("Не удалось получить время или WiFi не подключен");
      return;
    }
    char timeStr[20];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", &timeinfo);

    // Индикация
    for (int i = 0; i < 3; i++) {
      digitalWrite(GREEN_LED_PIN, HIGH);
      delay(100);
      digitalWrite(GREEN_LED_PIN, LOW);
      delay(100);
    }

#if LOCAL_MODE
    Serial.println("Локальный режим: Карта " + serial + ", Тип: " + cardType + ", Время: " + String(timeStr));
#else
    Serial.println("Отправка данных в Google Таблицы...");
    String response = sendToGoogleSheets(serial, timeStr);
    if (response.length() > 0) {
      StaticJsonDocument<256> doc;
      DeserializationError error = deserializeJson(doc, response);
      if (!error) {
        String status = doc["status"];
        Serial.println("Статус: " + status);
        if (status == "success") {
          digitalWrite(GREEN_LED_PIN, HIGH);
          delay(1000);
          digitalWrite(GREEN_LED_PIN, LOW);
        } else {
          digitalWrite(RED_LED_PIN, HIGH);
          delay(1000);
          digitalWrite(RED_LED_PIN, LOW);
        }
      } else {
        Serial.println("Ошибка разбора JSON: " + response);
        digitalWrite(RED_LED_PIN, HIGH);
        delay(1000);
        digitalWrite(RED_LED_PIN, LOW);
      }
    }
#endif
  }
  delay(100);
}

#if USE_RDM6300
RDM6300_Tag readRDM6300() {
  RDM6300_Tag tag;
  tag.isValid = false;

  while (RDM6300_SERIAL.available() > 0 && dataIndex < DATA_LENGTH) {
    byte inByte = RDM6300_SERIAL.read();
    if (inByte == 0x02) {
      dataIndex = 0;
      memset(tagData, 0, DATA_LENGTH);
    }
    tagData[dataIndex++] = inByte;
    if (inByte == 0x03 && dataIndex == DATA_LENGTH) {
      if (validateChecksum()) {
        unsigned long cardID = 0;
        for (int i = 1; i < 11; i += 2) {
          byte high = getHexValue(tagData[i]);
          byte low = getHexValue(tagData[i + 1]);
          if (high == 0xFF || low == 0xFF) break;
          cardID = (cardID << 8) | (high << 4 | low);
        }
        tag.tagID = cardID;
        tag.isValid = true;
      }
      dataIndex = 0;
      break;
    }
  }
  return tag;
}

bool validateChecksum() {
  byte checksum = 0;
  for (int i = 1; i <= 10; i += 2) {
    byte val = getHexValue(tagData[i]) << 4 | getHexValue(tagData[i + 1]);
    if (val == 0xFF) return false;
    checksum ^= val;
  }
  byte received = getHexValue(tagData[11]) << 4 | getHexValue(tagData[12]);
  return checksum == received;
}

byte getHexValue(byte c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return 0xFF;
}
#endif

String sendToGoogleSheets(String serial, String time) {
  if (WiFi.status() != WL_CONNECTED) return "{\"status\":\"error\",\"message\":\"Нет WiFi\"}";
  if (String(googleScriptURL).indexOf("YOUR_SCRIPT_ID") != -1) return "{\"status\":\"error\",\"message\":\"URL не настроен\"}";

  HTTPClient http;
  http.begin(googleScriptURL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<200> doc;
  doc["serial"] = serial;
  doc["time"] = time;
  String payload;
  serializeJson(doc, payload);

  Serial.println("Отправка POST: " + payload);
  int httpCode = http.POST(payload);

  String response = "";
  if (httpCode > 0) {
    response = http.getString();
    Serial.println("HTTP код: " + String(httpCode));
    Serial.println("Ответ: " + response);

    // Проверка на перенаправление (HTTP 302)
    if (httpCode == 302) {
      Serial.println("Перенаправление обнаружено. Пожалуйста, обновите URL Web App.");
      response = "{\"status\":\"error\",\"message\":\"Перенаправление 302, обновите URL\"}";
    }
  } else {
    response = "{\"status\":\"error\",\"message\":\"HTTP Error " + String(httpCode) + "\"}";
  }

  http.end();
  return response;
}