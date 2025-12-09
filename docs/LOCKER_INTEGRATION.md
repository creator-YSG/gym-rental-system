# 락카키 대여기 ↔ 운동복 대여기 통합 가이드

## 개요

이 문서는 **락카키 대여기**와 **운동복 대여기** 간 회원 정보 연동을 위한 API 명세와 구현 가이드입니다.

### 시스템 구성

```
┌──────────────────────┐                    ┌──────────────────┐
│  운동복/수건 대여기   │                    │  락카키 대여기    │
│  (현재 시스템)        │                    │  (별도 시스템)    │
│                      │                    │                  │
│  1. NFC 태그 인식    │ ──HTTP GET──>      │  - 락카 배정     │
│     (5A41B914524189) │                    │  - 회원 관리     │
│                      │                    │  - API 제공      │
│  2. 회원 정보 수신   │ <────응답────      │  - NFC 매핑 관리 │
│     (ID, 이름)       │                    │                  │
└──────────────────────┘                    └──────────────────┘
```

### 네트워크 환경

- 두 시스템 모두 **같은 내부 LAN** (공유기) 사용
- **락카키 대여기 IP**: `192.168.0.23:5000`
- HTTP 통신 latency: **1-5ms** (충분히 빠름)
- 별도 VPN이나 외부 인터넷 불필요

---

## 데이터 흐름

### 운동복 대여 시나리오

```
1. [사용자] 락카키 NFC 태그
   NFC UID: 5A41B914524189
     ↓
2. [운동복 대여기] 락카키 대여기 API 호출
     HTTP GET http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189
     ↓
3. [락카키 대여기] NFC UID → 락카 번호 매핑
   5A41B914524189 → M01
     ↓
4. [락카키 대여기] 회원 정보 응답
     {
       "status": "ok",
       "locker_number": "M01",
       "member_id": "20240861",
       "name": "쩐부테쑤안",
       "assigned_at": "2025-12-09 10:33:52"
     }
     ↓
5. [운동복 대여기] 로컬 DB에서 금액권/구독권 조회
     ↓
6. [운동복 대여기] 대여 화면 표시 (상품 선택)
```

---

## 🔌 API 명세 (락카키 대여기에 이미 구현됨 ✅)

### 1. 회원 정보 조회 API ⭐ **필수**

운동복 대여기가 NFC 태그 시 호출하는 API입니다.

#### 엔드포인트

```
GET /api/member/by-nfc/{nfc_uid}
```

#### 요청 예시

```bash
GET http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189
```

#### 응답 예시

**✅ 성공 (200 OK) - 대여 중인 락카**
```json
{
  "status": "ok",
  "locker_number": "M01",
  "member_id": "20240861",
  "name": "쩐부테쑤안",
  "assigned_at": "2025-12-09 10:33:52"
}
```

**❌ 락카 미배정 (404 Not Found) - 빈 락카**
```json
{
  "status": "error",
  "locker_number": "S01",
  "nfc_uid": "5AE17DD3514189",
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**❌ 등록되지 않은 NFC (404 Not Found)**
```json
{
  "status": "error",
  "nfc_uid": "UNKNOWN123456",
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**❌ 회원 정보 없음 (404 Not Found)**
```json
{
  "status": "error",
  "locker_number": "M01",
  "member_id": "20240861",
  "message": "회원 정보를 찾을 수 없습니다"
}
```

**❌ 서버 오류 (500 Internal Server Error)**
```json
{
  "status": "error",
  "message": "서버 오류"
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `status` | string | ✅ | 응답 상태 (`ok` 또는 `error`) |
| `locker_number` | string | ✅ | 락카 번호 (예: M01, F05, S10) |
| `member_id` | string | ✅ | 회원 ID (바코드 번호) |
| `name` | string | ✅ | 회원 이름 |
| `assigned_at` | string | ⚪ | 락카 배정 시각 (YYYY-MM-DD HH:MM:SS) |
| `nfc_uid` | string | ⚪ | NFC UID (에러 시에만 포함) |
| `message` | string | ⚪ | 에러 메시지 (에러 시에만 포함) |

**⚠️ 중요 사항:**
- **금액권/구독권 정보는 포함하지 않음** (운동복 대여기 로컬 DB에서 조회)
- **회원 ID와 이름만 전달** (개인정보 최소화)
- **NFC UID → 락카 번호 매핑은 락카키 대여기에서 자동 처리**

---

### 2. 헬스 체크 API ✅ **구현됨**

운동복 대여기가 락카키 대여기의 연결 상태를 확인하는 API입니다.

#### 엔드포인트

```
GET /api/health
```

#### 응답 예시

```json
{
  "status": "healthy",
  "service": "locker-api",
  "timestamp": "2024-12-01T10:00:00"
}
```

---

## 📝 NFC UID 샘플 데이터

현재 락카키 대여기에 등록된 NFC 태그 예시:

| NFC UID | 락카 번호 | 구역 | 상태 |
|---------|----------|------|------|
| `5A41B914524189` | M01 | 남성 | 대여 중 |
| `5AE17DD3514189` | S01 | 교직원 | 비어있음 |

> **참고**: 실제 운영 환경에서는 60개의 락카에 각각 고유한 NFC UID가 할당됩니다.

---

## 📐 통신 방식 비교

### Pull 방식 (HTTP GET) ⭐ **권장**

**장점:**
- ✅ 필요할 때만 요청 (NFC 태그 순간에만)
- ✅ 항상 최신 정보 보장 (실시간 조회)
- ✅ 구현 간단 (REST API 1개)
- ✅ 디버깅 쉬움 (HTTP 로그로 추적)
- ✅ 네트워크 부하 적음
- ✅ 동기화 문제 없음

**단점:**
- ⚠️ 락카키 대여기 서버 다운 시 대여 불가
  - 해결: 헬스 체크 + 오류 안내 메시지

**성능:**
- 같은 LAN: 1-5ms (사용자 체감 불가)

### Push 방식 (MQTT/WebSocket)

**장점:**
- ✅ 실시간 동기화 (락카 배정 즉시 전달)
- ✅ 락카키 대여기 다운 시에도 캐시된 정보로 대여 가능

**단점:**
- ❌ 구현 복잡도 높음 (MQTT 브로커 또는 WebSocket 필요)
- ❌ 동기화 이슈 (네트워크 끊김 시)
- ❌ 메모리 관리 필요 (모든 락카 정보 저장)
- ❌ 디버깅 어려움

### ✅ 결론: Pull 방식 권장

같은 LAN에서는 HTTP Pull이 **충분히 빠르고 안정적**입니다.

---

## 🛠️ 운동복 대여기 구현 가이드

### Python (Flask 백엔드)

```python
import requests

LOCKER_API_URL = "http://192.168.0.23:5000"  # 락카키 대여기 IP
TIMEOUT = 2.0  # 2초 타임아웃

def get_member_by_nfc(nfc_uid: str):
    """
    NFC UID로 회원 정보 조회
    
    Args:
        nfc_uid: NFC 태그 UID (예: "5A41B914524189")
    
    Returns:
        dict: 회원 정보 또는 None
    """
    try:
        response = requests.get(
            f"{LOCKER_API_URL}/api/member/by-nfc/{nfc_uid}",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'member_id': data['member_id'],
                'name': data['name'],
                'locker_number': data['locker_number'],
                'assigned_at': data.get('assigned_at', '')
            }
        elif response.status_code == 404:
            print(f"[API] 락카 미배정: NFC {nfc_uid}")
            return None
        else:
            print(f"[API] 오류: {response.status_code}")
            return None
            
    except requests.Timeout:
        print(f"[API] 타임아웃: 락카키 대여기 응답 없음")
        return None
    except requests.ConnectionError:
        print(f"[API] 연결 실패: 락카키 대여기 서버 다운")
        return None
    except Exception as e:
        print(f"[API] 예외 발생: {e}")
        return None


# 사용 예시
nfc_uid = "5A41B914524189"  # NFC 리더에서 읽은 UID
member = get_member_by_nfc(nfc_uid)

if member:
    print(f"회원 확인: {member['name']} ({member['member_id']})")
    print(f"락카 번호: {member['locker_number']}")
    # 운동복 대여 처리...
else:
    print("회원 정보를 찾을 수 없습니다")
```

### JavaScript (Node.js/Express)

```javascript
const axios = require('axios');

const LOCKER_API_URL = "http://192.168.0.23:5000";
const TIMEOUT = 2000; // 2초 타임아웃

async function getMemberByNFC(nfcUid) {
  try {
    const response = await axios.get(
      `${LOCKER_API_URL}/api/member/by-nfc/${nfcUid}`,
      { timeout: TIMEOUT }
    );
    
    if (response.status === 200 && response.data.status === 'ok') {
      return {
        memberId: response.data.member_id,
        name: response.data.name,
        lockerNumber: response.data.locker_number,
        assignedAt: response.data.assigned_at
      };
    }
    
    return null;
  } catch (error) {
    if (error.response?.status === 404) {
      console.log(`[API] 락카 미배정: NFC ${nfcUid}`);
    } else if (error.code === 'ECONNABORTED') {
      console.log('[API] 타임아웃');
    } else {
      console.log(`[API] 오류: ${error.message}`);
    }
    return null;
  }
}

// 사용 예시
(async () => {
  const nfcUid = "5A41B914524189"; // NFC 리더에서 읽은 UID
  const member = await getMemberByNFC(nfcUid);
  
  if (member) {
    console.log(`회원 확인: ${member.name} (${member.memberId})`);
    console.log(`락카 번호: ${member.lockerNumber}`);
    // 운동복 대여 처리...
  } else {
    console.log("회원 정보를 찾을 수 없습니다");
  }
})();
```

---

## 🔒 보안 고려사항

### 현재 (개발 단계)

- 인증 없음 (같은 LAN 내부 통신)
- 평문 HTTP

### 향후 (프로덕션)

- API Key 인증 (헤더 또는 쿼리 파라미터)
- HTTPS (TLS/SSL)
- IP 화이트리스트 (공유기 DHCP 고정 IP)

**예시: API Key 인증**

```python
API_KEY = "your-secret-api-key"

@app.route('/api/member/by-locker/<int:locker_number>', methods=['GET'])
def get_member_by_locker(locker_number):
    # API Key 확인
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    # ... 기존 로직
```

---

## 🧪 테스트 방법

### 1. 로컬 테스트 (curl)

```bash
# ✅ 성공 케이스 (대여 중인 락카)
curl http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189

# ❌ 실패 케이스 (빈 락카)
curl http://192.168.0.23:5000/api/member/by-nfc/5AE17DD3514189

# 헬스 체크
curl http://192.168.0.23:5000/api/health
```

### 2. Python 테스트 스크립트

```python
import requests
import json

def test_nfc_api():
    """NFC API 테스트"""
    test_cases = [
        ("5A41B914524189", "M01 대여중 - 성공 예상"),
        ("5AE17DD3514189", "S01 비어있음 - 404 예상"),
        ("INVALID_UID", "잘못된 UID - 404 예상")
    ]
    
    for nfc_uid, description in test_cases:
        print(f"\n테스트: {description}")
        print(f"NFC UID: {nfc_uid}")
        
        response = requests.get(
            f"http://192.168.0.23:5000/api/member/by-nfc/{nfc_uid}"
        )
        
        print(f"응답 코드: {response.status_code}")
        print(f"응답 데이터:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    test_nfc_api()
```

### 3. 성능 테스트

```bash
# Apache Bench로 부하 테스트
ab -n 1000 -c 10 http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189

# 예상 결과 (같은 LAN):
# - 평균 응답 시간: 1-5ms
# - 처리량: 초당 500-1000 요청
```

---

## 🔧 트러블슈팅

### 문제 1: 연결 실패 (Connection Refused)

**원인:**
- 락카키 대여기 API 서버 미실행
- 방화벽 차단
- 잘못된 IP 주소

**해결:**
```bash
# 1. 락카키 대여기에서 서버 실행 확인
ssh pi@192.168.0.23 'ps aux | grep "python3 run.py"'

# 2. 포트 리스닝 확인
ssh pi@192.168.0.23 'netstat -tlnp | grep 5000'

# 3. 헬스 체크로 연결 확인
curl http://192.168.0.23:5000/api/health

# 4. 방화벽 허용 (필요 시)
ssh pi@192.168.0.23 'sudo ufw allow 5000/tcp'
```

### 문제 2: 타임아웃

**원인:**
- 네트워크 지연
- 서버 과부하

**해결:**
```python
# 타임아웃 설정 (운동복 대여기)
response = requests.get(url, timeout=2.0)  # 2초 타임아웃
```

### 문제 3: 404 Not Found (락카 미배정)

**원인:**
- NFC UID가 DB에 등록되지 않음
- 락카가 비어있음 (대여 중이 아님)

**해결:**
- 락카키 대여기 관리자에게 문의
- NFC UID가 올바른지 확인
- 테스트용 NFC UID 사용: `5A41B914524189` (M01 대여중)

---

## 📝 체크리스트

### 락카키 대여기 ✅ **이미 구현됨**

- [x] API 서버 구현 (`GET /api/member/by-nfc/<nfc_uid>`)
- [x] 헬스 체크 API 구현 (`GET /api/health`)
- [x] NFC UID → 락카 번호 매핑 DB 테이블
- [x] 락카 배정 시 DB 업데이트 로직
- [x] 락카 반납 시 DB 삭제 로직
- [x] API 서버 자동 시작 (systemd)
- [x] 로깅 설정
- [x] 고정 IP 설정 (192.168.0.23)

### 운동복 대여기 (구현 필요)

#### 하드웨어 (미구현 ❌)

- [ ] **NFC 리더 전용 ESP32** 준비 및 연결
  - ⚠️ **중요**: 이것은 운동복 토출기용 ESP32가 **아님**
  - 라즈베리파이 옆에 USB 또는 시리얼로 연결하는 **별도의 ESP32**
  - NFC 리더 모듈 (PN532 또는 RC522) 연결
- [ ] NFC UID 읽기 펌웨어 개발
  - NFC 태그 감지
  - UID 읽기 (예: `5A41B914524189`)
  - 라즈베리파이로 UID 전송 (UART/Serial)

#### 소프트웨어 (라즈베리파이)

- [ ] NFC UID 수신 API 구현
  - Serial 포트 리스닝 (`/dev/ttyUSB0` 또는 `/dev/ttyACM0`)
  - UID 파싱 및 검증
- [ ] HTTP 클라이언트 구현
  - 락카키 대여기 API 호출 (`/api/member/by-nfc/{nfc_uid}`)
  - 에러 처리 (404, 500, 타임아웃)
  - 재시도 로직
- [ ] 로컬 DB에서 금액권/구독권 조회
- [ ] 대여 화면 표시 (웹 UI 연동)

---

## 🔄 시스템 시작 가이드

### 락카키 대여기 ✅ **자동 시작 설정됨**

락카키 대여기는 이미 systemd로 자동 시작되도록 설정되어 있습니다.

**상태 확인:**
```bash
ssh pi@192.168.0.23 'sudo systemctl status locker-api'
```

**재시작:**
```bash
ssh pi@192.168.0.23 'sudo systemctl restart locker-api'
```

---

## 📊 모니터링

### 로그 확인

```bash
# API 서버 로그 (systemd)
sudo journalctl -u locker-api -f

# 액세스 로그 (Flask)
tail -f /var/log/locker-api/access.log

# 에러 로그
tail -f /var/log/locker-api/error.log
```

### 헬스 체크 모니터링

```bash
# 1분마다 헬스 체크 (cron)
* * * * * curl -f http://localhost:5000/api/health || echo "API Down" | mail -s "Alert" admin@example.com
```

---

## 📞 문의 및 지원

- **락카키 대여기 시스템**: `/Users/yunseong-geun/Projects/raspberry-pi-gym-controller`
- **운동복 대여기 시스템**: `/Users/yunseong-geun/Projects/gym-rental-system`
- **API 서버 주소**: `http://192.168.0.23:5000`
- **헬스 체크**: `GET /api/health`

---

## 📅 버전 이력

- **v1.1.0** (2025-12-09): 실제 구현 내용 반영
  - NFC UID 기반 API로 업데이트 (`/api/member/by-nfc/{nfc_uid}`)
  - 락카키 대여기 실제 IP 반영 (192.168.0.23)
  - 실제 NFC UID 샘플 데이터 추가
  - 테스트 케이스 실제 데이터로 업데이트
- **v1.0.0** (2024-12-09): 초기 문서 작성

---

## 🚀 NFC 리더 ESP32 개발 가이드 (미구현 ❌)

### 하드웨어 구성

```
┌────────────────────────────────────────────┐
│         운동복 대여기 라즈베리파이           │
│                                            │
│  ┌──────────────┐   ┌──────────────┐     │
│  │   Flask App  │   │  MQTT Broker │     │
│  │  (대여 처리)  │   │ (토출 제어)  │     │
│  └──────────────┘   └──────────────┘     │
│          ↑                                 │
│          │ USB/Serial                      │
└──────────┼─────────────────────────────────┘
           │
           │
     ┌─────┴──────┐
     │ NFC 리더    │
     │ ESP32      │ ← 🆕 새로운 ESP32 (토출기와 별개)
     │            │
     │ ┌────────┐ │
     │ │ PN532  │ │ ← NFC 리더 모듈
     │ │/RC522  │ │
     │ └────────┘ │
     └────────────┘
```

### ESP32 펌웨어 개발 (Arduino IDE 또는 PlatformIO)

#### 1. 하드웨어 연결

**PN532 NFC 모듈 연결 (I2C 방식 권장)**

| PN532 | ESP32 |
|-------|-------|
| VCC   | 3.3V  |
| GND   | GND   |
| SDA   | GPIO21 (I2C SDA) |
| SCL   | GPIO22 (I2C SCL) |

**RC522 NFC 모듈 연결 (SPI 방식)**

| RC522 | ESP32 |
|-------|-------|
| VCC   | 3.3V  |
| RST   | GPIO22 |
| GND   | GND   |
| MISO  | GPIO19 |
| MOSI  | GPIO23 |
| SCK   | GPIO18 |
| SDA   | GPIO5  |

#### 2. ESP32 펌웨어 예시 (PN532 사용)

**`platformio.ini`**
```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
    adafruit/Adafruit PN532@^1.2.2
monitor_speed = 115200
```

**`src/main.cpp`**
```cpp
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PN532.h>

// I2C 핀 설정
#define PN532_SDA 21
#define PN532_SCL 22

// PN532 초기화 (I2C)
Adafruit_PN532 nfc(PN532_SDA, PN532_SCL);

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("NFC Reader ESP32 Starting...");
  
  // NFC 모듈 초기화
  nfc.begin();
  
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("ERROR: PN532 not found!");
    while (1); // 무한 대기
  }
  
  Serial.print("PN532 Firmware Version: 0x");
  Serial.println(versiondata, HEX);
  
  // NFC 리더 설정
  nfc.SAMConfig();
  
  Serial.println("NFC Reader Ready. Waiting for cards...");
}

void loop() {
  uint8_t uid[] = { 0, 0, 0, 0, 0, 0, 0 };
  uint8_t uidLength;
  
  // NFC 태그 감지 (타임아웃 100ms)
  bool success = nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 100);
  
  if (success) {
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
  }
  
  delay(100);
}
```

#### 3. RC522 버전 (대안)

**`platformio.ini`**
```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps = 
    miguelbalboa/MFRC522@^1.4.10
monitor_speed = 115200
```

**`src/main.cpp`**
```cpp
#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 22
#define SS_PIN  5

MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);
  SPI.begin();
  mfrc522.PCD_Init();
  
  Serial.println("NFC Reader ESP32 (RC522) Ready");
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
  
  delay(1000); // 중복 읽기 방지
}
```

### 라즈베리파이 시리얼 통신 설정

#### 1. USB 연결 확인

```bash
# ESP32 연결 후 포트 확인
ls -l /dev/ttyUSB* /dev/ttyACM*

# 권한 설정 (필요 시)
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyUSB0  # 또는 /dev/ttyACM0
```

#### 2. 시리얼 통신 테스트

```bash
# minicom 설치
sudo apt-get install minicom

# 시리얼 통신 테스트
minicom -b 115200 -D /dev/ttyUSB0

# NFC 카드 태그 시 출력 확인:
# {"nfc_uid":"5A41B914524189"}
```

---

## 📁 라즈베리파이 코드 구현

### 1. NFC 리더 서비스 추가

**`app/services/nfc_reader.py`** (새 파일)

```python
"""
NFC 리더 서비스
ESP32로부터 NFC UID를 시리얼로 수신
"""

import serial
import json
import threading
import time
from typing import Callable, Optional


class NFCReaderService:
    """ESP32 NFC 리더와 시리얼 통신"""
    
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200):
        """
        초기화
        
        Args:
            port: 시리얼 포트 (예: /dev/ttyUSB0, /dev/ttyACM0)
            baudrate: 통신 속도 (ESP32와 동일해야 함)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # NFC UID 수신 콜백
        self.on_nfc_detected: Optional[Callable[[str], None]] = None
        
    def connect(self) -> bool:
        """시리얼 포트 연결"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            print(f"[NFC Reader] ✓ 연결 성공: {self.port}")
            return True
        except Exception as e:
            print(f"[NFC Reader] ✗ 연결 실패: {e}")
            return False
    
    def start(self):
        """백그라운드 스레드에서 NFC UID 수신 시작"""
        if self.running:
            print("[NFC Reader] 이미 실행 중")
            return
        
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.connect():
                return
        
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        print("[NFC Reader] 시리얼 리스닝 시작")
    
    def stop(self):
        """NFC 리더 중지"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print("[NFC Reader] 중지")
    
    def _read_loop(self):
        """시리얼 데이터 읽기 루프"""
        while self.running:
            try:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    
                    if line:
                        self._process_line(line)
                        
            except Exception as e:
                print(f"[NFC Reader] 읽기 오류: {e}")
                time.sleep(1.0)
    
    def _process_line(self, line: str):
        """
        ESP32로부터 수신한 라인 처리
        
        예상 형식: {"nfc_uid":"5A41B914524189"}
        """
        try:
            data = json.loads(line)
            nfc_uid = data.get('nfc_uid')
            
            if nfc_uid:
                print(f"[NFC Reader] ← NFC 태그 감지: {nfc_uid}")
                
                # 콜백 실행
                if self.on_nfc_detected:
                    self.on_nfc_detected(nfc_uid)
            else:
                print(f"[NFC Reader] nfc_uid 없음: {line}")
                
        except json.JSONDecodeError:
            print(f"[NFC Reader] JSON 파싱 실패: {line}")
        except Exception as e:
            print(f"[NFC Reader] 처리 오류: {e}")
    
    def set_callback(self, callback: Callable[[str], None]):
        """
        NFC UID 수신 시 실행할 콜백 등록
        
        Args:
            callback: NFC UID를 인자로 받는 함수
        """
        self.on_nfc_detected = callback
        print("[NFC Reader] 콜백 등록 완료")


# 사용 예시
if __name__ == '__main__':
    def handle_nfc(nfc_uid: str):
        print(f"콜백 실행: NFC UID = {nfc_uid}")
        # 여기서 락카키 대여기 API 호출
    
    reader = NFCReaderService(port='/dev/ttyUSB0')
    reader.set_callback(handle_nfc)
    reader.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        reader.stop()
```

### 2. 락카키 대여기 API 클라이언트

**`app/services/locker_api_client.py`** (새 파일)

```python
"""
락카키 대여기 API 클라이언트
NFC UID로 회원 정보 조회
"""

import requests
from typing import Optional, Dict


class LockerAPIClient:
    """락카키 대여기 API 클라이언트"""
    
    def __init__(self, base_url: str = "http://192.168.0.23:5000", timeout: float = 2.0):
        """
        초기화
        
        Args:
            base_url: 락카키 대여기 API 주소
            timeout: 타임아웃 (초)
        """
        self.base_url = base_url
        self.timeout = timeout
    
    def get_member_by_nfc(self, nfc_uid: str) -> Optional[Dict]:
        """
        NFC UID로 회원 정보 조회
        
        Args:
            nfc_uid: NFC 태그 UID (예: "5A41B914524189")
        
        Returns:
            dict: 회원 정보 또는 None
            {
                'member_id': '20240861',
                'name': '쩐부테쑤안',
                'locker_number': 'M01',
                'assigned_at': '2025-12-09 10:33:52'
            }
        """
        try:
            url = f"{self.base_url}/api/member/by-nfc/{nfc_uid}"
            print(f"[Locker API] 요청: {url}")
            
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'ok':
                    print(f"[Locker API] ✓ 회원 조회 성공: {data.get('name')} ({data.get('member_id')})")
                    return {
                        'member_id': data['member_id'],
                        'name': data['name'],
                        'locker_number': data.get('locker_number', ''),
                        'assigned_at': data.get('assigned_at', '')
                    }
                else:
                    print(f"[Locker API] ✗ 응답 오류: {data.get('message')}")
                    return None
                    
            elif response.status_code == 404:
                print(f"[Locker API] ✗ 락카 미배정: NFC {nfc_uid}")
                return None
            else:
                print(f"[Locker API] ✗ HTTP 오류: {response.status_code}")
                return None
                
        except requests.Timeout:
            print(f"[Locker API] ✗ 타임아웃: 락카키 대여기 응답 없음")
            return None
        except requests.ConnectionError:
            print(f"[Locker API] ✗ 연결 실패: 락카키 대여기 서버 다운")
            return None
        except Exception as e:
            print(f"[Locker API] ✗ 예외 발생: {e}")
            return None
    
    def health_check(self) -> bool:
        """락카키 대여기 API 서버 상태 확인"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=1.0)
            return response.status_code == 200
        except:
            return False


# 사용 예시
if __name__ == '__main__':
    client = LockerAPIClient()
    
    # 헬스 체크
    if client.health_check():
        print("✓ 락카키 대여기 서버 정상")
    else:
        print("✗ 락카키 대여기 서버 다운")
    
    # 회원 조회
    member = client.get_member_by_nfc("5A41B914524189")
    if member:
        print(f"회원 정보: {member}")
    else:
        print("회원 정보 없음")
```

### 3. Flask 앱에 통합

**`app/__init__.py`** 수정

```python
# 기존 import에 추가
from app.services.nfc_reader import NFCReaderService
from app.services.locker_api_client import LockerAPIClient

# 전역 변수 추가
nfc_reader = None
locker_api_client = None

def create_app(config_name='default'):
    global nfc_reader, locker_api_client
    
    # ... 기존 코드 ...
    
    # NFC 리더 초기화
    try:
        nfc_port = os.getenv('NFC_PORT', '/dev/ttyUSB0')
        nfc_reader = NFCReaderService(port=nfc_port)
        
        # 락카키 대여기 API 클라이언트
        locker_api_url = os.getenv('LOCKER_API_URL', 'http://192.168.0.23:5000')
        locker_api_client = LockerAPIClient(base_url=locker_api_url)
        
        # NFC 태그 감지 시 처리 함수
        def handle_nfc_tag(nfc_uid: str):
            """NFC 태그 감지 시 실행"""
            print(f"[App] NFC 태그 감지: {nfc_uid}")
            
            # 락카키 대여기 API 호출
            member = locker_api_client.get_member_by_nfc(nfc_uid)
            
            if member:
                # 웹 UI로 회원 정보 전송 (SocketIO)
                socketio.emit('member_detected', {
                    'member_id': member['member_id'],
                    'name': member['name'],
                    'locker_number': member['locker_number']
                })
                
                print(f"[App] ✓ 회원 정보 전송: {member['name']}")
            else:
                # 오류 메시지 전송
                socketio.emit('member_error', {
                    'message': '락카가 배정되어 있지 않습니다'
                })
                print(f"[App] ✗ 회원 정보 없음")
        
        # 콜백 등록
        nfc_reader.set_callback(handle_nfc_tag)
        
        # NFC 리더 시작
        nfc_reader.start()
        
        print("[App] NFC 리더 서비스 시작")
        
    except Exception as e:
        print(f"[App] NFC 리더 초기화 실패: {e}")
    
    return app

def get_nfc_reader():
    """NFC 리더 인스턴스 반환"""
    return nfc_reader

def get_locker_api_client():
    """락카키 대여기 API 클라이언트 반환"""
    return locker_api_client
```

---

## 부록: API 흐름도

```
[NFC 리더 ESP32]
     ↓
1. NFC 태그 감지
   NFC UID: "5A41B914524189"
     ↓
2. 시리얼 전송 (USB/UART)
   → {"nfc_uid":"5A41B914524189"}
     ↓
[운동복 대여기 라즈베리파이]
     ↓
3. 시리얼 데이터 수신 (NFCReaderService)
   → nfc_uid 파싱
     ↓
4. 락카키 대여기 API 호출 (LockerAPIClient)
   → HTTP GET http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189
     ↓
[락카키 대여기]
     ↓
5. NFC UID → 락카 번호 매핑
   "5A41B914524189" → "M01"
     ↓
6. 락카 번호 → 대여 정보 조회
   "M01" → 회원 "20240861" (쩐부테쑤안)
     ↓
7. 회원 정보 응답
   {"status": "ok", "member_id": "20240861", "name": "쩐부테쑤안", ...}
     ↓
[운동복 대여기 라즈베리파이]
     ↓
8. 회원 정보 수신
   - 로컬 DB에서 금액권/구독권 조회
   - SocketIO로 웹 UI에 전송
     ↓
[웹 UI]
     ↓
9. 대여 화면 표시
   - 회원 이름 표시
   - 상품 선택 가능
```

---

## 📋 구현 진행 상황 (2025-12-09)

### ✅ 완료된 작업

#### 1. Google Sheets 통합 - 락카키 대여기 IP 동적 관리
- **상태**: ✅ 구현 완료 및 라즈베리파이 테스트 성공
- **시트**: System_Integration (ID: `15qpiY1r_SEK6b2dr00UDmKrYHSVuGMmiMeTZ898Lv8Q`)
- **구현 내용**:
  - `app/services/integration_sync.py`: IntegrationSync 클래스 (락카키 대여기 코드에서 복사)
  - `app/__init__.py`: 부팅 시 System_Integration 시트에서 락카키 대여기 IP 자동 다운로드
  - 로컬 캐시 (`config/locker_api_cache.json`): 오프라인 백업
  - 실패 시 기본값 사용 (`http://192.168.0.23:5000`)
- **테스트 결과**:
  ```
  ✓ Google Sheets 연결: System_Integration
  ✓ 락카키 대여기 IP 다운로드: 192.168.0.23:5000
  ✓ 로컬 캐시 저장 완료
  ✓ 헬스 체크 성공
  ```
- **장점**:
  - 헬스장별 독립된 구글 드라이브 폴더 관리
  - 락카키 대여기 IP 변경 시 자동 반영
  - 기존 F-BOX-DB-TEST 시트와 독립적으로 동작

#### 2. NFC 로그인 기능 구현 (큐 + 폴링 방식)
- **상태**: ✅ 구현 완료 및 라즈베리파이 테스트 성공
- **방식**: SocketIO → 큐(Queue) + HTTP 폴링으로 변경 (라즈베리파이 환경 최적화)
- **구현 내용**:
  - `app/__init__.py`: NFC 이벤트 큐 추가, `handle_nfc_tag` 콜백에서 큐에 저장
  - `app/routes/main.py`:
    - `GET /api/nfc/poll`: 프론트엔드가 500ms마다 폴링하여 NFC 이벤트 확인
    - `POST /api/test/nfc-inject`: 테스트용 NFC UID 주입 API
    - `POST /api/auth/member_id`: NFC 로그인 시 member_id로 인증
  - `app/static/js/main.js`: SocketIO 리스너 제거, 폴링 방식으로 전환
  - `app/services/locker_api_client.py`: 락카키 대여기 API 클라이언트
  - `app/services/nfc_reader.py`: ESP32 시리얼 통신 처리 (미사용 예정)

#### 2. 테스트 데이터 구축
- **회원**: 20240861 (쩐부테쑤안)
  - 전화번호: 010-8095-9275
  - 비밀번호: 123456
- **금액권**: VCH-50K (5만원, 잔액 50,000원)
- **구독권**: SUB-1M-BASIC (1개월 기본 이용권)
  - 일일 제한: top 1회, pants 1회, towel 1회
  - 유효기간: 2025-12-09 ~ 2026-01-08
- **Google Sheets 동기화**: ✅ 완료 (members, member_subscriptions, member_vouchers)

#### 3. 수동 동기화 스크립트
- **파일**: `scripts/sync_member_to_sheets.py`
- **기능**: 로컬 DB → Google Sheets 수동 동기화
- **사용법**: `python3 scripts/sync_member_to_sheets.py <member_id>`

#### 4. 라즈베리파이 테스트 결과
- **NFC UID 주입 테스트**: ✅ 성공
  ```bash
  curl -X POST http://localhost:5000/api/test/nfc-inject \
    -H 'Content-Type: application/json' \
    -d '{"nfc_uid":"5A41B914524189"}'
  ```
- **화면 전환**: ✅ 홈 화면 → 대여 화면 자동 전환 확인
- **로그인**: ✅ 회원 정보 조회 및 로그인 성공

---

### ⚠️ 미완료 (컨펌 필요)

#### 1. ESP32 NFC 리더 하드웨어 연결
- **상태**: ⚠️ **컨펌 안 됨**
- **파일**: `esp32code/nfc-reader-pn532/`, `esp32code/nfc-reader-rc522/`
- **내용**: 
  - ESP32 펌웨어 코드 작성됨 (PN532, RC522 지원)
  - 시리얼 통신으로 NFC UID 전송 구현됨
  - **실제 하드웨어 연결 및 테스트 필요**

#### 2. 실제 NFC 리더 동작 확인
- **상태**: ⚠️ **컨펌 안 됨**
- **확인 필요 사항**:
  - ESP32 → 라즈베리파이 시리얼 연결 (`/dev/ttyUSB0`)
  - NFC 카드 태그 시 UID 정상 전송 여부
  - `app/services/nfc_reader.py` 실제 동작 확인

---

### 🚀 다음 단계

1. **ESP32 NFC 리더 하드웨어 설정**
   - ESP32에 펌웨어 업로드
   - 라즈베리파이와 USB 시리얼 연결
   - 실제 NFC 카드로 테스트

2. **운영 환경 배포**
   - Google Sheets 회원 데이터 정리
   - 실제 회원으로 NFC 로그인 테스트
   - 대여/반납 전체 플로우 확인

3. **모니터링 및 최적화**
   - NFC 인식 속도 측정
   - 폴링 간격 조정 (현재 500ms)
   - 오류 처리 강화

---

**문서 끝**

