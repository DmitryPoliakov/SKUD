/*
 * SKUD - Система контроля и учета доступа с поддержкой RC522 (Mifare 13.56 МГц)
 * Версия для работы с Python-сервером
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
 * Код считывает RFID метки и отправляет их ID на Python-сервер
 * для учета посещаемости сотрудников.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ESPmDNS.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>

// Настройки режима работы
#define LOCAL_MODE 0  // 1 - локальный режим без отправки данных, 0 - отправка данных на сервер

// Настройки светодиодной индикации
#define STANDBY_BRIGHTNESS 12  // 30% от 255 для режима ожидания
#define ERROR_BLINK_INTERVAL 500  // Интервал мигания красного светодиода при ошибке (мс)

// WiFi settings
const char* primary_ssid = "TP-Link_6D5C";
const char* primary_password = "70277029";
const char* backup_ssid = "treestene";
const char* backup_password = "89028701826";

// Python API URL - IP-адрес вашего сервера
const char* serverURL = "http://194.87.43.42/api/attendance";
//http://194.87.43.42:5000/dashboard

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
  Serial.println("СКУД система запущена (Python API версия)");
  
  // Настраиваем пины для светодиодов
  pinMode(GREEN_LED_PIN, OUTPUT); // Зеленый светодиод
  pinMode(RED_LED_PIN, OUTPUT);    // Красный светодиод
  
  // Тестируем светодиоды при запуске
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, HIGH);
  delay(500);
  digitalWrite(RED_LED_PIN, LOW);
  
  // Устанавливаем зелёный светодиод на уровень ожидания (30% яркости)
  analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
  
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
    
    // Инициализация OTA
    ArduinoOTA.setHostname("SKUD-ESP32"); // Установка имени устройства в сети для OTA
    ArduinoOTA
      .onStart([]() {
        String type;
        if (ArduinoOTA.getCommand() == U_FLASH)
          type = "sketch";
        else // U_SPIFFS
          type = "filesystem";
        Serial.println("Start updating " + type);
      })
      .onEnd([]() {
        Serial.println("\nEnd");
      })
      .onProgress([](unsigned int progress, unsigned int total) {
        Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
      })
      .onError([](ota_error_t error) {
        Serial.printf("Error[%u]: ", error);
        if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
        else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
        else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
        else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
        else if (error == OTA_END_ERROR) Serial.println("End Failed");
      });
    ArduinoOTA.begin();
    Serial.println("OTA initialized with hostname: SKUD-ESP32");
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
  static unsigned long lastErrorBlinkTime = 0;
  static bool errorLedState = false;
  
  if (millis() - lastDebugTime > 5000) {
    lastDebugTime = millis();
    Serial.println("Checking RC522 status...");
    // Проверяем состояние считывателя
    byte version = rfid.PCD_ReadRegister(rfid.VersionReg);
    if (version == 0x00 || version == 0xFF) {
      Serial.println("ERROR: RFID reader not responding or not connected!");
      // Мигаем красным для индикации проблемы со считывателем
      if (millis() - lastErrorBlinkTime > ERROR_BLINK_INTERVAL) {
        lastErrorBlinkTime = millis();
        errorLedState = !errorLedState;
        digitalWrite(RED_LED_PIN, errorLedState ? HIGH : LOW);
        analogWrite(GREEN_LED_PIN, 0);
      }
    } else {
      Serial.print("RFID reader version: 0x");
      Serial.println(version, HEX);
      // Убедимся, что светодиод ожидания включен, если нет ошибок
      if (WiFi.status() == WL_CONNECTED) {
        struct tm timeinfo;
        if (getLocalTime(&timeinfo)) {
          analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
          digitalWrite(RED_LED_PIN, LOW);
        } else {
          // Нет синхронизации времени - мигаем красным
          if (millis() - lastErrorBlinkTime > ERROR_BLINK_INTERVAL) {
            lastErrorBlinkTime = millis();
            errorLedState = !errorLedState;
            digitalWrite(RED_LED_PIN, errorLedState ? HIGH : LOW);
            analogWrite(GREEN_LED_PIN, 0);
          }
        }
      } else {
        // Нет WiFi - мигаем красным
        if (millis() - lastErrorBlinkTime > ERROR_BLINK_INTERVAL) {
          lastErrorBlinkTime = millis();
          errorLedState = !errorLedState;
          digitalWrite(RED_LED_PIN, errorLedState ? HIGH : LOW);
          analogWrite(GREEN_LED_PIN, 0);
        }
      }
    }
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
    // Индикация ошибки - мигаем красным
    fadeInOut(RED_LED_PIN, 2, FADE_DELAY_FAST);
    // Возвращаем зелёный светодиод в режим ожидания
    analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
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
      // Отправляем данные на Python-сервер
      Serial.println("=== ОТПРАВКА ДАННЫХ ===");
      response = sendToPythonServer(serial, timeStr);
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
          
          // Индикация успешной отправки - одно плавное мигание вместо двух
          fadeInOut(GREEN_LED_PIN, 1, FADE_DELAY_SLOW);
          
          // Возвращаем светодиод в режим ожидания
          analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
        } else if (status == "error") {
          Serial.println("=== ОШИБКА ===");
          Serial.println("Причина: " + message);
          Serial.println("=============");
          
          // Индикация ошибки - быстрое мерцание
          fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
          
          // Возвращаем зелёный светодиод в режим ожидания
          analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
        }
      } else {
        Serial.println("Ошибка разбора JSON ответа");
        Serial.println("Полученный ответ: " + response);
        
        // Индикация ошибки - быстрое мерцание
        fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
        
        // Возвращаем зелёный светодиод в режим ожидания
        analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
      }
    }
  }
  
  // Обработка OTA обновлений
  ArduinoOTA.handle();
  
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
  
  // Если это зелёный светодиод, возвращаем его в режим ожидания
  if (pin == GREEN_LED_PIN) {
    analogWrite(pin, STANDBY_BRIGHTNESS);
  } else {
    digitalWrite(pin, LOW);
  }
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
  
  // Если это зелёный светодиод, возвращаем его в режим ожидания
  if (pin == GREEN_LED_PIN) {
    analogWrite(pin, STANDBY_BRIGHTNESS);
  } else {
    digitalWrite(pin, LOW);
  }
}

/**
 * Отправка данных на Python-сервер
 * @param serial - Серийный номер карты
 * @param time - Время в формате YYYY-MM-DD HH:MM:SS
 * @return Ответ от сервера в формате JSON
 */
String sendToPythonServer(String serial, String time) {
  if (WiFi.status() != WL_CONNECTED) {
    // Возвращаем зелёный светодиод в режим ожидания после ошибки
    analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
    return "{\"status\":\"error\",\"message\":\"Нет WiFi\"}";
  }
  
  HTTPClient http;
  http.begin(serverURL);
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
