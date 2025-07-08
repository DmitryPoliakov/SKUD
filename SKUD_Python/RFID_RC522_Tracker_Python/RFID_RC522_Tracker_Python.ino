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
 *    - ArduinoOTA для обновления по WiFi
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
#include <ArduinoOTA.h>

// Настройки режима работы
#define LOCAL_MODE 0  // 1 - локальный режим без отправки данных, 0 - отправка данных на сервер

// Настройки светодиодной индикации
#define STANDBY_BRIGHTNESS 10  // 4% от 255 для режима ожидания

// Настройки OTA
#define OTA_HOST "SKUD_RFID_Controller"  // Имя устройства для OTA

// WiFi settings
const char* primary_ssid = "treestene";
const char* primary_password = "89028701826";
const char* backup_ssid = "TP-link";
const char* backup_password = "4722027";

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

// Добавляем глобальные переменные для отслеживания состояния системы
bool wifiConnected = false;
bool timeIsSynchronized = false;
bool rfidInitialized = false;

// Добавляем переменные для пульсации красного светодиода
unsigned long lastPulseTime = 0;
int pulseDirection = 1; // 1 - увеличение яркости, -1 - уменьшение
int currentRedBrightness = 0;
int pulseSpeed = 5; // Скорость пульсации (мс между шагами)
int pulseStep = 5;  // Шаг изменения яркости (1-10)

// Коды ошибок для определения скорости пульсации
#define ERROR_NONE 0       // Нет ошибок
#define ERROR_WIFI 1       // Проблема с WiFi
#define ERROR_TIME 2       // Проблема с синхронизацией времени
#define ERROR_RFID 3       // Проблема с RFID-считывателем
#define ERROR_MULTIPLE 4   // Несколько проблем одновременно

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
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  
  // Инициализация RC522 (13.56 МГц)
  SPI.begin(8, 9, 10, 6); // SCK, MISO, MOSI, SS
  rfid.PCD_Init();
  Serial.println("RC522 инициализирован");
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("RFID reader version: 0x");
  Serial.println(v, HEX);
  
  // Проверка инициализации RC522
  if (v == 0x00 || v == 0xFF) {
    Serial.println("ОШИБКА: RC522 не инициализирован или не подключен!");
    rfidInitialized = false;
    // Индикация ошибки - быстрое мигание красным светодиодом
    for (int i = 0; i < 5; i++) {
      digitalWrite(RED_LED_PIN, HIGH);
      delay(100);
      digitalWrite(RED_LED_PIN, LOW);
      delay(100);
    }
  } else {
    rfidInitialized = true;
  }
  
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
    wifiConnected = true;
    
    // Синхронизация времени
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    
    // Проверка синхронизации времени
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
      Serial.println("Time synchronized");
      timeIsSynchronized = true;
    } else {
      Serial.println("Не удалось синхронизировать время");
      timeIsSynchronized = false;
    }
    
    // Настройка OTA
    setupOTA();
  } else {
    wifiConnected = false;
    timeIsSynchronized = false;
    Serial.println("Не удалось подключиться ни к одной сети WiFi!");
    // Индикация ошибки - быстрое мигание красным светодиодом
    for (int i = 0; i < 5; i++) {
      digitalWrite(RED_LED_PIN, HIGH);
      delay(100);
      digitalWrite(RED_LED_PIN, LOW);
      delay(100);
    }
  }
  
  // Обновляем состояние светодиодов
  updateLEDStatus();
}

// Функция для обновления состояния светодиодов
void updateLEDStatus() {
  // Проверяем общее состояние системы
  bool systemOK = wifiConnected && timeIsSynchronized && rfidInitialized;
  
  if (systemOK) {
    // Всё работает нормально - зелёный светодиод горит, красный выключен
    analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
    digitalWrite(RED_LED_PIN, LOW);
    currentRedBrightness = 0;
  } else {
    // Есть проблемы - зелёный светодиод выключен, красный будет пульсировать
    digitalWrite(GREEN_LED_PIN, LOW);
    
    // Определяем тип ошибки для настройки скорости пульсации
    int errorType = ERROR_NONE;
    
    if (!wifiConnected && !timeIsSynchronized && !rfidInitialized) {
      errorType = ERROR_MULTIPLE; // Несколько проблем
      pulseSpeed = 2;  // Очень быстрая пульсация
      pulseStep = 10;  // Большой шаг
    } else if (!wifiConnected) {
      errorType = ERROR_WIFI;
      pulseSpeed = 3;  // Быстрая пульсация
      pulseStep = 5;   // Средний шаг
    } else if (!timeIsSynchronized) {
      errorType = ERROR_TIME;
      pulseSpeed = 5;  // Средняя пульсация
      pulseStep = 3;   // Малый шаг
    } else if (!rfidInitialized) {
      errorType = ERROR_RFID;
      pulseSpeed = 8;  // Медленная пульсация
      pulseStep = 2;   // Очень малый шаг
    }
    
    // Запускаем пульсацию только если есть ошибка
    if (errorType != ERROR_NONE) {
      // Пульсация будет происходить в основном цикле
      // Здесь просто включаем красный на начальную яркость
      analogWrite(RED_LED_PIN, currentRedBrightness);
    } else {
      digitalWrite(RED_LED_PIN, LOW);
    }
  }
}

// Функция для обновления пульсации красного светодиода
void updateRedPulse() {
  // Проверяем, нужна ли пульсация
  bool systemOK = wifiConnected && timeIsSynchronized && rfidInitialized;
  if (systemOK) {
    return; // Если система в порядке, пульсация не нужна
  }
  
  // Обновляем пульсацию по таймеру
  if (millis() - lastPulseTime >= pulseSpeed) {
    lastPulseTime = millis();
    
    // Изменяем яркость
    currentRedBrightness += pulseDirection * pulseStep;
    
    // Проверяем границы и меняем направление при необходимости
    if (currentRedBrightness >= 255) {
      currentRedBrightness = 255;
      pulseDirection = -1;
    } else if (currentRedBrightness <= 10) {
      currentRedBrightness = 10;
      pulseDirection = 1;
    }
    
    // Применяем новую яркость
    analogWrite(RED_LED_PIN, currentRedBrightness);
  }
}

// Функция для настройки OTA-обновления
void setupOTA() {
  // Устанавливаем имя устройства для OTA
  ArduinoOTA.setHostname(OTA_HOST);
  
  // Можно установить пароль для защиты OTA
  // ArduinoOTA.setPassword("admin");
  
  // Коллбэк при начале OTA-обновления
  ArduinoOTA.onStart([]() {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH) {
      type = "sketch";
    } else { // U_SPIFFS
      type = "filesystem";
    }
    
    // Отключаем светодиоды перед обновлением
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(RED_LED_PIN, LOW);
    
    Serial.println("Начало OTA-обновления: " + type);
  });
  
  // Коллбэк при завершении OTA-обновления
  ArduinoOTA.onEnd([]() {
    Serial.println("\nОбновление завершено");
    // Мигаем зеленым светодиодом 5 раз при успешном завершении
    for (int i = 0; i < 5; i++) {
      digitalWrite(GREEN_LED_PIN, HIGH);
      delay(100);
      digitalWrite(GREEN_LED_PIN, LOW);
      delay(100);
    }
  });
  
  // Коллбэк для отображения прогресса
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Прогресс: %u%%\r", (progress / (total / 100)));
    // Мигаем красным светодиодом для индикации процесса
    if (progress % 5 == 0) {
      digitalWrite(RED_LED_PIN, !digitalRead(RED_LED_PIN));
    }
  });
  
  // Коллбэк при ошибке
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("Ошибка[%u]: ", error);
    if (error == OTA_AUTH_ERROR) {
      Serial.println("Ошибка аутентификации");
    } else if (error == OTA_BEGIN_ERROR) {
      Serial.println("Ошибка начала обновления");
    } else if (error == OTA_CONNECT_ERROR) {
      Serial.println("Ошибка соединения");
    } else if (error == OTA_RECEIVE_ERROR) {
      Serial.println("Ошибка получения данных");
    } else if (error == OTA_END_ERROR) {
      Serial.println("Ошибка завершения");
    }
    
    // Быстро мигаем красным светодиодом при ошибке
    for (int i = 0; i < 10; i++) {
      digitalWrite(RED_LED_PIN, HIGH);
      delay(50);
      digitalWrite(RED_LED_PIN, LOW);
      delay(50);
    }
    
    // Возвращаем зеленый светодиод в режим ожидания
    analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
  });
  
  // Запускаем OTA-сервис
  ArduinoOTA.begin();
  Serial.println("OTA готов. Устройство доступно в Arduino IDE как '" + String(OTA_HOST) + "'");
  Serial.println("IP адрес: " + WiFi.localIP().toString());
}

void loop() {
  // Обработка OTA-обновлений
  ArduinoOTA.handle();
  
  // Обновляем пульсацию красного светодиода
  updateRedPulse();
  
  // Периодическая проверка WiFi-соединения и синхронизации времени
  static unsigned long lastSystemCheck = 0;
  if (millis() - lastSystemCheck > 30000) { // Каждые 30 секунд
    lastSystemCheck = millis();
    
    // Проверка WiFi
    wifiConnected = (WiFi.status() == WL_CONNECTED);
    if (!wifiConnected) {
      Serial.println("Потеряно соединение с WiFi!");
      timeIsSynchronized = false;
    } else if (!timeIsSynchronized) {
      // Если WiFi есть, но время не синхронизировано - пробуем синхронизировать
      struct tm timeinfo;
      if (getLocalTime(&timeinfo)) {
        Serial.println("Время успешно синхронизировано");
        timeIsSynchronized = true;
      } else {
        Serial.println("Не удалось синхронизировать время");
      }
    }
    
    // Обновляем состояние светодиодов
    updateLEDStatus();
  }
  
  String serial = "";
  bool cardDetected = false;
  String cardType = "";
  
  // Код для RC522 (13.56 МГц)
  static unsigned long lastDebugTime = 0;
  if (millis() - lastDebugTime > 5000) {
    lastDebugTime = millis();
    Serial.println("Checking RC522 status...");
    // Обновляем состояние светодиодов
    updateLEDStatus();
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
      
      // Обновляем статус WiFi и времени
      wifiConnected = (WiFi.status() == WL_CONNECTED);
      timeIsSynchronized = false;
      
      // Обновляем состояние светодиодов
      updateLEDStatus();
      
      // Дополнительная индикация ошибки - быстрое мигание красным светодиодом
      bool prevRedState = digitalRead(RED_LED_PIN);
      fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
      digitalWrite(RED_LED_PIN, prevRedState); // Восстанавливаем состояние красного светодиода
      
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
          
          // Временно включаем зелёный светодиод на полную яркость для индикации успеха
          bool systemOK = wifiConnected && timeIsSynchronized && rfidInitialized;
          if (systemOK) {
            // Сохраняем текущее состояние зелёного светодиода
            int prevGreenBrightness = STANDBY_BRIGHTNESS;
            
            // Индикация успешной отправки - одно плавное мигание
            fadeInOut(GREEN_LED_PIN, 1, FADE_DELAY_SLOW);
            
            // Возвращаем зелёный светодиод в режим ожидания
            analogWrite(GREEN_LED_PIN, prevGreenBrightness);
          } else {
            // Если система не в порядке, просто кратковременно включаем зелёный
            digitalWrite(RED_LED_PIN, LOW);
            digitalWrite(GREEN_LED_PIN, HIGH);
            delay(500);
            digitalWrite(GREEN_LED_PIN, LOW);
            digitalWrite(RED_LED_PIN, HIGH);
          }
        } else if (status == "error") {
          Serial.println("=== ОШИБКА ===");
          Serial.println("Причина: " + message);
          Serial.println("=============");
          
          // Дополнительная индикация ошибки - быстрое мигание красным
          bool prevRedState = digitalRead(RED_LED_PIN);
          fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
          digitalWrite(RED_LED_PIN, prevRedState);
          
          // Обновляем состояние светодиодов
          updateLEDStatus();
        }
      } else {
        Serial.println("Ошибка разбора JSON ответа");
        Serial.println("Полученный ответ: " + response);
        
        // Дополнительная индикация ошибки - быстрое мигание красным
        bool prevRedState = digitalRead(RED_LED_PIN);
        fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
        digitalWrite(RED_LED_PIN, prevRedState);
        
        // Обновляем состояние светодиодов
        updateLEDStatus();
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
  // Сохраняем предыдущее состояние светодиода
  bool isGreen = (pin == GREEN_LED_PIN);
  bool prevState = digitalRead(pin);
  int prevBrightness = isGreen ? STANDBY_BRIGHTNESS : 0;
  
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
  
  // Светодиод выключается в конце эффекта
  digitalWrite(pin, LOW);
}

/**
 * Пульсация светодиода (быстрое включение, медленное затухание)
 * @param pin - Пин светодиода
 * @param cycles - Количество циклов пульсации
 * @param delayTime - Задержка между шагами
 */
void pulseLED(int pin, int cycles, int delayTime) {
  // Сохраняем предыдущее состояние светодиода
  bool isGreen = (pin == GREEN_LED_PIN);
  bool prevState = digitalRead(pin);
  int prevBrightness = isGreen ? STANDBY_BRIGHTNESS : 0;
  
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
  
  // Светодиод выключается в конце эффекта
  digitalWrite(pin, LOW);
}

/**
 * Отправка данных на Python-сервер
 * @param serial - Серийный номер карты
 * @param time - Время в формате YYYY-MM-DD HH:MM:SS
 * @return Ответ от сервера в формате JSON
 */
String sendToPythonServer(String serial, String time) {
  if (WiFi.status() != WL_CONNECTED) {
    // Обновляем статус WiFi
    wifiConnected = false;
    
    // Обновляем состояние светодиодов
    updateLEDStatus();
    
    // Дополнительная индикация ошибки - мигание красным
    bool prevRedState = digitalRead(RED_LED_PIN);
    digitalWrite(RED_LED_PIN, LOW);
    delay(100);
    digitalWrite(RED_LED_PIN, HIGH);
    delay(200);
    digitalWrite(RED_LED_PIN, prevRedState);
    
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
      // Дополнительная индикация ошибки - короткое мигание красным
      bool prevRedState = digitalRead(RED_LED_PIN);
      digitalWrite(RED_LED_PIN, LOW);
      delay(50);
      digitalWrite(RED_LED_PIN, HIGH);
      delay(100);
      digitalWrite(RED_LED_PIN, prevRedState);
      
      response = "{\"status\":\"error\",\"message\":\"Получен пустой ответ от сервера\"}";
    }
  } else {
    // Дополнительная индикация ошибки - мигание красным
    bool prevRedState = digitalRead(RED_LED_PIN);
    digitalWrite(RED_LED_PIN, LOW);
    delay(100);
    digitalWrite(RED_LED_PIN, HIGH);
    delay(200);
    digitalWrite(RED_LED_PIN, prevRedState);
    
    response = "{\"status\":\"error\",\"message\":\"HTTP Error " + String(httpCode) + "\"}";
  }
  
  http.end();
  return response;
} 