/*
 * SKUD - Система контроля и учета доступа с поддержкой RC522 (Mifare 13.56 МГц)
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
 * Перед использованием:
 * 1. Установите необходимые библиотеки:
 *    - MFRC522 для RC522
 * 2. Настройте WiFi и URL для отправки данных
 * 
 * Код считывает RFID метки и отправляет их ID в Google Sheets
 * для учета посещаемости сотрудников.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <MFRC522.h>

// Настройки режима работы
#define LOCAL_MODE 0  // 1 - локальный режим без отправки данных, 0 - отправка данных на сервер

// WiFi settings
const char* primary_ssid = "treestene";
const char* primary_password = "89028701826";
const char* backup_ssid = "TP-link";
const char* backup_password = "4722027";

// Google Apps Script URL
  // https://docs.google.com/spreadsheets/d/1vyUPj2rnUWmzjyvmItjLp9Dhv69jswUZ3iASZn4l8Hc/edit?usp=sharing
 // https://script.google.com/u/0/home/projects/1BIUbMH5hntb-37NmqS7xb1JD1WYYtElcxlzPwFQ2uavPaQYdCz_y6Awz/edit
 // https://script.google.com/macros/s/AKfycbxVU1KidIsEnyTDBiUBUnjohuHShCYouPN7THvdABB3BvdxVCle6W6xVDjyHgub_Ouu/exec
const char* googleScriptURL = "https://script.google.com/macros/s/AKfycbwRBuU1NfRVZ-WAu4PlvtYLtZFVz1rdhOSNBVdjmbyiD8LHN59dOsVFNX3zW7jp6OY/exec";

// LEDs
#define GREEN_LED_PIN 4  // Green LED pin
#define RED_LED_PIN 5    // Red LED pin

// Определения для RC522 (13.56 МГц)
  #define RST_PIN 7         // RST pin for RFID RC522 (GPIO7, D5)
  #define SS_PIN 6          // SS (SDA) pin for RFID RC522 (GPIO6, D4)
  MFRC522 rfid(SS_PIN, RST_PIN); // Create MFRC522 instance

// Общие определения
#define FADE_STEPS 50     // Number of steps for smooth brightness change
#define FADE_DELAY_SLOW 15 // Delay for slow fading (ms)
#define FADE_DELAY_MEDIUM 8 // Delay for medium fading (ms)
#define FADE_DELAY_FAST 3   // Delay for fast fading (ms)

// NTP settings
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 18000; // GMT+5 (Уральское время)
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("СКУД система запущена");
  
  // Настраиваем пины для светодиодов
  pinMode(GREEN_LED_PIN, OUTPUT); // Зеленый светодиод
  pinMode(RED_LED_PIN, OUTPUT);    // Красный светодиод
  
  // Тестируем светодиоды при запуске
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, HIGH);
  delay(500);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  
  // Инициализация RC522 (13.56 МГц)
  SPI.begin(8, 9, 10, 6); // SCK, MISO, MOSI, SS
  rfid.PCD_Init();
  Serial.println("RC522 инициализирован");
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("RFID reader version: 0x");
  Serial.println(v, HEX);
  
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
  
  // Код для RC522 (13.56 МГц)
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
  
  // Общий код для обработки карты
  if (cardDetected && serial.length() > 0) {
    // Получение текущего времени
    struct tm timeinfo;
    if (WiFi.status() != WL_CONNECTED || !getLocalTime(&timeinfo)) {
      Serial.println("Не удалось получить время или WiFi не подключен");
      return;
    }
    char timeStr[20];
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", &timeinfo);

    // Индикация - плавное мерцание
    pulseLED(GREEN_LED_PIN, 2, FADE_DELAY_MEDIUM);

    // Отправляем данные и получаем ответ
    String response;
    if (LOCAL_MODE) {
    // В локальном режиме просто выводим данные в консоль
      response = "{\"status\":\"success\",\"message\":\"Local mode\",\"employee\":\"Unknown\",\"event\":\"scan\",\"time\":\"" + String(timeStr) + "\"}";
    Serial.println("=== ЛОКАЛЬНЫЙ РЕЖИМ ===");
    Serial.println("Карта: " + serial + ", Тип: " + cardType + ", Время: " + String(timeStr));
    Serial.println("=====================");
    } else {
    // Отправляем данные на сервер Google Таблиц
    Serial.println("=== ОТПРАВКА ДАННЫХ ===");
      response = sendToGoogleSheets(serial, timeStr);
    Serial.println("======================");
    }
    
    // Обрабатываем ответ
    if (response.length() > 0) {
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
          
          Serial.println("=== РЕЗУЛЬТАТ ===");
          Serial.println("Сотрудник: " + employee);
          Serial.println("Событие: " + event);
          Serial.println("Время: " + time);
          Serial.println("================");
          
          // Индикация успешной отправки - плавное мерцание
          fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_SLOW);
        } else if (status == "error") {
          Serial.println("=== ОШИБКА ===");
          Serial.println("Причина: " + message);
          Serial.println("=============");
          
          // Индикация ошибки - быстрое мерцание
          fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
        }
      } else {
        Serial.println("Ошибка разбора JSON ответа");
        Serial.println("Полученный ответ: " + response);
        
        // Индикация ошибки - быстрое мерцание
        fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
      }
    }
  }
  
  delay(100); // Уменьшаем задержку перед следующим чтением
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

String sendToGoogleSheets(String serial, String time) {
  if (WiFi.status() != WL_CONNECTED) return "{\"status\":\"error\",\"message\":\"Нет WiFi\"}";
  if (String(googleScriptURL).indexOf("YOUR_SCRIPT_ID") != -1) return "{\"status\":\"error\",\"message\":\"URL не настроен\"}";

  HTTPClient http;
  http.begin(googleScriptURL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000); // Увеличиваем таймаут до 10 секунд

  StaticJsonDocument<200> doc;
  doc["serial"] = serial;
  doc["time"] = time;
  String payload;
  serializeJson(doc, payload);

  Serial.println("Отправка POST: " + payload);
  int httpCode = http.POST(payload);

  String response = "";
  if (httpCode > 0) {
    // Получаем ответ от сервера
    response = http.getString();
    Serial.println("HTTP код: " + String(httpCode));
    
    // Для кода 302 добавляем дополнительную информацию в лог
    if (httpCode == 302) {
      String location = http.header("Location");
      Serial.println("Получен редирект 302. Location: " + location);
      
      // Пробуем выполнить запрос по новому URL
      http.end();
      http.begin(location);
      http.addHeader("Content-Type", "application/json");
      int redirectCode = http.POST(payload);
      
      if (redirectCode > 0) {
        response = http.getString();
        Serial.println("HTTP код после редиректа: " + String(redirectCode));
        Serial.println("Ответ после редиректа: " + response);
      } else {
        Serial.println("Ошибка при следовании редиректу: " + String(redirectCode));
      }
    }
    
    // Выводим ответ в лог
    Serial.println("Ответ: " + response);
    
    // Если ответ пустой, создаем временный ответ
    if (response.length() == 0) {
      response = "{\"status\":\"error\",\"message\":\"Получен пустой ответ от сервера\"}";
    }
  } else {
    response = "{\"status\":\"error\",\"message\":\"HTTP Error " + String(httpCode) + "\"}";
  }
  
  http.end();
  return response;
}