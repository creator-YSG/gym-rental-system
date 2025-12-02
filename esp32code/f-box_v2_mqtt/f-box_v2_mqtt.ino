/*
  F-BOX 운동복 대여기 펌웨어 v2.0
  - MQTT 통신 기능 추가
  - 라즈베리파이 MQTT 브로커와 연동
  
  기능:
  - SETUP 모드: AP + QR + 설정 웹서버 + NVS 저장
  - RUN 모드: Wi-Fi STA + MQTT 통신 + 모터/리미트/LCD 동작
  - MQTT 명령 수신 (DISPENSE, SET_STOCK, STATUS, STOP, LOCK, UNLOCK, HOME, REBOOT, CLEAR_ERROR)
  - MQTT 이벤트 발행 (boot_complete, heartbeat, dispense_complete, door_opened/closed, stock_updated 등)
  - 재고 관리, 잠금 기능
  
  하드웨어:
  - ESP32
  - TB6600 + NEMA17 + GT2 20T, 1/2 스텝
  - ST7789 240x320 TFT (Adafruit_GFX)
  - 리미트 스위치 2개
      * LIMIT_FLOOR (32): 1층 도달, C->GND, NO->32, LOW=눌림
      * LIMIT_DOOR  (33): 문 닫힘, C->GND, NO->33, LOW=문 닫힘
  
  필요 라이브러리:
  - PubSubClient (MQTT)
  - Adafruit GFX Library
  - Adafruit ST7789 Library
  - ArduinoJson
*/

#include <WiFi.h>  
#include <WebServer.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <Fonts/FreeSansBold24pt7b.h>

// ESP32 코어에 포함된 QR 코드 라이브러리
#include "qrcode.h"

// =============================
// 펌웨어 버전
// =============================
#define FIRMWARE_VERSION "v2.0.0"

// =============================
// 1. 공통 상수 / 핀 / 전역 변수
// =============================

// AP(Access Point) 설정 (설정 모드 전용)
const char* AP_SSID     = "F-BOX-01";
const char* AP_PASSWORD = "12345678";

// QR로 인코딩할 URL (AP 기본 IP)
const char* QR_URL      = "http://192.168.4.1";

// ST7789 TFT 핀맵
#define TFT_CS   5
#define TFT_DC   16
#define TFT_RST  17
#define TFT_BL   4

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);

// HTTP 서버 (설정 모드에서만 사용)
WebServer server(80);

// WiFi & MQTT 클라이언트
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// NVS(Preferences) 네임스페이스 이름
const char* PREF_NAMESPACE = "fbox_cfg";
Preferences prefs;

// 시스템 상태 정의
enum SystemState {
  STATE_SETUP = 0,
  STATE_RUN,
  STATE_ERROR
};

SystemState currentState = STATE_SETUP;

// =============================
// 2. 설정 구조체 AppConfig
// =============================

struct AppConfig {
  char wifiSsid[32];
  char wifiPass[64];
  char size[8];           // "M", "L", "XL", "105" 등
  char deviceId[32];      // "FBOX-UPPER-105" 같은 기기 ID
  char brokerHost[64];    // MQTT 브로커 주소 (라즈베리파이 IP)
  uint16_t brokerPort;    // 기본 1883
};

AppConfig g_config;

// =============================
// 3. 재고 및 상태 변수
// =============================

// 재고 관리
int g_stock = 0;                    // 현재 재고
const int MAX_STOCK = 30;           // 최대 재고
const int LOW_STOCK_THRESHOLD = 5;  // 재고 부족 경고 기준

// 기기 잠금 상태
bool g_locked = false;

// 에러 상태
bool g_hasError = false;
char g_errorMessage[64] = "";

// MQTT 토픽 (런타임에 구성)
char g_topicCmd[64];     // fbox/{deviceId}/cmd
char g_topicStatus[64];  // fbox/{deviceId}/status

// Heartbeat 관련
unsigned long lastHeartbeatTime = 0;
const unsigned long HEARTBEAT_INTERVAL = 60000;  // 1분

// Wi-Fi 재연결 관련
unsigned long lastWifiCheckTime = 0;
const unsigned long WIFI_CHECK_INTERVAL = 10000;  // 10초

// 긴급 정지 플래그
volatile bool g_emergencyStop = false;

// 토출 진행 중 플래그
bool g_dispensing = false;

// =============================
// 4. 모터/리미트/LCD (RUN 모드용)
// =============================

// 모터(TB6600) 핀 설정
const int PIN_STEP = 25;
const int PIN_DIR  = 26;
const int PIN_ENA  = 27;

// 리미트 스위치 핀
const int LIMIT_FLOOR = 32;  // 1층 도달 스위치 (LOW=도달)
const int LIMIT_DOOR  = 33;  // 문 닫힘 스위치 (LOW=문 닫힘)

// 모터 / 기구 설정
const int   STEPS_PER_REV  = 400;
const float PULLEY_TOOTH   = 20.0;
const float BELT_PITCH     = 2.0;
const float MM_PER_REV     = PULLEY_TOOTH * BELT_PITCH;
const float STEPS_PER_MM   = (float)STEPS_PER_REV / MM_PER_REV;
const float DISPENSE_DIST_MM = 15.0;  // 토출 시 이동 거리
const int   STEP_DELAY_US  = 500;

// 방향 정의
const int DIR_FORWARD = LOW;   // 정방향 (토출 방향)
const int DIR_BACK    = HIGH;  // 역방향

// 색상 정의 (16bit RGB565)
uint16_t COLOR_MINT     = 0;
uint16_t COLOR_SOFT_RED = 0;
uint16_t COLOR_YELLOW   = 0;
uint16_t COLOR_GREEN    = 0;

// 리미트 상태
int lastDoorState  = HIGH;
int lastFloorState = HIGH;

// =============================
// 5. 함수 프로토타입
// =============================

// NVS 설정 관련
bool loadConfig(AppConfig &cfg);
bool saveConfig(const AppConfig &cfg);
void clearConfig();

// LCD 표시 관련
void drawSizeOnBackground(uint16_t bgColor, uint16_t textColor);
void showIdleScreen();
void showSetupScreen();
void showWifiErrorScreen();
void showStatusOnLCD(const char* status);
void flashPattern(uint16_t color, uint16_t textColor, unsigned long totalDurationMs);

// 모터 제어 관련
void move_mm(float mm, int dirState);
void homeToFirstFloor();
bool dispenseOne();

// MQTT 관련
void setupMqttTopics();
void mqttCallback(char* topic, byte* payload, unsigned int length);
bool connectMqtt();
void publishEvent(const char* eventJson);
void publishBootComplete();
void publishHeartbeat();
void publishStatus();
void publishDispenseComplete();
void publishDispenseFailed(const char* reason);
void publishDoorOpened();
void publishDoorClosed();
void publishStockUpdated(const char* source);
void publishStockLow();
void publishStockEmpty();
void publishError(const char* errorCode, const char* errorMessage);
void publishHomeFailed(const char* reason);
void publishWifiReconnected();
void publishMqttReconnected();

// 명령 처리 관련
void handleCommand(const char* cmd, JsonDocument& doc);
void handleDispense();
void handleSetStock(int stock);
void handleStatusRequest();
void handleStop();
void handleLock();
void handleUnlock();
void handleHome();
void handleReboot();
void handleClearError();

// HTTP 핸들러 관련
void handleRoot();
void handleSave();
void handleNotFound();
String makeConfigPage(const AppConfig &cfg);

// 상태 전환 관련
void startSetupMode();
void startRunMode();
void loopSetupMode();
void loopRunMode();

// =============================
// 6. NVS 설정 함수
// =============================

bool loadConfig(AppConfig &cfg) {
  prefs.begin(PREF_NAMESPACE, true);
  bool valid = prefs.getBool("valid", false);

  if (!valid) {
    prefs.end();
    Serial.println("[CONFIG] 저장된 설정 없음");
    return false;
  }

  String ssid  = prefs.getString("wifiSsid", "");
  String pass  = prefs.getString("wifiPass", "");
  String size  = prefs.getString("size",     "");
  String devId = prefs.getString("deviceId", "");
  String host  = prefs.getString("brokerHost", "");
  uint32_t port = prefs.getUInt("brokerPort", 1883);
  
  // 재고 로드 (전원 꺼져도 유지)
  g_stock = prefs.getInt("stock", 0);

  prefs.end();

  ssid.toCharArray(cfg.wifiSsid, sizeof(cfg.wifiSsid));
  pass.toCharArray(cfg.wifiPass, sizeof(cfg.wifiPass));
  size.toCharArray(cfg.size,     sizeof(cfg.size));
  devId.toCharArray(cfg.deviceId,sizeof(cfg.deviceId));
  host.toCharArray(cfg.brokerHost, sizeof(cfg.brokerHost));
  cfg.brokerPort = (uint16_t)port;

  Serial.println("[CONFIG] 설정 로드 완료");
  Serial.print("  SSID: "); Serial.println(cfg.wifiSsid);
  Serial.print("  SIZE: "); Serial.println(cfg.size);
  Serial.print("  DEV : "); Serial.println(cfg.deviceId);
  Serial.print("  HOST: "); Serial.println(cfg.brokerHost);
  Serial.print("  PORT: "); Serial.println(cfg.brokerPort);
  Serial.print("  STOCK: "); Serial.println(g_stock);

  return true;
}

bool saveConfig(const AppConfig &cfg) {
  prefs.begin(PREF_NAMESPACE, false);

  prefs.putBool("valid", true);
  prefs.putString("wifiSsid",   cfg.wifiSsid);
  prefs.putString("wifiPass",   cfg.wifiPass);
  prefs.putString("size",       cfg.size);
  prefs.putString("deviceId",   cfg.deviceId);
  prefs.putString("brokerHost", cfg.brokerHost);
  prefs.putUInt("brokerPort",   cfg.brokerPort);

  prefs.end();

  Serial.println("[CONFIG] 설정 저장 완료");
  return true;
}

void saveStock() {
  prefs.begin(PREF_NAMESPACE, false);
  prefs.putInt("stock", g_stock);
  prefs.end();
}

void clearConfig() {
  prefs.begin(PREF_NAMESPACE, false);
  prefs.clear();
  prefs.end();
  Serial.println("[CONFIG] 설정 전체 삭제");
}

// =============================
// 7. LCD 표시 함수
// =============================

void drawSizeOnBackground(uint16_t bgColor, uint16_t textColor) {
  tft.fillScreen(bgColor);

  tft.setFont(&FreeSansBold24pt7b);
  tft.setTextColor(textColor);
  uint8_t textSize = 3;
  tft.setTextSize(textSize);

  const char* textToShow = (strlen(g_config.size) > 0) ? g_config.size : "---";

  int16_t x1, y1;
  uint16_t w, h;
  tft.getTextBounds(textToShow, 0, 0, &x1, &y1, &w, &h);

  uint16_t screenW = tft.width();
  uint16_t screenH = tft.height();

  int16_t x = (screenW - w) / 2 - x1;
  int16_t y = (screenH - h) / 2 - y1;

  tft.setCursor(x, y);
  tft.print(textToShow);
}

void showIdleScreen() {
  digitalWrite(TFT_BL, HIGH);
  
  // 잠금 상태이면 노란색 배경
  if (g_locked) {
    drawSizeOnBackground(COLOR_YELLOW, ST77XX_BLACK);
  } 
  // 재고 없으면 빨간 배경
  else if (g_stock <= 0) {
    drawSizeOnBackground(ST77XX_RED, ST77XX_WHITE);
  }
  // 재고 부족이면 주황색 배경
  else if (g_stock <= LOW_STOCK_THRESHOLD) {
    uint16_t orange = tft.color565(255, 165, 0);
    drawSizeOnBackground(orange, ST77XX_WHITE);
  }
  // 정상 상태
  else {
    drawSizeOnBackground(ST77XX_BLACK, ST77XX_WHITE);
  }
}

void showStatusOnLCD(const char* status) {
  digitalWrite(TFT_BL, HIGH);
  tft.fillScreen(ST77XX_BLACK);
  
  tft.setFont();
  tft.setTextSize(2);
  tft.setTextColor(ST77XX_WHITE);
  
  tft.setCursor(10, 50);
  tft.print(g_config.size);
  
  tft.setCursor(10, 100);
  tft.print("Stock: ");
  tft.print(g_stock);
  
  tft.setCursor(10, 130);
  tft.print("Status: ");
  tft.print(status);
  
  if (g_locked) {
    tft.setCursor(10, 160);
    tft.setTextColor(ST77XX_YELLOW);
    tft.print("LOCKED");
  }
}

void flashPattern(uint16_t color, uint16_t textColor, unsigned long totalDurationMs) {
  unsigned long startTime = millis();

  drawSizeOnBackground(color, textColor);

  const unsigned long fastBlinkInterval = 80;
  const unsigned long restInterval      = 350;

  while (millis() - startTime < totalDurationMs) {
    // 긴급 정지 체크
    if (g_emergencyStop) {
      g_emergencyStop = false;
      break;
    }
    
    for (int i = 0; i < 4; i++) {
      if (millis() - startTime >= totalDurationMs || g_emergencyStop) break;
      digitalWrite(TFT_BL, HIGH);
      delay(fastBlinkInterval);
      digitalWrite(TFT_BL, LOW);
      delay(fastBlinkInterval);
    }

    if (millis() - startTime >= totalDurationMs || g_emergencyStop) break;

    digitalWrite(TFT_BL, LOW);
    delay(restInterval);

    for (int i = 0; i < 4; i++) {
      if (millis() - startTime >= totalDurationMs || g_emergencyStop) break;
      digitalWrite(TFT_BL, HIGH);
      delay(fastBlinkInterval);
      digitalWrite(TFT_BL, LOW);
      delay(fastBlinkInterval);
    }

    if (millis() - startTime >= totalDurationMs || g_emergencyStop) break;

    digitalWrite(TFT_BL, LOW);
    delay(restInterval);
  }

  digitalWrite(TFT_BL, HIGH);
  showIdleScreen();
}

// QR 코드 표시 콜백
void drawQRCodeOnTFT(esp_qrcode_handle_t qrcode) {
  int size = esp_qrcode_get_size(qrcode);
  const int scale = 6;

  int qrPixelSize = size * scale;
  int16_t screenW = tft.width();
  int16_t screenH = tft.height();

  int16_t offsetX = (screenW - qrPixelSize) / 2;
  int16_t offsetY = (screenH - qrPixelSize) / 2 + 10;

  tft.fillRect(offsetX - 4, offsetY - 4,
               qrPixelSize + 8, qrPixelSize + 8,
               ST77XX_WHITE);

  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      int16_t px = offsetX + x * scale;
      int16_t py = offsetY + y * scale;

      if (esp_qrcode_get_module(qrcode, x, y)) {
        tft.fillRect(px, py, scale, scale, ST77XX_BLACK);
      } else {
        tft.fillRect(px, py, scale, scale, ST77XX_WHITE);
      }
    }
  }
}

void showSetupScreen() {
  tft.fillScreen(ST77XX_WHITE);

  tft.setFont();
  tft.setTextColor(ST77XX_BLACK);

  tft.setTextSize(2);
  tft.setCursor(10, 20);
  tft.print("SETUP MODE");

  tft.setTextSize(1);
  tft.setCursor(10, 50);
  tft.print("1) Connect Wi-Fi 'F-BOX-01'");
  tft.setCursor(10, 65);
  tft.print("2) Then scan QR code");

  esp_qrcode_config_t cfg = ESP_QRCODE_CONFIG_DEFAULT();
  cfg.display_func       = drawQRCodeOnTFT;
  cfg.max_qrcode_version = 10;
  cfg.qrcode_ecc_level   = ESP_QRCODE_ECC_LOW;

  (void)esp_qrcode_generate(&cfg, QR_URL);
}

void showWifiErrorScreen() {
  tft.fillScreen(ST77XX_RED);
  tft.setFont();
  tft.setTextSize(2);
  tft.setTextColor(ST77XX_WHITE);
  tft.setCursor(10, 40);
  tft.print("WiFi ERROR");

  tft.setTextSize(1);
  tft.setCursor(10, 80);
  tft.print("Check SSID / PASS");
  tft.setCursor(10, 95);
  tft.print("Re-enter in SETUP");
}

void showMqttConnectingScreen() {
  tft.fillScreen(ST77XX_BLUE);
  tft.setFont();
  tft.setTextSize(2);
  tft.setTextColor(ST77XX_WHITE);
  tft.setCursor(10, 60);
  tft.print("MQTT");
  tft.setCursor(10, 90);
  tft.print("Connecting...");
}

void showDispensingScreen() {
  tft.fillScreen(COLOR_GREEN);
  tft.setFont(&FreeSansBold24pt7b);
  tft.setTextSize(2);
  tft.setTextColor(ST77XX_WHITE);
  
  const char* text = g_config.size;
  int16_t x1, y1;
  uint16_t w, h;
  tft.getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
  
  int16_t x = (tft.width() - w) / 2 - x1;
  int16_t y = (tft.height() - h) / 2 - y1;
  
  tft.setCursor(x, y);
  tft.print(text);
}

// =============================
// 8. 모터 제어 함수
// =============================

void move_mm(float mm, int dirState) {
  digitalWrite(PIN_DIR, dirState);
  delayMicroseconds(100);

  int stepsToMove = (int)(mm * STEPS_PER_MM + 0.5);

  for (int i = 0; i < stepsToMove; i++) {
    // 긴급 정지 체크
    if (g_emergencyStop) {
      Serial.println("[MOTOR] 긴급 정지!");
      g_emergencyStop = false;
      return;
    }
    
    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(STEP_DELAY_US);
  }
}

void homeToFirstFloor() {
  Serial.println("[HOME] 1층 복귀 시작");

  const long MAX_STEPS = 10000;

  digitalWrite(PIN_DIR, DIR_FORWARD);
  delayMicroseconds(100);

  for (long i = 0; i < MAX_STEPS; i++) {
    // 긴급 정지 체크
    if (g_emergencyStop) {
      Serial.println("[HOME] 긴급 정지로 중단");
      g_emergencyStop = false;
      publishHomeFailed("emergency_stop");
      return;
    }
    
    if (digitalRead(LIMIT_FLOOR) == LOW) {
      Serial.println("[HOME] 1층 도달, 자동 이동 종료");
      break;
    }

    if (digitalRead(LIMIT_DOOR) == HIGH) {
      Serial.println("[HOME] 문 열림 감지, 자동 이동 중단");
      publishHomeFailed("door_opened");
      return;
    }

    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(STEP_DELAY_US);
  }

  if (digitalRead(LIMIT_FLOOR) == LOW) {
    Serial.println("[STATE] 1층 도달 완료");
  } else {
    Serial.println("[HOME] MAX_STEPS 도달로 홈 미완료");
    publishHomeFailed("max_steps_reached");
  }
}

bool dispenseOne() {
  Serial.println("[DISPENSE] 토출 시작");
  
  // 잠금 상태 체크
  if (g_locked) {
    Serial.println("[DISPENSE] 기기 잠금 상태 - 토출 거부");
    publishDispenseFailed("device_locked");
    return false;
  }
  
  // 재고 체크
  if (g_stock <= 0) {
    Serial.println("[DISPENSE] 재고 없음 - 토출 거부");
    publishDispenseFailed("no_stock");
    return false;
  }
  
  // 문 상태 체크
  if (digitalRead(LIMIT_DOOR) == HIGH) {
    Serial.println("[DISPENSE] 문 열림 상태 - 토출 거부");
    publishDispenseFailed("door_open");
    return false;
  }
  
  g_dispensing = true;
  showDispensingScreen();
  
  // 토출 동작: 정방향으로 이동
  move_mm(DISPENSE_DIST_MM, DIR_FORWARD);
  
  // 긴급 정지가 발생했는지 체크
  if (g_emergencyStop) {
    g_dispensing = false;
    g_emergencyStop = false;
    publishDispenseFailed("emergency_stop");
    showIdleScreen();
    return false;
  }
  
  // 재고 감소
  g_stock--;
  saveStock();
  
  g_dispensing = false;
  
  Serial.print("[DISPENSE] 토출 완료, 남은 재고: ");
  Serial.println(g_stock);
  
  // 성공 이벤트 발행
  publishDispenseComplete();
  
  // 재고 경고 체크
  if (g_stock == 0) {
    publishStockEmpty();
  } else if (g_stock <= LOW_STOCK_THRESHOLD) {
    publishStockLow();
  }
  
  // 깜빡임 패턴 후 idle 화면으로
  flashPattern(COLOR_GREEN, ST77XX_WHITE, 3000);
  
  return true;
}

// =============================
// 9. MQTT 함수
// =============================

void setupMqttTopics() {
  snprintf(g_topicCmd, sizeof(g_topicCmd), "fbox/%s/cmd", g_config.deviceId);
  snprintf(g_topicStatus, sizeof(g_topicStatus), "fbox/%s/status", g_config.deviceId);
  
  Serial.print("[MQTT] CMD Topic: "); Serial.println(g_topicCmd);
  Serial.print("[MQTT] STATUS Topic: "); Serial.println(g_topicStatus);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // 페이로드를 문자열로 변환
  char message[256];
  if (length >= sizeof(message)) {
    length = sizeof(message) - 1;
  }
  memcpy(message, payload, length);
  message[length] = '\0';
  
  Serial.print("[MQTT] 메시지 수신: ");
  Serial.println(message);
  
  // JSON 파싱
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.print("[MQTT] JSON 파싱 실패: ");
    Serial.println(error.c_str());
    publishError("E002", "Invalid JSON format");
    return;
  }
  
  const char* cmd = doc["cmd"];
  if (cmd == nullptr) {
    Serial.println("[MQTT] cmd 필드 없음");
    publishError("E001", "Missing cmd field");
    return;
  }
  
  handleCommand(cmd, doc);
}

bool connectMqtt() {
  if (mqttClient.connected()) {
    return true;
  }
  
  Serial.print("[MQTT] 연결 시도: ");
  Serial.print(g_config.brokerHost);
  Serial.print(":");
  Serial.println(g_config.brokerPort);
  
  mqttClient.setServer(g_config.brokerHost, g_config.brokerPort);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);  // 버퍼 크기 증가
  
  // 연결 시도 (클라이언트 ID로 deviceId 사용)
  if (mqttClient.connect(g_config.deviceId)) {
    Serial.println("[MQTT] 연결 성공");
    
    // 명령 토픽 구독
    if (mqttClient.subscribe(g_topicCmd, 1)) {  // QoS 1
      Serial.print("[MQTT] Subscribe: ");
      Serial.println(g_topicCmd);
    } else {
      Serial.println("[MQTT] Subscribe 실패");
    }
    
    return true;
  } else {
    Serial.print("[MQTT] 연결 실패, 에러 코드: ");
    Serial.println(mqttClient.state());
    return false;
  }
}

void publishEvent(const char* eventJson) {
  if (!mqttClient.connected()) {
    Serial.println("[MQTT] 연결 안됨 - 이벤트 발행 실패");
    return;
  }
  
  bool success = mqttClient.publish(g_topicStatus, eventJson, false);  // retain = false
  if (success) {
    Serial.print("[MQTT] Publish: ");
    Serial.println(eventJson);
  } else {
    Serial.println("[MQTT] Publish 실패");
  }
}

unsigned long getTimestamp() {
  // 실제 시간이 없으므로 millis() 기반 상대 시간 사용
  // 나중에 NTP 동기화 추가 가능
  return millis() / 1000;
}

void publishBootComplete() {
  JsonDocument doc;
  doc["event"] = "boot_complete";
  doc["deviceId"] = g_config.deviceId;
  doc["size"] = g_config.size;
  doc["stock"] = g_stock;
  doc["firmwareVersion"] = FIRMWARE_VERSION;
  doc["ipAddress"] = WiFi.localIP().toString();
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishHeartbeat() {
  JsonDocument doc;
  doc["event"] = "heartbeat";
  doc["deviceId"] = g_config.deviceId;
  doc["stock"] = g_stock;
  doc["doorState"] = (digitalRead(LIMIT_DOOR) == LOW) ? "closed" : "open";
  doc["locked"] = g_locked;
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishStatus() {
  JsonDocument doc;
  doc["event"] = "status";
  doc["deviceId"] = g_config.deviceId;
  doc["size"] = g_config.size;
  doc["stock"] = g_stock;
  doc["doorState"] = (digitalRead(LIMIT_DOOR) == LOW) ? "closed" : "open";
  doc["floorState"] = (digitalRead(LIMIT_FLOOR) == LOW) ? "reached" : "moving";
  doc["locked"] = g_locked;
  doc["wifiRssi"] = WiFi.RSSI();
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishDispenseComplete() {
  JsonDocument doc;
  doc["event"] = "dispense_complete";
  doc["deviceId"] = g_config.deviceId;
  doc["stock"] = g_stock;
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishDispenseFailed(const char* reason) {
  JsonDocument doc;
  doc["event"] = "dispense_failed";
  doc["deviceId"] = g_config.deviceId;
  doc["reason"] = reason;
  doc["stock"] = g_stock;
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishDoorOpened() {
  JsonDocument doc;
  doc["event"] = "door_opened";
  doc["deviceId"] = g_config.deviceId;
  doc["timestamp"] = getTimestamp();
  
  char json[192];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishDoorClosed() {
  JsonDocument doc;
  doc["event"] = "door_closed";
  doc["deviceId"] = g_config.deviceId;
  doc["stock"] = g_stock;
  doc["sensorAvailable"] = false;  // 재고 센서 없음
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishStockUpdated(const char* source) {
  JsonDocument doc;
  doc["event"] = "stock_updated";
  doc["deviceId"] = g_config.deviceId;
  doc["stock"] = g_stock;
  doc["source"] = source;
  doc["needsVerification"] = false;
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishStockLow() {
  JsonDocument doc;
  doc["event"] = "stock_low";
  doc["deviceId"] = g_config.deviceId;
  doc["stock"] = g_stock;
  doc["timestamp"] = getTimestamp();
  
  char json[192];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishStockEmpty() {
  JsonDocument doc;
  doc["event"] = "stock_empty";
  doc["deviceId"] = g_config.deviceId;
  doc["stock"] = 0;
  doc["timestamp"] = getTimestamp();
  
  char json[192];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishError(const char* errorCode, const char* errorMsg) {
  JsonDocument doc;
  doc["event"] = "error";
  doc["deviceId"] = g_config.deviceId;
  doc["errorCode"] = errorCode;
  doc["errorMessage"] = errorMsg;
  doc["timestamp"] = getTimestamp();
  
  char json[256];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishHomeFailed(const char* reason) {
  JsonDocument doc;
  doc["event"] = "home_failed";
  doc["deviceId"] = g_config.deviceId;
  doc["reason"] = reason;
  doc["timestamp"] = getTimestamp();
  
  char json[192];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishWifiReconnected() {
  JsonDocument doc;
  doc["event"] = "wifi_reconnected";
  doc["deviceId"] = g_config.deviceId;
  doc["ipAddress"] = WiFi.localIP().toString();
  doc["timestamp"] = getTimestamp();
  
  char json[192];
  serializeJson(doc, json);
  publishEvent(json);
}

void publishMqttReconnected() {
  JsonDocument doc;
  doc["event"] = "mqtt_reconnected";
  doc["deviceId"] = g_config.deviceId;
  doc["timestamp"] = getTimestamp();
  
  char json[128];
  serializeJson(doc, json);
  publishEvent(json);
}

// =============================
// 10. 명령 처리 함수
// =============================

void handleCommand(const char* cmd, JsonDocument& doc) {
  Serial.print("[CMD] 명령 처리: ");
  Serial.println(cmd);
  
  if (strcmp(cmd, "DISPENSE") == 0) {
    handleDispense();
  }
  else if (strcmp(cmd, "STATUS") == 0) {
    handleStatusRequest();
  }
  else if (strcmp(cmd, "SET_STOCK") == 0) {
    int stock = doc["stock"] | -1;
    if (stock >= 0 && stock <= MAX_STOCK) {
      handleSetStock(stock);
    } else {
      publishError("E002", "Invalid stock value");
    }
  }
  else if (strcmp(cmd, "STOP") == 0) {
    handleStop();
  }
  else if (strcmp(cmd, "LOCK") == 0) {
    handleLock();
  }
  else if (strcmp(cmd, "UNLOCK") == 0) {
    handleUnlock();
  }
  else if (strcmp(cmd, "HOME") == 0) {
    handleHome();
  }
  else if (strcmp(cmd, "REBOOT") == 0) {
    handleReboot();
  }
  else if (strcmp(cmd, "CLEAR_ERROR") == 0) {
    handleClearError();
  }
  else {
    Serial.print("[CMD] 알 수 없는 명령: ");
    Serial.println(cmd);
    publishError("E001", "Unknown command received");
  }
}

void handleDispense() {
  if (g_dispensing) {
    Serial.println("[CMD] 이미 토출 중");
    publishError("E004", "Already dispensing");
    return;
  }
  
  dispenseOne();
}

void handleSetStock(int stock) {
  g_stock = stock;
  saveStock();
  
  Serial.print("[CMD] 재고 설정: ");
  Serial.println(g_stock);
  
  publishStockUpdated("manual");
  showIdleScreen();
  
  // 재고 경고 체크
  if (g_stock == 0) {
    publishStockEmpty();
  } else if (g_stock <= LOW_STOCK_THRESHOLD) {
    publishStockLow();
  }
}

void handleStatusRequest() {
  publishStatus();
}

void handleStop() {
  Serial.println("[CMD] 긴급 정지 명령");
  g_emergencyStop = true;
  
  // 즉시 상태 보고
  publishStatus();
}

void handleLock() {
  g_locked = true;
  Serial.println("[CMD] 기기 잠금");
  showIdleScreen();
  publishStatus();
}

void handleUnlock() {
  g_locked = false;
  Serial.println("[CMD] 기기 잠금 해제");
  showIdleScreen();
  publishStatus();
}

void handleHome() {
  Serial.println("[CMD] 강제 홈 복귀");
  
  // 문이 닫혀있을 때만 홈 복귀
  if (digitalRead(LIMIT_DOOR) == LOW) {
    homeToFirstFloor();
    publishDoorClosed();
  } else {
    Serial.println("[CMD] 문이 열려있어 홈 복귀 불가");
    publishHomeFailed("door_open");
  }
  
  showIdleScreen();
}

void handleReboot() {
  Serial.println("[CMD] 재부팅 명령 수신 - 1초 후 재부팅");
  delay(1000);
  ESP.restart();
}

void handleClearError() {
  g_hasError = false;
  memset(g_errorMessage, 0, sizeof(g_errorMessage));
  Serial.println("[CMD] 에러 상태 초기화");
  showIdleScreen();
  publishStatus();
}

// =============================
// 11. HTTP 핸들러 (설정 모드용)
// =============================

String makeConfigPage(const AppConfig &cfg) {
  String html = "";
  html += "<!DOCTYPE html><html lang='ko'><head>";
  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>F-BOX 설정</title>";
  html += "<style>";
  html += "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif; padding:16px; max-width:480px; margin:auto; background:#f5f5f5;}";
  html += ".card{background:white; border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.1);}";
  html += "h1{color:#333; margin-bottom:8px;}";
  html += "p{color:#666; font-size:14px;}";
  html += "label{display:block; margin-top:16px; font-weight:600; color:#333;}";
  html += "input,select{width:100%; padding:12px; margin-top:6px; box-sizing:border-box; border:1px solid #ddd; border-radius:8px; font-size:16px;}";
  html += "input:focus{outline:none; border-color:#007AFF;}";
  html += "button{width:100%; margin-top:24px; padding:14px; background:#007AFF; color:white; border:none; border-radius:8px; font-size:16px; font-weight:600; cursor:pointer;}";
  html += "button:hover{background:#0056b3;}";
  html += ".version{text-align:center; color:#999; font-size:12px; margin-top:20px;}";
  html += "</style>";
  html += "</head><body>";
  
  html += "<div class='card'>";
  html += "<h1>F-BOX 설정</h1>";
  html += "<p>운동복 대여기 설정을 입력하세요.</p>";
  html += "</div>";
  
  html += "<div class='card'>";
  html += "<form method='POST' action='/save'>";

  // Wi-Fi SSID
  html += "<label for='wifiSsid'>Wi-Fi SSID</label>";
  html += "<input type='text' id='wifiSsid' name='wifiSsid' value='";
  html += cfg.wifiSsid;
  html += "' placeholder='헬스장 Wi-Fi 이름' required>";

  // Wi-Fi Password
  html += "<label for='wifiPass'>Wi-Fi Password</label>";
  html += "<input type='password' id='wifiPass' name='wifiPass' value='";
  html += cfg.wifiPass;
  html += "' placeholder='Wi-Fi 비밀번호' required>";

  // Size
  html += "<label for='size'>사이즈</label>";
  html += "<input type='text' id='size' name='size' value='";
  html += cfg.size;
  html += "' placeholder='예: 105, M, L, XL' required>";

  // Device ID
  html += "<label for='deviceId'>Device ID</label>";
  html += "<input type='text' id='deviceId' name='deviceId' value='";
  html += cfg.deviceId;
  html += "' placeholder='예: FBOX-UPPER-105' required>";

  // Broker Host
  html += "<label for='brokerHost'>MQTT 브로커 주소</label>";
  html += "<input type='text' id='brokerHost' name='brokerHost' value='";
  html += cfg.brokerHost;
  html += "' placeholder='라즈베리파이 IP (예: 192.168.0.10)' required>";

  // Broker Port
  html += "<label for='brokerPort'>MQTT 포트</label>";
  html += "<input type='number' id='brokerPort' name='brokerPort' value='";
  html += String(cfg.brokerPort == 0 ? 1883 : cfg.brokerPort);
  html += "' required>";
  
  // 초기 재고
  html += "<label for='stock'>초기 재고 수량</label>";
  html += "<input type='number' id='stock' name='stock' value='0' min='0' max='30' placeholder='0~30'>";

  html += "<button type='submit'>설정 저장</button>";
  html += "</form>";
  html += "</div>";

  html += "<p class='version'>Firmware: ";
  html += FIRMWARE_VERSION;
  html += "</p>";
  
  html += "</body></html>";
  return html;
}

void handleRoot() {
  Serial.println("[HTTP] GET /");
  server.send(200, "text/html", makeConfigPage(g_config));
}

void handleSave() {
  Serial.println("[HTTP] POST /save");

  String ssid  = server.arg("wifiSsid");
  String pass  = server.arg("wifiPass");
  String size  = server.arg("size");
  String devId = server.arg("deviceId");
  String host  = server.arg("brokerHost");
  String portS = server.arg("brokerPort");
  String stockS = server.arg("stock");

  if (ssid.length() == 0 || pass.length() == 0 || devId.length() == 0 || host.length() == 0) {
    server.send(400, "text/plain", "필수 값이 비어 있습니다.");
    return;
  }

  ssid.toCharArray(g_config.wifiSsid, sizeof(g_config.wifiSsid));
  pass.toCharArray(g_config.wifiPass, sizeof(g_config.wifiPass));
  size.toCharArray(g_config.size,     sizeof(g_config.size));
  devId.toCharArray(g_config.deviceId,sizeof(g_config.deviceId));
  host.toCharArray(g_config.brokerHost, sizeof(g_config.brokerHost));
  g_config.brokerPort = (uint16_t)(portS.toInt() > 0 ? portS.toInt() : 1883);
  
  // 초기 재고 설정
  int initialStock = stockS.toInt();
  if (initialStock >= 0 && initialStock <= MAX_STOCK) {
    g_stock = initialStock;
  }

  saveConfig(g_config);
  saveStock();

  String html = "";
  html += "<!DOCTYPE html><html lang='ko'><head>";
  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>설정 저장 완료</title>";
  html += "<style>";
  html += "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif; padding:20px; text-align:center; background:#f5f5f5;}";
  html += ".card{background:white; border-radius:12px; padding:30px; max-width:400px; margin:40px auto; box-shadow:0 2px 8px rgba(0,0,0,0.1);}";
  html += ".icon{font-size:48px; margin-bottom:16px;}";
  html += "h1{color:#28a745; margin-bottom:12px;}";
  html += "p{color:#666;}";
  html += "</style>";
  html += "</head><body>";
  html += "<div class='card'>";
  html += "<div class='icon'>✓</div>";
  html += "<h1>설정 완료</h1>";
  html += "<p>보드가 자동으로 재부팅됩니다.</p>";
  html += "<p>MQTT 브로커에 연결 후 운영 모드로 전환됩니다.</p>";
  html += "</div>";
  html += "</body></html>";

  server.send(200, "text/html", html);

  Serial.println("[HTTP] 설정 저장 완료 → 1초 후 자동 재부팅");
  delay(1000);
  ESP.restart();
}

void handleNotFound() {
  String msg = "404 Not Found\n\n";
  msg += "요청한 URL: ";
  msg += server.uri();
  server.send(404, "text/plain", msg);
}

// =============================
// 12. 상태별 진입/루프 함수
// =============================

void startSetupMode() {
  Serial.println("[STATE] SETUP MODE 진입");

  showSetupScreen();

  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_AP);
  bool apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD);
  if (apStarted) {
    Serial.println("[WIFI] AP 모드 시작 성공");
  } else {
    Serial.println("[WIFI] AP 모드 시작 실패");
  }

  IPAddress apIP = WiFi.softAPIP();
  Serial.print("[WIFI] AP IP: ");
  Serial.println(apIP);

  server.on("/", HTTP_GET, handleRoot);
  server.on("/save", HTTP_POST, handleSave);
  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("[HTTP] 설정용 HTTP 서버 시작 (포트 80)");
}

void loopSetupMode() {
  server.handleClient();
}

void startRunMode() {
  Serial.println("[STATE] RUN MODE 진입");

  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_STA);

  Serial.print("[WIFI] STA 모드로 Wi-Fi 연결 시도: SSID=");
  Serial.println(g_config.wifiSsid);

  WiFi.begin(g_config.wifiSsid, g_config.wifiPass);

  const int MAX_RETRY = 20;
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < MAX_RETRY) {
    delay(500);
    Serial.print(".");
    retry++;
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI] 연결 실패. SETUP 모드로 되돌아갑니다.");
    showWifiErrorScreen();
    delay(2000);

    currentState = STATE_SETUP;
    startSetupMode();
    return;
  }

  IPAddress ip = WiFi.localIP();
  Serial.println("[WIFI] 연결 성공!");
  Serial.print("[WIFI] IP 주소: ");
  Serial.println(ip);

  // 모터 핀 설정
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR,  OUTPUT);
  pinMode(PIN_ENA,  OUTPUT);

  digitalWrite(PIN_STEP, LOW);
  digitalWrite(PIN_DIR, LOW);
  digitalWrite(PIN_ENA, LOW);

  // 리미트 스위치 핀 설정
  pinMode(LIMIT_FLOOR, INPUT_PULLUP);
  pinMode(LIMIT_DOOR,  INPUT_PULLUP);

  // 색상 정의
  COLOR_MINT     = tft.color565(80,  220, 180);
  COLOR_SOFT_RED = tft.color565(255, 80,  120);
  COLOR_YELLOW   = tft.color565(255, 255, 0);
  COLOR_GREEN    = tft.color565(0, 200, 80);

  // MQTT 토픽 설정
  setupMqttTopics();
  
  // MQTT 연결 시도
  showMqttConnectingScreen();
  
  int mqttRetry = 0;
  const int MQTT_MAX_RETRY = 5;
  while (!connectMqtt() && mqttRetry < MQTT_MAX_RETRY) {
    delay(2000);
    mqttRetry++;
    Serial.print("[MQTT] 재시도 ");
    Serial.print(mqttRetry);
    Serial.print("/");
    Serial.println(MQTT_MAX_RETRY);
  }
  
  if (mqttClient.connected()) {
    // 부팅 완료 이벤트 발행
    publishBootComplete();
  } else {
    Serial.println("[MQTT] 초기 연결 실패 - 백그라운드에서 재시도 계속");
  }

  // 대기 화면 표시
  showIdleScreen();

  Serial.println("=================================");
  Serial.println("F-BOX v2.0 운영 모드 시작");
  Serial.print("Device ID: "); Serial.println(g_config.deviceId);
  Serial.print("Size: "); Serial.println(g_config.size);
  Serial.print("Stock: "); Serial.println(g_stock);
  Serial.println("=================================");

  // 초기 상태 읽기
  lastDoorState  = digitalRead(LIMIT_DOOR);
  lastFloorState = digitalRead(LIMIT_FLOOR);

  // 부팅 시 문이 닫혀 있으면 홈 복귀
  if (lastDoorState == LOW) {
    Serial.println("[RUN] 전원 ON 시 문 닫힘 상태 → 홈 동작 실행");
    homeToFirstFloor();
    showIdleScreen();
  }
  
  lastHeartbeatTime = millis();
  lastWifiCheckTime = millis();
}

void loopRunMode() {
  // MQTT 루프 (메시지 수신 처리)
  if (mqttClient.connected()) {
    mqttClient.loop();
  }
  
  // Wi-Fi 연결 상태 체크
  if (millis() - lastWifiCheckTime >= WIFI_CHECK_INTERVAL) {
    lastWifiCheckTime = millis();
    
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WIFI] 연결 끊김 - 재연결 시도");
      WiFi.reconnect();
      
      int retry = 0;
      while (WiFi.status() != WL_CONNECTED && retry < 10) {
        delay(500);
        retry++;
      }
      
      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("[WIFI] 재연결 성공");
        publishWifiReconnected();
      }
    }
  }
  
  // MQTT 연결 상태 체크 및 재연결
  if (!mqttClient.connected()) {
    static unsigned long lastMqttReconnect = 0;
    if (millis() - lastMqttReconnect >= 5000) {  // 5초마다 재시도
      lastMqttReconnect = millis();
      Serial.println("[MQTT] 연결 끊김 - 재연결 시도");
      
      if (connectMqtt()) {
        publishMqttReconnected();
      }
    }
  }
  
  // Heartbeat 전송 (1분마다)
  if (millis() - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
    lastHeartbeatTime = millis();
    publishHeartbeat();
  }

  // 리미트 스위치 상태 모니터링
  int floorState = digitalRead(LIMIT_FLOOR);
  if (floorState != lastFloorState) {
    lastFloorState = floorState;
    if (floorState == LOW) {
      Serial.println("[STATE] 1층 도달");
    } else {
      Serial.println("[STATE] 1층 스위치 해제");
    }
  }

  // 문 스위치 상태 체크
  int doorState = digitalRead(LIMIT_DOOR);
  if (doorState != lastDoorState) {
    lastDoorState = doorState;

    if (doorState == LOW) {
      // 문 닫힘
      Serial.println("[STATE] 문 닫힘 감지 → 1층 복귀 시작");
      publishDoorClosed();
      homeToFirstFloor();
      showIdleScreen();
    } else {
      // 문 열림
      Serial.println("[STATE] 문 열림");
      publishDoorOpened();
    }
  }

  // 시리얼 명령 처리 (디버깅/테스트용)
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == '\n' || cmd == '\r') {
      return;
    }

    Serial.print("시리얼 명령: ");
    Serial.println(cmd);

    switch (cmd) {
      case 'D':  // Dispense
        Serial.println("[SERIAL] 토출 명령");
        dispenseOne();
        break;
        
      case 'S':  // Status
        Serial.println("[SERIAL] 상태 출력");
        Serial.print("  Stock: "); Serial.println(g_stock);
        Serial.print("  Locked: "); Serial.println(g_locked ? "Yes" : "No");
        Serial.print("  Door: "); Serial.println(digitalRead(LIMIT_DOOR) == LOW ? "Closed" : "Open");
        Serial.print("  Floor: "); Serial.println(digitalRead(LIMIT_FLOOR) == LOW ? "Reached" : "Moving");
        Serial.print("  MQTT: "); Serial.println(mqttClient.connected() ? "Connected" : "Disconnected");
        publishStatus();
        break;
        
      case 'L':  // Lock
        handleLock();
        break;
        
      case 'U':  // Unlock
        handleUnlock();
        break;
        
      case 'H':  // Home
        handleHome();
        break;
        
      case 'R':  // Reboot
        handleReboot();
        break;
        
      case '+':  // Stock +1
        if (g_stock < MAX_STOCK) {
          g_stock++;
          saveStock();
          Serial.print("[SERIAL] 재고 증가: ");
          Serial.println(g_stock);
          publishStockUpdated("manual");
          showIdleScreen();
        }
        break;
        
      case '-':  // Stock -1
        if (g_stock > 0) {
          g_stock--;
          saveStock();
          Serial.print("[SERIAL] 재고 감소: ");
          Serial.println(g_stock);
          publishStockUpdated("manual");
          showIdleScreen();
        }
        break;
        
      case 'C':  // Clear config (SETUP 모드로 돌아가기)
        Serial.println("[SERIAL] 설정 초기화 → 재부팅");
        clearConfig();
        delay(500);
        ESP.restart();
        break;
        
      default:
        Serial.println("알 수 없는 명령입니다.");
        Serial.println("D: Dispense, S: Status, L: Lock, U: Unlock, H: Home, R: Reboot");
        Serial.println("+: Stock+1, -: Stock-1, C: Clear config");
        break;
    }
  }
}

// =============================
// 13. Arduino setup / loop
// =============================

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("===== F-BOX v2.0 시작 =====");
  Serial.print("Firmware: ");
  Serial.println(FIRMWARE_VERSION);

  // TFT 백라이트
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);

  // SPI + TFT 초기화
  SPI.begin(18, -1, 23);
  tft.init(240, 320);
  tft.setRotation(3);

  // 기본 config 초기화
  memset(&g_config, 0, sizeof(g_config));
  strncpy(g_config.size, "---", sizeof(g_config.size) - 1);
  strncpy(g_config.deviceId, "FBOX-01", sizeof(g_config.deviceId) - 1);
  strncpy(g_config.brokerHost, "192.168.0.10", sizeof(g_config.brokerHost) - 1);
  g_config.brokerPort = 1883;

  // NVS에서 설정 로드
  if (loadConfig(g_config)) {
    currentState = STATE_RUN;
    startRunMode();
  } else {
    currentState = STATE_SETUP;
    startSetupMode();
  }
}

void loop() {
  switch (currentState) {
    case STATE_SETUP:
      loopSetupMode();
      break;

    case STATE_RUN:
      loopRunMode();
      break;

    case STATE_ERROR:
      // 에러 모드 - 나중에 구현
      delay(1000);
      break;
  }
}

