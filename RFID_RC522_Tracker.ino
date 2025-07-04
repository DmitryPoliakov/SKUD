/*
 * SKUD - Employee Tracking System with RFID RC522
 * 
 * Connection diagram for ESP32-C3-MINI-1:
 * +-----------+----------------+
 * | RC522     | ESP32-C3       |
 * +-----------+----------------+
 * | SDA (SS)  | GPIO5          |
 * | SCK       | GPIO2          |
 * | MOSI      | GPIO4          |
 * | MISO      | GPIO3          |
 * | GND       | GND            |
 * | RST       | GPIO6          |
 * | 3.3V      | 3.3V           |
 * +-----------+----------------+
 * 
 * LED Indicators:
 * - GREEN LED on GPIO10: Success indicator
 * - RED LED on GPIO9: Error indicator
 * 
 * LED Patterns:
 * - Slow fading green: Successful operation
 * - Medium alternating red/green: Warning
 * - Fast fading red: Error
 * 
 * Before using:
 * 1. Install MFRC522 library (Sketch -> Include Library -> Manage Libraries...)
 * 2. Set your WiFi credentials and Google Script URL below
 * 3. Make sure your RFID tags are Mifare standard (13.56 MHz)
 * 
 * This code reads RFID tags and sends their IDs to Google Sheets
 * for employee attendance tracking.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <time.h>
#include <ArduinoJson.h>

// WiFi settings
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Google Apps Script URL
const char* googleScriptURL = "YOUR_GOOGLE_SCRIPT_URL";

// RFID RC522 settings
#define RST_PIN         6    // RST pin for RFID RC522
#define SS_PIN          5     // SS (SDA) pin for RFID RC522
MFRC522 rfid(SS_PIN, RST_PIN); // Create MFRC522 instance

// LEDs
#define GREEN_LED_PIN 10  // Green LED pin
#define RED_LED_PIN 9    // Red LED pin

// Constants for smooth fading
#define FADE_STEPS 50     // Number of steps for smooth brightness change
#define FADE_DELAY_SLOW 15  // Delay for slow fading (ms)
#define FADE_DELAY_MEDIUM 8 // Delay for medium fading (ms)
#define FADE_DELAY_FAST 3   // Delay for fast fading (ms)

// NTP settings
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 10800; // GMT+3 (Moscow)
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  
  // LED setup
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  
  // Welcome indication at startup
  fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_MEDIUM);
  
  // Initialize SPI - для ESP32-C3 указываем нужные пины
  SPI.begin(2, 3, 4, 5); // SCK, MISO, MOSI, SS
  
  // Initialize RFID RC522
  rfid.PCD_Init();
  Serial.println("RFID reader initialized");
  
  // Show RC522 firmware version
  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("RFID reader version: 0x");
  Serial.println(v, HEX);
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi...");
    pulseLED(RED_LED_PIN, 1, FADE_DELAY_MEDIUM);
  }
  Serial.println("Connected to WiFi");
  fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_FAST);

  // Setup time
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Time synchronized");
}

void loop() {
  // Check for new card
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }
  
  // Successful key reading - brief green flash
  digitalWrite(GREEN_LED_PIN, HIGH);
  
  // Get card ID
  String serial = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) serial += "0";
    serial += String(rfid.uid.uidByte[i], HEX);
  }
  serial.toUpperCase();
  Serial.println("Card read: " + serial);
  
  // End operation with current card
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  // Get current time
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Failed to obtain time");
    fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST); // Fast red fading - error
    digitalWrite(GREEN_LED_PIN, LOW);
    return;
  }
  char timeStr[20];
  strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M", &timeinfo);

  // Send data and receive response
  String response = sendToGoogleSheets(serial, timeStr);
  
  // Process response
  if (response.length() > 0) {
    // Parse JSON response
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, response);
    
    if (!error) {
      String status = doc["status"];
      String message = doc["message"];
      
      Serial.println("Status: " + status);
      Serial.println("Message: " + message);
      
      if (status == "success") {
        String employee = doc["employee"];
        String event = doc["event"];
        String time = doc["time"];
        
        Serial.println("Employee: " + employee);
        Serial.println("Event: " + event);
        Serial.println("Time: " + time);
        
        // Successful operation - slow green fading
        fadeInOut(GREEN_LED_PIN, 2, FADE_DELAY_SLOW);
        
      } else if (status == "ignored") {
        // Warning - alternating red and green (medium fading)
        alternatingFade(GREEN_LED_PIN, RED_LED_PIN, 2, FADE_DELAY_MEDIUM);
        
      } else if (status == "unknown") {
        // Error - fast red fading
        fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
      }
    } else {
      Serial.println("JSON parsing error");
      // Critical error - fast red fading
      fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
    }
  } else {
    // Sending error - fast red fading
    fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
  }
  
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  delay(1000); // Delay before next reading
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
    // WiFi error - fast red fading
    fadeInOut(RED_LED_PIN, 3, FADE_DELAY_FAST);
  }
  
  return response;
}

/**
 * Smooth fade in and out for LED
 * @param pin - LED pin
 * @param cycles - Number of fading cycles
 * @param delayTime - Delay between steps (determines fading speed)
 */
void fadeInOut(int pin, int cycles, int delayTime) {
  for (int j = 0; j < cycles; j++) {
    // Brightness increase
    for (int i = 0; i <= FADE_STEPS; i++) {
      analogWrite(pin, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
    
    // Brightness decrease
    for (int i = FADE_STEPS; i >= 0; i--) {
      analogWrite(pin, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
  }
  digitalWrite(pin, LOW);
}

/**
 * LED pulsation (fast on, slow fade)
 * @param pin - LED pin
 * @param cycles - Number of pulsation cycles
 * @param delayTime - Delay between steps
 */
void pulseLED(int pin, int cycles, int delayTime) {
  for (int j = 0; j < cycles; j++) {
    // Fast on
    digitalWrite(pin, HIGH);
    delay(50);
    
    // Slow fade
    for (int i = FADE_STEPS; i >= 0; i--) {
      analogWrite(pin, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
  }
  digitalWrite(pin, LOW);
}

/**
 * Alternating smooth fading between two LEDs
 * @param pin1 - First LED pin
 * @param pin2 - Second LED pin
 * @param cycles - Number of alternation cycles
 * @param delayTime - Delay between steps
 */
void alternatingFade(int pin1, int pin2, int cycles, int delayTime) {
  for (int j = 0; j < cycles; j++) {
    // First LED increases, second decreases
    for (int i = 0; i <= FADE_STEPS; i++) {
      analogWrite(pin1, i * (255 / FADE_STEPS));
      analogWrite(pin2, (FADE_STEPS - i) * (255 / FADE_STEPS));
      delay(delayTime);
    }
    
    // First LED decreases, second increases
    for (int i = 0; i <= FADE_STEPS; i++) {
      analogWrite(pin1, (FADE_STEPS - i) * (255 / FADE_STEPS));
      analogWrite(pin2, i * (255 / FADE_STEPS));
      delay(delayTime);
    }
  }
  digitalWrite(pin1, LOW);
  digitalWrite(pin2, LOW);
}
