# F-BOX ESP32 펌웨어

## 개요

ESP32 기반 F-BOX 대여기 펌웨어입니다.

### 주요 기능
- Wi-Fi 연결 (SETUP 모드 / RUN 모드)
- MQTT 통신 (라즈베리파이와 통신)
- 모터 제어 (TB6600 드라이버)
- LCD 표시 (ST7789 TFT)
- 리미트 스위치 감지
- 재고 관리

---

## 하드웨어

### ESP32
- 메인 컨트롤러

### TB6600 스텝 모터 드라이버
- NEMA17 모터 제어
- 1/2 스텝 모드

### GT2 벨트 & 풀리
- 20T 풀리
- 2mm 피치

### ST7789 TFT LCD
- 240x320 해상도
- SPI 통신

### 리미트 스위치 x2
- LIMIT_FLOOR (GPIO 32): 1층 도달 감지
- LIMIT_DOOR (GPIO 33): 문 닫힘 감지

---

## 펌웨어 버전

### v1 (기본 버전)
- Wi-Fi 설정 (SETUP 모드)
- 모터 제어
- LCD 표시
- 파일: `251130_2040_v1_wifi`

### v2 (MQTT 추가)
- v1 기능 포함
- MQTT 통신 추가
- 명령 수신 (DISPENSE, SET_STOCK 등)
- 이벤트 발행 (dispense_complete, heartbeat 등)
- 재고 카운트
- 파일: `f-box_v2_mqtt/f-box_v2_mqtt.ino`

---

## MQTT 통신

### 토픽 구조

**명령 수신 (Subscribe):**
```
fbox/{deviceId}/cmd
```

**이벤트 발행 (Publish):**
```
fbox/{deviceId}/status
```

### 지원 명령
- `DISPENSE`: 1장 토출
- `STATUS`: 상태 보고
- `SET_STOCK <n>`: 재고 설정
- `STOP`: 긴급 정지
- `LOCK` / `UNLOCK`: 기기 잠금/해제
- `HOME`: 강제 홈 복귀
- `REBOOT`: 재시작
- `CLEAR_ERROR`: 에러 초기화

### 발행 이벤트
- `boot_complete`: 부팅 완료
- `heartbeat`: 생존 신호 (1분마다)
- `dispense_complete`: 토출 완료
- `door_opened` / `door_closed`: 문 상태
- `stock_updated`: 재고 업데이트
- `stock_low` / `stock_empty`: 재고 부족/없음
- `dispense_failed`: 토출 실패
- `error`: 에러 발생

자세한 내용은 `docs/MQTT_PROTOCOL.md` 참조

---

## 설정

### NVS (Non-Volatile Storage)
ESP32 플래시에 저장되는 설정:

```cpp
struct AppConfig {
  char wifiSsid[32];      // Wi-Fi SSID
  char wifiPass[64];      // Wi-Fi Password
  char size[8];           // Size (예: "105")
  char deviceId[16];      // Device ID (예: "FBOX-UPPER-105")
  char brokerHost[64];    // MQTT 브로커 주소 (라즈베리파이 IP)
  uint16_t brokerPort;    // MQTT 브로커 포트 (기본 1883)
};
```

### SETUP 모드
설정이 없을 때 자동으로 진입:
1. AP 모드로 Wi-Fi 생성 (`F-BOX-01`)
2. LCD에 QR 코드 표시
3. 웹 브라우저로 `http://192.168.4.1` 접속
4. 설정 입력 후 저장
5. 자동 재부팅 → RUN 모드로 전환

---

## 업로드 방법

### Arduino IDE
1. ESP32 보드 매니저 설치
2. 필요한 라이브러리 설치:
   - `PubSubClient` (MQTT)
   - `Adafruit GFX` (LCD)
   - `Adafruit ST7789` (LCD)
   - `esp_qrcode` (QR 코드, ESP32 기본 포함)
3. 보드 선택: ESP32 Dev Module
4. 포트 선택
5. 업로드

### PlatformIO
```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
    knolleary/PubSubClient @ ^2.8
    adafruit/Adafruit GFX Library @ ^1.11.0
    adafruit/Adafruit ST7735 and ST7789 Library @ ^1.9.0
```

---

## 핀 배열

### 모터 (TB6600)
- PIN_STEP: GPIO 25 (PUL+)
- PIN_DIR: GPIO 26 (DIR+)
- PIN_ENA: GPIO 27 (ENA+)

### LCD (ST7789)
- TFT_CS: GPIO 5
- TFT_DC: GPIO 16
- TFT_RST: GPIO 17
- TFT_BL: GPIO 4 (백라이트)
- SPI:
  - SCK: GPIO 18
  - MOSI: GPIO 23
  - MISO: -1 (사용 안 함)

### 리미트 스위치
- LIMIT_FLOOR: GPIO 32 (INPUT_PULLUP, LOW=눌림)
- LIMIT_DOOR: GPIO 33 (INPUT_PULLUP, LOW=닫힘)

---

## 시리얼 모니터

### 보드레이트
115200

### 로그 예시
```
===== F-BOX 통합 코드 시작 =====
[CONFIG] 설정 로드 완료
  SSID: MyWiFi
  SIZE: 105
  DEV : FBOX-UPPER-105
  HOST: 192.168.1.10
  PORT: 1883
[STATE] RUN MODE 진입
[WIFI] STA 모드로 Wi-Fi 연결 시도: SSID=MyWiFi
[WIFI] 연결 성공!
[WIFI] IP 주소: 192.168.1.100
[MQTT] 연결 시도...
[MQTT] 연결 성공
[MQTT] Subscribe: fbox/FBOX-UPPER-105/cmd
[MQTT] Publish: boot_complete
=================================
TB6600 + GT2 20T 15mm + ST7789 + LIMIT 2개
  LIMIT_FLOOR(32): 1층 도달 스위치 (LOW=도달)
  LIMIT_DOOR (33): 문 닫힘 스위치 (LOW=문 닫힘)
=================================
```

---

## 트러블슈팅

### Wi-Fi 연결 실패
- SSID/Password 확인
- 신호 강도 확인
- 2.4GHz 대역 사용 확인 (ESP32는 5GHz 미지원)

### MQTT 연결 실패
- 브로커 주소/포트 확인
- 브로커 실행 상태 확인 (`mosquitto_sub -t "test"`)
- 방화벽 포트 1883 열기

### 모터 작동 안 함
- TB6600 전원 확인
- ENA 핀 상태 확인
- 리미트 스위치 상태 확인

### LCD 표시 안 됨
- SPI 핀 연결 확인
- 백라이트 핀 (GPIO 4) HIGH 상태 확인

---

## 테스트 기록

### ✅ v2.0.0 MQTT 통신 테스트 완료 (2024-12-02)

**테스트 환경:**
- ESP32: FBOX-01 (하드웨어 미연결 상태)
- 라즈베리파이: 192.168.0.27 (Mosquitto 브로커)
- 네트워크: 192.168.0.x 대역

**테스트 결과:**
```
ESP32 → 라즈베리파이:
  ✅ boot_complete 이벤트 발행
  ✅ heartbeat 이벤트 발행 (1분 주기)
  ✅ status 응답

라즈베리파이 → ESP32:
  ✅ STATUS 명령 수신 및 응답
  ✅ fbox/FBOX-01/cmd 토픽 구독 확인
```

**실제 수신 메시지:**
```json
fbox/FBOX-01/status {"event":"status","deviceId":"FBOX-01","size":"TOWEL","stock":30,"doorState":"open","floorState":"moving","locked":false,"wifiRssi":-37,"timestamp":302}
fbox/FBOX-01/status {"event":"heartbeat","deviceId":"FBOX-01","stock":30,"doorState":"open","locked":false,"timestamp":303}
```

**결론:** MQTT 양방향 통신 정상 동작 확인. 하드웨어(모터, LCD, 스위치) 연결 시 토출 기능도 동작 예상.

---

## 라이선스

MIT License

---

## 버전 이력

- **v1.0.0** (2024-12-01): 초기 버전 (Wi-Fi + 모터 + LCD)
- **v2.0.0** (2024-12-01): MQTT 통신 추가
- **v2.0.0** (2024-12-02): 라즈베리파이 MQTT 브로커 연동 테스트 완료 ✅

