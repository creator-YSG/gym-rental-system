/**
 * NFC Reader ESP32 - RC522 버전
 * 
 * 운동복 대여기용 NFC 리더
 * NFC UID를 읽어서 라즈베리파이로 시리얼 전송
 */

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>

// RC522 핀 설정 (SPI)
#define RST_PIN 22
#define SS_PIN  5

// RC522 초기화
MFRC522 mfrc522(SS_PIN, RST_PIN);

// LED (내장 LED 사용)
#define LED_PIN 2

void setup() {
  // 시리얼 초기화
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("NFC Reader ESP32 (RC522) Starting...");
  
  // LED 초기화
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  // SPI 초기화
  SPI.begin();
  
  // RC522 초기화
  mfrc522.PCD_Init();
  
  // 버전 확인
  byte version = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  if (version == 0x00 || version == 0xFF) {
    Serial.println("ERROR: RC522 not found!");
    Serial.println("Check SPI connections");
    Serial.println("RST=22, SS=5, MOSI=23, MISO=19, SCK=18");
    
    // 에러 표시 (LED 깜빡임)
    while (1) {
      digitalWrite(LED_PIN, HIGH);
      delay(200);
      digitalWrite(LED_PIN, LOW);
      delay(200);
    }
  }
  
  Serial.print("RC522 Version: 0x");
  Serial.println(version, HEX);
  Serial.println("NFC Reader Ready. Waiting for cards...");
  
  // 준비 완료 표시 (LED 2초 켜기)
  digitalWrite(LED_PIN, HIGH);
  delay(2000);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
  // 새 카드 감지
  if (!mfrc522.PICC_IsNewCardPresent()) {
    delay(100);
    return;
  }
  
  // UID 읽기
  if (!mfrc522.PICC_ReadCardSerial()) {
    delay(100);
    return;
  }
  
  // LED 켜기 (태그 감지)
  digitalWrite(LED_PIN, HIGH);
  
  // UID를 16진수 문자열로 변환
  String uidStr = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(mfrc522.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();
  
  // 라즈베리파이로 전송 (JSON 형식)
  Serial.print("{\"nfc_uid\":\"");
  Serial.print(uidStr);
  Serial.println("\"}");
  
  // 카드 읽기 종료
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  
  // 중복 읽기 방지 (1초 대기)
  delay(1000);
  
  // LED 끄기
  digitalWrite(LED_PIN, LOW);
}

