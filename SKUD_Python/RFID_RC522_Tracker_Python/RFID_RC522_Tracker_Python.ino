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
#define ENABLE_OTA 1  // 1 - включить OTA обновления, 0 - отключить (для отладки проблем с RC522)
#define ENABLE_WIFI 1 // 1 - включить WiFi, 0 - отключить (только RC522 тест, для отладки конфликтов)

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

// Функция мигания красным светодиодом
void blinkRed(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(RED_LED_PIN, HIGH);
    delay(200);
    digitalWrite(RED_LED_PIN, LOW);
    delay(200);
  }
}

// Функция тестирования RC522 с разными настройками SPI
bool testRC522Connection() {
  Serial.println("[RC522] Тестирование соединения...");
  
  // Пробуем разные частоты SPI
  uint32_t frequencies[] = {1000000, 2000000, 4000000, 8000000}; // 1, 2, 4, 8 МГц
  int freqCount = sizeof(frequencies) / sizeof(frequencies[0]);
  
  for (int i = 0; i < freqCount; i++) {
    Serial.printf("[RC522] Тест с частотой %lu Гц...\n", frequencies[i]);
    
    SPI.setFrequency(frequencies[i]);
    delay(10);
    
    // Сброс и повторная инициализация
    rfid.PCD_Reset();
    delay(50);
    rfid.PCD_Init();
    delay(100);
    
    // Проверяем версию
    byte version = rfid.PCD_ReadRegister(rfid.VersionReg);
    Serial.printf("[RC522] Версия при %lu Гц: 0x%02X\n", frequencies[i], version);
    
    if (version != 0x00 && version != 0xFF) {
      // Пробуем выполнить самотест
      bool selfTest = rfid.PCD_PerformSelfTest();
      Serial.printf("[RC522] Самотест при %lu Гц: %s\n", frequencies[i], selfTest ? "ПРОЙДЕН" : "ПРОВАЛЕН");
      
      if (selfTest) {
        Serial.printf("[RC522] ✓ Оптимальная частота найдена: %lu Гц\n", frequencies[i]);
        // Переинициализируем после самотеста
        rfid.PCD_Init();
        return true;
      }
    }
  }
  
  Serial.println("[RC522][ERROR] Не удалось найти рабочую частоту SPI!");
  return false;
}

// Функция подключения к WiFi с предварительным сканированием
void connectToWiFi() {
  Serial.println("[WiFi] Начинаю подключение к WiFi...");
  
  while (true) {
    Serial.println("[WiFi] Сканирую доступные сети...");
    int n = WiFi.scanNetworks();
    bool primaryFound = false, backupFound = false;
    
    Serial.printf("[WiFi] Найдено сетей: %d\n", n);
    
    for (int i = 0; i < n; ++i) {
      String ssid = WiFi.SSID(i);
      Serial.printf("[WiFi] Сеть %d: %s (сигнал: %d dBm)\n", i+1, ssid.c_str(), WiFi.RSSI(i));
      if (ssid == primary_ssid) {
        primaryFound = true;
        Serial.println("[WiFi] ✓ Основная сеть найдена!");
      }
      if (ssid == backup_ssid) {
        backupFound = true;
        Serial.println("[WiFi] ✓ Резервная сеть найдена!");
      }
    }

    if (primaryFound) {
      Serial.println("[WiFi] Подключаюсь к основной сети: " + String(primary_ssid));
      WiFi.begin(primary_ssid, primary_password);
    } else if (backupFound) {
      Serial.println("[WiFi] Основная сеть не найдена, подключаюсь к резервной: " + String(backup_ssid));
      WiFi.begin(backup_ssid, backup_password);
    } else {
      Serial.println("[WiFi][ERROR] Нет доступных известных сетей!");
      Serial.println("[WiFi] Ожидаю 10 секунд и повторяю сканирование...");
      blinkRed(25); // мигаем 5 секунд
      delay(5000);  // ещё 5 секунд ждём
      continue;
    }

    // Ждём подключения максимум 15 секунд
    int timeout = 0;
    while (WiFi.status() != WL_CONNECTED && timeout < 30) {
      delay(500);
      Serial.print(".");
      timeout++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\n[WiFi] ✓ Успешно подключено к WiFi!");
      Serial.print("[WiFi] IP адрес: ");
      Serial.println(WiFi.localIP());
      Serial.print("[WiFi] Сила сигнала: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      Serial.print("[WiFi] Подключено к сети: ");
      Serial.println(WiFi.SSID());
      break; // Выходим из цикла - подключение успешно
    } else {
      Serial.println("\n[WiFi][ERROR] Не удалось подключиться к сети!");
      Serial.println("[WiFi] Ожидаю 10 секунд и повторяю попытку...");
      WiFi.disconnect(); // Отключаемся перед новой попыткой
      blinkRed(25); // мигаем 5 секунд
      delay(5000);  // ещё 5 секунд ждём
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("СКУД система запущена (Python API версия)");
  
  // Настраиваем пины для светодиодов
  pinMode(GREEN_LED_PIN, OUTPUT); // Зеленый светодиод
  pinMode(RED_LED_PIN, OUTPUT);    // Красный светодиод
  
  // СТАРТ: Всегда красный, пока не прошли все этапы
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  Serial.println("[LED] Красный: стартовая инициализация");
  delay(500);

  // Инициализация RC522 (13.56 МГц)
  Serial.println("[RC522] Инициализация...");
  Serial.println("[RC522] ВНИМАНИЕ: Используются пины GPIO6,7,8,9,10 - возможны конфликты на ESP32-C3!");
  Serial.println("[RC522] Если проблемы - смените пины на GPIO1,2,3,0,20 или отключите WiFi");
  
  // Пробуем инициализировать SPI с пониженной частотой для стабильности
  SPI.begin(8, 9, 10, 6); // SCK, MISO, MOSI, SS
  SPI.setFrequency(1000000); // Понижаем частоту SPI до 1 МГц (вместо стандартных 4 МГц)
  SPI.setDataMode(SPI_MODE0);
  SPI.setBitOrder(MSBFIRST);
  
  rfid.PCD_Init();
  delay(100); // Даём время RC522 инициализироваться
  
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("[RC522] Версия считывателя: 0x");
  Serial.println(v, HEX);
  
  // Дополнительная диагностика
  if (v == 0x91 || v == 0x92) {
    Serial.println("[RC522] ✓ Обнаружен MFRC522 v1.0 или v2.0");
  } else if (v == 0x12) {
    Serial.println("[RC522] ✓ Обнаружен совместимый чип (возможно клон)");
  } else {
    Serial.printf("[RC522][WARN] Неожиданная версия: 0x%02X (может работать нестабильно)\n", v);
  }
  if (v == 0x00 || v == 0xFF) {
    Serial.println("[RC522][ERROR] Не удалось обнаружить RC522! Пробуем автоматическую настройку...");
    
    // Пробуем найти рабочую конфигурацию
    if (!testRC522Connection()) {
      Serial.println("[RC522][ERROR] Автоматическая настройка не помогла!");
      Serial.println("[RC522][ERROR] Возможные причины:");
      Serial.println("[RC522][ERROR] 1. Неправильное подключение проводов");
      Serial.println("[RC522][ERROR] 2. Конфликт пинов GPIO6,7,8,9,10 с Flash/WiFi");
      Serial.println("[RC522][ERROR] 3. Неисправный RC522 модуль");
      Serial.println("[RC522][ERROR] 4. Недостаточное питание (нужно 3.3V)");
      
      // Мигаем красным и блокируем работу
      while (true) {
        blinkRed(10);
        delay(2000);
        Serial.println("[RC522][ERROR] Для решения проблемы:");
        Serial.println("[RC522][ERROR] - Проверьте провода");
        Serial.println("[RC522][ERROR] - Попробуйте другие GPIO пины");
        Serial.println("[RC522][ERROR] - Установите ENABLE_OTA=0 для отключения WiFi во время отладки");
      }
    } else {
      Serial.println("[RC522] ✓ Автоматическая настройка успешна!");
    }
  }

  // WiFi подключение (если включено)
  if (ENABLE_WIFI) {
    connectToWiFi();
  } else {
    Serial.println("[WiFi] WiFi отключен (ENABLE_WIFI = 0) - тестируем только RC522");
  }

  // NTP и синхронизация времени
  Serial.println("[NTP] Синхронизация времени...");
  Serial.println("[NTP] NTP сервер: " + String(ntpServer));
  Serial.println("[NTP] Часовой пояс: GMT+" + String(gmtOffset_sec/3600));
  
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  
  // Ждём синхронизации с увеличивающимся таймаутом
  struct tm timeinfo;
  int attempt = 1;
  int maxAttempts = 10;
  
  while (attempt <= maxAttempts) {
    Serial.printf("[NTP] Попытка %d/%d - ожидание синхронизации", attempt, maxAttempts);
    
    // Ждём с прогрессом
    int waitTime = 3 + (attempt * 2); // 5, 7, 9, 11... секунд
    for (int i = 0; i < waitTime; i++) {
      delay(1000);
      Serial.print(".");
      // Проверяем время каждую секунду
      if (getLocalTime(&timeinfo)) {
        Serial.println("");
        Serial.printf("[NTP] ✓ Время синхронизировано за %d сек: %02d:%02d:%02d %02d.%02d.%04d\n", 
                     i+1, timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec,
                     timeinfo.tm_mday, timeinfo.tm_mon+1, timeinfo.tm_year+1900);
        goto ntp_success;
      }
    }
    
    Serial.println("");
    Serial.printf("[NTP][WARN] Попытка %d неудачна, повторяю...\n", attempt);
    
    // Мигаем красным только при неудачной попытке
    blinkRed(3);
    
    // Повторяем конфигурацию NTP для следующей попытки
    if (attempt < maxAttempts) {
      configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    }
    
    attempt++;
  }
  
  // Если все попытки неудачны
  Serial.println("[NTP][ERROR] Не удалось синхронизировать время за " + String(maxAttempts) + " попыток!");
  Serial.println("[NTP][ERROR] Проверьте подключение к интернету и NTP сервер");
  while (true) {
    blinkRed(20);
    delay(5000);
    Serial.println("[NTP][ERROR] Критическая ошибка! Перезагрузите устройство или проверьте сеть.");
  }
  
  ntp_success:
  Serial.println("[NTP] ✓ Синхронизация времени завершена успешно!");

  // OTA (если включено)
  if (ENABLE_OTA) {
    Serial.println("[OTA] Инициализация...");
    ArduinoOTA.setHostname("SKUD-ESP32");
  ArduinoOTA.setPort(3232);  // Стандартный порт OTA
  ArduinoOTA
    .onStart([]() {
      String type;
      if (ArduinoOTA.getCommand() == U_FLASH)
        type = "sketch";
      else
        type = "filesystem";
      Serial.println("[OTA] Начало обновления: " + type);
      Serial.println("[OTA] ВНИМАНИЕ: RC522 будет отключен во время обновления!");
      
      // Останавливаем RC522 во время OTA
      rfid.PCD_SoftPowerDown();
      
      // Индикация OTA - быстрое мигание обоих светодиодов
      for (int i = 0; i < 10; i++) {
        digitalWrite(RED_LED_PIN, HIGH);
        digitalWrite(GREEN_LED_PIN, HIGH);
        delay(100);
        digitalWrite(RED_LED_PIN, LOW);
        digitalWrite(GREEN_LED_PIN, LOW);
        delay(100);
      }
      // Оставляем красный включенным во время обновления
      digitalWrite(RED_LED_PIN, HIGH);
    })
    .onEnd([]() {
      Serial.println("[OTA] Обновление завершено!");
      Serial.println("[OTA] Перезагрузка...");
      // Светодиоды выключим - после перезагрузки инициализируются заново
      digitalWrite(RED_LED_PIN, LOW);
      digitalWrite(GREEN_LED_PIN, LOW);
    })
    .onProgress([](unsigned int progress, unsigned int total) {
      // Показываем прогресс только каждые 10%
      static int lastPercent = -1;
      int percent = (progress / (total / 100));
      if (percent != lastPercent && percent % 10 == 0) {
        Serial.printf("[OTA] Прогресс: %u%%\n", percent);
        lastPercent = percent;
      }
    })
    .onError([](ota_error_t error) {
      Serial.printf("[OTA][ERROR] Ошибка %u: ", error);
      if (error == OTA_AUTH_ERROR) Serial.println("Ошибка авторизации");
      else if (error == OTA_BEGIN_ERROR) Serial.println("Ошибка начала");
      else if (error == OTA_CONNECT_ERROR) Serial.println("Ошибка подключения");
      else if (error == OTA_RECEIVE_ERROR) Serial.println("Ошибка получения");
      else if (error == OTA_END_ERROR) Serial.println("Ошибка завершения");
      
      // Перезапускаем RC522 после ошибки OTA
      rfid.PCD_Reset();
      rfid.PCD_Init();
      
      // Возвращаем нормальную индикацию
      digitalWrite(RED_LED_PIN, LOW);
      analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
      Serial.println("[OTA] RC522 восстановлен после ошибки OTA");
    });
    ArduinoOTA.begin();
    Serial.println("[OTA] OTA инициализирован (hostname: SKUD-ESP32, port: 3232)");
  } else {
    Serial.println("[OTA] OTA отключен (ENABLE_OTA = 0)");
  }

  // Если всё успешно — включаем зелёный, красный выключаем
  digitalWrite(RED_LED_PIN, LOW);
  analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
  Serial.println("[LED] Готов к работе: зелёный (ожидание карты)");
}

void loop() {
  String serial = "";
  bool cardDetected = false;
  String cardType = "";
  
  // Код для RC522 (13.56 МГц)
  static unsigned long lastDebugTime = 0;
  static unsigned long lastErrorBlinkTime = 0;
  static bool errorLedState = false;
  
  // Проверка статуса системы каждые 5 секунд
  if (millis() - lastDebugTime > 5000) {
    lastDebugTime = millis();
    Serial.println("[STATUS] Проверка состояния системы...");
    
    // Проверяем WiFi подключение
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[STATUS][ERROR] WiFi отключен! Попытка переподключения...");
      connectToWiFi(); // Переподключаемся
      return;
    }
    
    // Проверяем RC522
    byte version = rfid.PCD_ReadRegister(rfid.VersionReg);
    if (version == 0x00 || version == 0xFF) {
      Serial.println("[STATUS][ERROR] RC522 не отвечает!");
      // Мигаем красным для индикации проблемы со считывателем
      if (millis() - lastErrorBlinkTime > ERROR_BLINK_INTERVAL) {
        lastErrorBlinkTime = millis();
        errorLedState = !errorLedState;
        digitalWrite(RED_LED_PIN, errorLedState ? HIGH : LOW);
        analogWrite(GREEN_LED_PIN, 0);
      }
    } else {
      Serial.printf("[STATUS] RC522 OK (версия: 0x%02X), WiFi OK (RSSI: %d dBm)\n", version, WiFi.RSSI());
      
      // Проверяем синхронизацию времени
      struct tm timeinfo;
      if (getLocalTime(&timeinfo)) {
        Serial.printf("[STATUS] Время синхронизировано: %02d:%02d:%02d\n", 
                     timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
        // Всё в порядке - зелёный светодиод в режиме ожидания
        analogWrite(GREEN_LED_PIN, STANDBY_BRIGHTNESS);
        digitalWrite(RED_LED_PIN, LOW);
      } else {
        Serial.println("[STATUS][ERROR] Время не синхронизировано!");
        // Пытаемся повторно синхронизировать время
        configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
        // Мигаем красным
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
    Serial.println("[CARD] RC522 считывание: " + serial + " (тип: " + cardType + ")");
  }
  
  // Общий код для обработки карты
  if (cardDetected && serial.length() > 0) {
      // Получение текущего времени
    struct tm timeinfo;
    if (WiFi.status() != WL_CONNECTED || !getLocalTime(&timeinfo)) {
      Serial.println("[CARD][ERROR] Не удалось получить время или WiFi не подключен");
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
      Serial.println("[API] Отправка данных на сервер...");
      Serial.println("[API] Карта: " + serial + ", Время: " + String(timeStr));
      response = sendToPythonServer(serial, timeStr);
      Serial.println("[API] Ответ получен");
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
  
  // Обработка OTA обновлений (ограничиваем частоту)
  if (ENABLE_OTA) {
    static unsigned long lastOTACheck = 0;
    if (millis() - lastOTACheck > 1000) { // Проверяем OTA только раз в секунду
      lastOTACheck = millis();
      ArduinoOTA.handle();
    }
  }
  
  delay(50); // Уменьшаем задержку для более быстрого считывания карт
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
