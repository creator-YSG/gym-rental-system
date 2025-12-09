/**
 * NFC Reader ESP32 - PN532 버전
 * 
 * 운동복 대여기용 NFC 리더
 * NFC UID를 읽어서 라즈베리파이로 시리얼 전송
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PN532.h>

// I2C 핀 설정
#define PN532_SDA 21
#define PN532_SCL 22

// PN532 초기화 (I2C)
Adafruit_PN532 nfc(PN532_SDA, PN532_SCL);

// LED (내장 LED 사용)
#define LED_PIN 2

void setup() {
  // 시리얼 초기화
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("NFC Reader ESP32 Starting...");
  
  // LED 초기화
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  // NFC 모듈 초기화
  nfc.begin();
  
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("ERROR: PN532 not found!");
    Serial.println("Check I2C connections (SDA=21, SCL=22)");
    
    // 에러 표시 (LED 깜빡임)
    while (1) {
      digitalWrite(LED_PIN, HIGH);
      delay(200);
      digitalWrite(LED_PIN, LOW);
      delay(200);
    }
  }
  
  Serial.print("PN532 Firmware Version: 0x");
  Serial.println(versiondata, HEX);
  
  // NFC 리더 설정
  nfc.SAMConfig();
  
  Serial.println("NFC Reader Ready. Waiting for cards...");
  
  // 준비 완료 표시 (LED 2초 켜기)
  digitalWrite(LED_PIN, HIGH);
  delay(2000);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;
  
  // NFC 태그 감지 (타임아웃 100ms)
  bool success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100);
  
  if (success) {
    // LED 켜기 (태그 감지)
    digitalWrite(LED_PIN, HIGH);
    
    // UID를 16진수 문자열로 변환
    String uidStr = "";
    for (uint8_t i = 0; i < uidLength; i++) {
      if (uid[i] < 0x10) uidStr += "0";
      uidStr += String(uid[i], HEX);
    }
    uidStr.toUpperCase();
    
    // 라즈베리파이로 전송 (JSON 형식)
    Serial.print("{\"nfc_uid\":\"");
    Serial.print(uidStr);
    Serial.println("\"}");
    
    // 중복 읽기 방지 (1초 대기)
    delay(1000);
    
    // LED 끄기
    digitalWrite(LED_PIN, LOW);
  }
  
  delay(100);
}

