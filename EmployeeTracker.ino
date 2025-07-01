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

// Константы для плавного мерцания
#define FADE_STEPS 50     // Количество шагов для плавного изменения яркости
#define FADE_DELAY_SLOW 15  // Задержка для медленного мерцания (мс)
#define FADE_DELAY_MEDIUM 8 // Задержка для среднего мерцания (мс)
#define FADE_DELAY_FAST 3   // Задержка для быстрого мерцания (мс)

// NTP настройки
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 10800; // GMT+3 (Москва)
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  
  // Настройка светодиодов
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  
  // Приветственная индикация при запуске
  fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_MEDIUM);
  
  // Подключение к Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi...");
    pulseLED(RED_LED_PIN, 1, FADE_DELAY_MEDIUM);
  }
  Serial.println("Connected to WiFi");
  fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_FAST);

  // Настройка времени
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Time synchronized");
}

void loop() {
  byte addr[8];
  if (ds.search(addr)) {
    // Успешное считывание ключа - короткая вспышка зеленого
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
      fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST); // Быстрое мерцание красным - ошибка
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
          
          // Успешная операция - медленное плавное мерцание зеленым
          fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_SLOW);
          
        } else if (status == "ignored") {
          // Предупреждение - чередование красного и зеленого (среднее мерцание)
          alternatingFade(GREEN_LED_PIN, RED_LED_PIN, 2, FADE_DELAY_MEDIUM);
          
        } else if (status == "unknown") {
          // Ошибка - быстрое мерцание красным
          fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
        }
      } else {
        Serial.println("Ошибка парсинга JSON");
        // Критическая ошибка - быстрое мерцание красным
        fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
      }
    } else {
      // Ошибка отправки - быстрое мерцание красным
      fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
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
    // Ошибка WiFi - быстрое мерцание красным
    fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
  }
  
  return response;
}

/**
 * Плавное включение и выключение светодиода
 * @param pin - Пин светодиода
 * @param cycles - Количество циклов мерцания
 * @param delayTime - Задержка между шагами (определяет скорость мерцания)
 */
void fadeInOut(int pin, int cycles, int delayTime) {
  for (int j = 0; j < cycles; j++) {
    // Нарастание яркости
    for (int i = 0; i <= FADE_STEPS; i++) {
      analogWrite(pin, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
    
    // Убывание яркости
    for (int i = FADE_STEPS; i >= 0; i--) {
      analogWrite(pin, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
  }
  digitalWrite(pin, LOW);
}

/**
 * Пульсация светодиода (быстрое включение, медленное затухание)
 * @param pin - Пин светодиода
 * @param cycles - Количество циклов пульсации
 * @param delayTime - Задержка между шагами
 */
void pulseLED(int pin, int cycles, int delayTime) {
  for (int j = 0; j < cycles; j++) {
    // Быстрое включение
    digitalWrite(pin, HIGH);
    delay(50);
    
    // Медленное затухание
    for (int i = FADE_STEPS; i >= 0; i--) {
      analogWrite(pin, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
  }
  digitalWrite(pin, LOW);
}

/**
 * Чередующееся плавное мерцание двух светодиодов
 * @param pin1 - Пин первого светодиода
 * @param pin2 - Пин второго светодиода
 * @param cycles - Количество циклов чередования
 * @param delayTime - Задержка между шагами
 */
void alternatingFade(int pin1, int pin2, int cycles, int delayTime) {
  for (int j = 0; j < cycles; j++) {
    // Первый светодиод нарастает, второй убывает
    for (int i = 0; i <= FADE_STEPS; i++) {
      analogWrite(pin1, i * (255 / FADE_STEPS));
      analogWrite(pin2, (FADE_STEPS - i) * (255 / FADE_STEPS));
      delay(delayTime);
    }
    
    // Первый светодиод убывает, второй нарастает
    for (int i = 0; i <= FADE_STEPS; i++) {
      analogWrite(pin1, (FADE_STEPS - i) * (255 / FADE_STEPS));
      analogWrite(pin2, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
  }
  digitalWrite(pin1, LOW);
  digitalWrite(pin2, LOW);
}