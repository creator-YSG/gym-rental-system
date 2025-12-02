# F-BOX MQTT 통신 프로토콜

## 개요

F-BOX 시스템은 라즈베리파이(MQTT 브로커)와 ESP32 기기 간 MQTT 프로토콜을 사용하여 통신합니다.

### 통신 구조
```
[라즈베리파이 MQTT 브로커]
   ↕ MQTT (포트 1883)
[ESP32 F-BOX 기기들]
```

---

## 토픽 구조

### 명령 토픽 (라즈베리파이 → ESP32)
```
fbox/{deviceUUID}/cmd
```
- 라즈베리파이가 특정 ESP32 기기에 명령을 전송하는 토픽
- deviceUUID는 MAC 주소 기반 자동 생성 (예: FBOX-004B1238C424)
- 예시: `fbox/FBOX-004B1238C424/cmd`

### 이벤트 토픽 (ESP32 → 라즈베리파이)
```
fbox/{deviceUUID}/status
```
- ESP32 기기가 상태 변화나 이벤트를 라즈베리파이에 보고하는 토픽
- 예시: `fbox/FBOX-004B1238C424/status`

### Device UUID 생성 규칙
- **형식**: `FBOX-{MAC주소 12자리}`
- **예시**: MAC `00:4B:12:38:C4:24` → UUID `FBOX-004B1238C424`
- **특징**: MAC 기반이므로 변경 불가, 상품명/사이즈 변경해도 기록 유지

### 락카 배정 토픽 (락카키 대여기 → 운동복 대여기)
```
fbox/locker/assigned
```
- 락카키 대여기가 운동복 대여기 라즈베리파이에 락카 배정 정보 전송
- 직접 HTTP 통신으로 대체 가능

---

## 명령 셋 (라즈베리파이 → ESP32)

### 1. DISPENSE - 토출
물품 1개를 토출합니다.

**메시지 포맷:**
```json
{
  "cmd": "DISPENSE",
  "timestamp": 1733097600
}
```

**ESP32 응답:** `dispense_complete` 또는 `dispense_failed` 이벤트

---

### 2. STATUS - 상태 조회
현재 기기 상태를 즉시 보고하도록 요청합니다.

**메시지 포맷:**
```json
{
  "cmd": "STATUS",
  "timestamp": 1733097600
}
```

**ESP32 응답:** `status` 이벤트

---

### 3. SET_STOCK - 재고 설정
현재 재고를 특정 값으로 설정합니다.

**메시지 포맷:**
```json
{
  "cmd": "SET_STOCK",
  "stock": 20,
  "timestamp": 1733097600
}
```

**파라미터:**
- `stock`: 설정할 재고 수량 (0~30)

**ESP32 응답:** `stock_updated` 이벤트

---

### 4. STOP - 긴급 정지
현재 실행 중인 모터 동작을 즉시 중단합니다.

**메시지 포맷:**
```json
{
  "cmd": "STOP",
  "timestamp": 1733097600
}
```

**ESP32 응답:** 즉시 모터 정지 + `status` 이벤트

---

### 5. LOCK / UNLOCK - 기기 잠금/해제
점검 모드를 활성화/비활성화합니다.

**메시지 포맷:**
```json
{
  "cmd": "LOCK",
  "timestamp": 1733097600
}
```

```json
{
  "cmd": "UNLOCK",
  "timestamp": 1733097600
}
```

**잠금 상태일 때:**
- DISPENSE 명령 거부
- STATUS는 응답 가능
- 문 열림/닫힘 감지는 계속 동작

---

### 6. HOME - 강제 홈 복귀
1층 도달까지 자동 이동을 실행합니다.

**메시지 포맷:**
```json
{
  "cmd": "HOME",
  "timestamp": 1733097600
}
```

**ESP32 응답:** 홈 복귀 완료 시 `door_closed` 이벤트, 실패 시 `home_failed`

---

### 7. REBOOT - 재시작
ESP32를 재시작합니다.

**메시지 포맷:**
```json
{
  "cmd": "REBOOT",
  "timestamp": 1733097600
}
```

**ESP32 응답:** 재부팅 후 `boot_complete` 이벤트

---

### 8. CLEAR_ERROR - 에러 초기화
에러 상태를 초기화합니다.

**메시지 포맷:**
```json
{
  "cmd": "CLEAR_ERROR",
  "timestamp": 1733097600
}
```

---

## 이벤트 셋 (ESP32 → 라즈베리파이)

### 정상 작동 이벤트

#### boot_complete - 부팅 완료
ESP32가 부팅을 완료하고 MQTT에 연결되었을 때 발생합니다.
**이 이벤트로 서버에 기기 및 상품이 자동 등록됩니다.**

**메시지 포맷:**
```json
{
  "event": "boot_complete",
  "deviceUUID": "FBOX-004B1238C424",
  "macAddress": "00:4B:12:38:C4:24",
  "category": "top",
  "size": "105",
  "deviceName": "운동복 상의 105",
  "stock": 30,
  "firmwareVersion": "v2.1.0",
  "ipAddress": "192.168.0.28",
  "wifiRssi": -35,
  "timestamp": 1733097600
}
```

**필드 설명:**
- `deviceUUID`: MAC 기반 고유 ID (내부 DB 연결용)
- `macAddress`: 원본 MAC 주소
- `category`: 카테고리 (top/pants/towel/sweat_towel/other)
- `size`: 사이즈 (LCD 표시용)
- `deviceName`: 상품명 (한글 가능, 키오스크 표시용)
- `stock`: 현재 재고
- `firmwareVersion`: 펌웨어 버전
- `ipAddress`: ESP32 IP 주소
- `wifiRssi`: Wi-Fi 신호 강도

**서버 동작:**
1. device_registry 테이블에 기기 등록/업데이트
2. products 테이블에 상품 자동 생성 (device_uuid로 연결)
3. Google Sheets로 동기화

---

#### heartbeat - 생존 신호
1분마다 자동으로 발송되는 생존 신호입니다.

**메시지 포맷:**
```json
{
  "event": "heartbeat",
  "deviceUUID": "FBOX-004B1238C424",
  "stock": 30,
  "doorState": "closed",
  "locked": false,
  "wifiRssi": -35,
  "timestamp": 1733097600
}
```

---

#### status - 상태 보고
STATUS 명령에 대한 응답 또는 주기적 상태 보고입니다.

**메시지 포맷:**
```json
{
  "event": "status",
  "deviceUUID": "FBOX-004B1238C424",
  "size": "105",
  "stock": 30,
  "doorState": "closed",
  "floorState": "reached",
  "locked": false,
  "wifiRssi": -35,
  "timestamp": 1733097600
}
```

**필드 설명:**
- `doorState`: `"open"` 또는 `"closed"`
- `floorState`: `"reached"` (1층 도달) 또는 `"moving"` (이동 중)
- `locked`: `true` (잠금 상태) 또는 `false` (정상 동작)
- `wifiRssi`: Wi-Fi 신호 강도 (dBm)

---

#### dispense_complete - 토출 완료
물품 토출이 성공적으로 완료되었을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "dispense_complete",
  "deviceUUID": "FBOX-004B1238C424",
  "stock": 29,
  "timestamp": 1733097600
}
```

---

#### door_opened - 문 열림
기기 문이 열렸을 때 발생합니다 (재고 보충 시작).

**메시지 포맷:**
```json
{
  "event": "door_opened",
  "deviceUUID": "FBOX-004B1238C424",
  "timestamp": 1733097600
}
```

---

#### door_closed - 문 닫힘
문이 닫히고 홈 복귀가 완료되었을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "door_closed",
  "deviceUUID": "FBOX-004B1238C424",
  "stock": 30,
  "sensorAvailable": false,
  "timestamp": 1733097600
}
```

**필드 설명:**
- `stock`: 현재 재고 (센서가 있으면 자동 감지된 값)
- `sensorAvailable`: 재고 센서 활성화 여부

---

#### stock_updated - 재고 업데이트
재고가 업데이트되었을 때 발생합니다 (SET_STOCK 명령 또는 센서 감지).

**메시지 포맷:**
```json
{
  "event": "stock_updated",
  "deviceUUID": "FBOX-004B1238C424",
  "stock": 30,
  "source": "manual",
  "needsVerification": false,
  "timestamp": 1733097600
}
```

**필드 설명:**
- `source`: `"sensor"` (센서 감지), `"manual"` (수동 설정), `"dispense"` (토출)
- `needsVerification`: 센서 감지 시 관리자 확인 필요 여부

---

### 경고 이벤트

#### stock_low - 재고 부족
재고가 5개 이하로 떨어졌을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "stock_low",
  "deviceId": "FBOX-UPPER-105",
  "stock": 4,
  "timestamp": 1733097600
}
```

---

#### stock_empty - 재고 없음
재고가 0이 되었을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "stock_empty",
  "deviceId": "FBOX-UPPER-105",
  "stock": 0,
  "timestamp": 1733097600
}
```

---

### 에러 이벤트

#### error - 일반 에러
일반적인 에러가 발생했을 때 사용합니다.

**메시지 포맷:**
```json
{
  "event": "error",
  "deviceId": "FBOX-UPPER-105",
  "errorCode": "E001",
  "errorMessage": "Unknown command received",
  "timestamp": 1733097600
}
```

**에러 코드:**
- `E001`: Unknown command
- `E002`: Invalid parameter
- `E003`: Insufficient stock
- `E004`: Device locked
- `E999`: Unknown error

---

#### dispense_failed - 토출 실패
토출 명령이 실패했을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "dispense_failed",
  "deviceId": "FBOX-UPPER-105",
  "reason": "motor_stuck",
  "stock": 15,
  "timestamp": 1733097600
}
```

**실패 원인:**
- `motor_stuck`: 모터 멈춤
- `no_stock`: 재고 없음
- `door_open`: 문 열림 상태
- `device_locked`: 기기 잠금 상태

---

#### home_failed - 홈 복귀 실패
1층 복귀가 실패했을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "home_failed",
  "deviceId": "FBOX-UPPER-105",
  "reason": "limit_switch_error",
  "timestamp": 1733097600
}
```

---

#### motor_error - 모터 이상
모터에 이상이 감지되었을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "motor_error",
  "deviceId": "FBOX-UPPER-105",
  "errorMessage": "Motor overcurrent detected",
  "timestamp": 1733097600
}
```

---

### 네트워크 이벤트

#### wifi_reconnected - Wi-Fi 재연결
Wi-Fi 연결이 끊겼다가 재연결되었을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "wifi_reconnected",
  "deviceId": "FBOX-UPPER-105",
  "ipAddress": "192.168.1.100",
  "timestamp": 1733097600
}
```

---

#### mqtt_reconnected - MQTT 재연결
MQTT 연결이 끊겼다가 재연결되었을 때 발생합니다.

**메시지 포맷:**
```json
{
  "event": "mqtt_reconnected",
  "deviceId": "FBOX-UPPER-105",
  "timestamp": 1733097600
}
```

---

## 락카 배정 메시지 (락카키 대여기 → 운동복 대여기)

락카키 대여기가 운동복 대여기에 락카 배정 정보를 전송합니다.

**토픽:** `fbox/locker/assigned`

**메시지 포맷:**
```json
{
  "locker_number": 105,
  "member_id": "A001",
  "assigned_at": "2024-12-01T10:00:00"
}
```

**또는 HTTP POST 방식:**
```
POST http://{라즈베리파이IP}/api/locker/assign
Content-Type: application/json

{
  "locker": 105,
  "member": "A001"
}
```

---

## QoS (Quality of Service)

### 권장 QoS 레벨

| 토픽 | QoS | 이유 |
|------|-----|------|
| `fbox/{deviceId}/cmd` | 1 | 명령이 최소 1번은 전달되어야 함 |
| `fbox/{deviceId}/status` | 0 | 주기적으로 전송되므로 손실 허용 |
| `heartbeat` | 0 | 주기적 전송, 손실 허용 |
| `dispense_complete` | 1 | 중요 이벤트, 반드시 전달 |
| `error` | 1 | 에러는 반드시 기록 |

---

## 재연결 로직

### ESP32 측
1. Wi-Fi 연결 끊김 감지 → 재연결 시도 (최대 20회)
2. MQTT 연결 끊김 감지 → 재연결 시도 (무한 재시도)
3. 재연결 성공 시 → `boot_complete` 또는 `mqtt_reconnected` 이벤트 전송

### 라즈베리파이 측
1. ESP32로부터 heartbeat 2분 이상 없음 → 오프라인 상태로 표시
2. 재연결 이벤트 수신 시 → `STATUS` 명령으로 상태 동기화

---

## 메시지 크기 제한

- 최대 메시지 크기: 256 bytes
- JSON 메시지는 압축하지 않음 (가독성 우선)
- 큰 데이터는 분할 전송하지 않음 (현재 필요 없음)

---

## 보안 고려사항

### 현재 (개발 단계)
- 인증 없음 (`allow_anonymous true`)
- 암호화 없음 (평문 전송)

### 향후 (프로덕션)
- MQTT 사용자 인증 추가
- TLS/SSL 암호화 (포트 8883)
- 토픽별 ACL (Access Control List) 설정

---

## 예제 시나리오

### 시나리오 1: 정상 토출
```
1. 라즈베리파이 → ESP32
   Topic: fbox/FBOX-UPPER-105/cmd
   {"cmd": "DISPENSE", "timestamp": 1733097600}

2. ESP32 → 라즈베리파이
   Topic: fbox/FBOX-UPPER-105/status
   {"event": "dispense_complete", "deviceId": "FBOX-UPPER-105", "stock": 14, ...}
```

### 시나리오 2: 토출 실패 (재고 없음)
```
1. 라즈베리파이 → ESP32
   Topic: fbox/FBOX-UPPER-105/cmd
   {"cmd": "DISPENSE", "timestamp": 1733097600}

2. ESP32 → 라즈베리파이
   Topic: fbox/FBOX-UPPER-105/status
   {"event": "dispense_failed", "reason": "no_stock", "stock": 0, ...}
```

### 시나리오 3: 재고 보충
```
1. ESP32 → 라즈베리파이 (문 열림)
   {"event": "door_opened", ...}

2. (관리자가 재고 보충)

3. ESP32 → 라즈베리파이 (문 닫힘)
   {"event": "door_closed", "stock": 15, "sensorAvailable": false, ...}

4. 라즈베리파이 → ESP32 (수동 재고 설정)
   {"cmd": "SET_STOCK", "stock": 15, ...}

5. ESP32 → 라즈베리파이 (재고 업데이트 확인)
   {"event": "stock_updated", "stock": 15, "source": "manual", ...}
```

---

## 버전 이력

- v1.0 (2024-12-01): 초기 버전

