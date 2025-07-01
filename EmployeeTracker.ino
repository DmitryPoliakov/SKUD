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

// Светодиоды
#define GREEN_LED_PIN 25  // Пин зеленого светодиода
#define RED_LED_PIN 26    // Пин красного светодиода
#define LED_BLINK_DURATION 500 // Длительность мигания светодиода в мс

// NTP настройки
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 10800; // GMT+3 (Москва)
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  
  // Настройка светодиодов
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  
  // Тестовое мигание светодиодов при запуске
  blinkLED(GREEN_LED_PIN, 2);
  blinkLED(RED_LED_PIN, 2);
  
  // Подключение к Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
    blinkLED(RED_LED_PIN, 1); // Мигаем красным при подключении
  }
  Serial.println("Connected to WiFi");
  blinkLED(GREEN_LED_PIN, 3); // Мигаем зеленым при успешном подключении

  // Настройка времени
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Time synchronized");
}

void loop() {
  byte addr[8];
  if (ds.search(addr)) {
    // Успешное считывание ключа
    digitalWrite(GREEN_LED_PIN, HIGH);
    
    String serial = "";
    for (byte i = 0; i < 8; i++) {
      if (addr[i] < 16) serial += "0";
      serial += String(addr[i], HEX);
    }
    serial.toUpperCase();
    Serial.println("Считан ключ: " + serial);
    
    // Получение текущего времени
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
      Serial.println("Failed to obtain time");
      blinkLED(RED_LED_PIN, 2); // Ошибка получения времени
      digitalWrite(GREEN_LED_PIN, LOW);
      return;
    }
    char timeStr[20];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M", &timeinfo);

    // Отправка данных и получение ответа
    String response = sendToGoogleSheets(serial, timeStr);
    
    // Обработка ответа
    if (response.length() > 0) {
      // Парсим JSON-ответ
      StaticJsonDocument<256> doc;
      DeserializationError error = deserializeJson(doc, response);
      
      if (!error) {
        String status = doc["status"];
        String message = doc["message"];
        
        Serial.println("Статус: " + status);
        Serial.println("Сообщение: " + message);
        
        if (status == "success") {
          String employee = doc["employee"];
          String event = doc["event"];
          String time = doc["time"];
          
          Serial.println("Сотрудник: " + employee);
          Serial.println("Событие: " + event);
          Serial.println("Время: " + time);
          
          // Визуальная индикация типа события
          if (event == "приход") {
            // Приход - два быстрых мигания зеленым
            blinkLED(GREEN_LED_PIN, 2, 200);
          } else if (event == "уход") {
            // Уход - три быстрых мигания зеленым
            blinkLED(GREEN_LED_PIN, 3, 200);
          }
        } else if (status == "ignored") {
          // Игнорированное событие - попеременное мигание красным и зеленым
          for (int i = 0; i < 2; i++) {
            digitalWrite(RED_LED_PIN, HIGH);
            delay(200);
            digitalWrite(RED_LED_PIN, LOW);
            digitalWrite(GREEN_LED_PIN, HIGH);
            delay(200);
            digitalWrite(GREEN_LED_PIN, LOW);
          }
        } else if (status == "unknown") {
          // Неизвестный ключ - быстрое мигание красным
          blinkLED(RED_LED_PIN, 5, 100);
        }
      } else {
        Serial.println("Ошибка парсинга JSON");
        blinkLED(RED_LED_PIN, 3);
      }
    } else {
      // Ошибка отправки
      blinkLED(RED_LED_PIN, 3);
    }
    
    ds.reset_search();
  }
  
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  delay(100);
}

String sendToGoogleSheets(String serial, String time) {
  String response = "";
  
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
      response = http.getString();
      Serial.println("HTTP Response: " + response);
    } else {
      Serial.println("HTTP Error: " + String(httpCode));
    }
    http.end();
  } else {
    Serial.println("WiFi disconnected");
    blinkLED(RED_LED_PIN, 5); // Ошибка WiFi
  }
  
  return response;
}

/**
 * Мигает светодиодом указанное количество раз
 * @param pin - Пин светодиода
 * @param times - Количество миганий
 * @param duration - Длительность мигания (опционально)
 */
void blinkLED(int pin, int times, int duration = LED_BLINK_DURATION) {
  for (int i = 0; i < times; i++) {
    digitalWrite(pin, HIGH);
    delay(duration);
    digitalWrite(pin, LOW);
    delay(duration);
  }
}