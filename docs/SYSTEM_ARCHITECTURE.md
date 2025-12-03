# F-BOX 시스템 아키텍처

## 개요

F-BOX는 헬스장에서 운동복과 수건을 자동으로 대여해주는 IoT 기반 무인 대여 시스템입니다.

---

## 시스템 구성도

```
┌──────────────────────────────────────────────────────────────┐
│                       헬스장 센터                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────┐         ┌─────────────────────┐   │
│  │  락카키 대여기       │         │  운동복/수건 대여기  │   │
│  │  (라즈베리파이 #1)   │◄─ HTTP ─│  (라즈베리파이 #2)  │   │
│  │  + Flask API 서버   │  Pull   │  + Flask 서버       │   │
│  │  + SQLite (락카)    │         │  + MQTT 브로커      │   │
│  └─────────────────────┘         │  + SQLite (대여)    │   │
│                                   └─────────┬───────────┘   │
│                                             │ MQTT           │
│                    ┌────────────────────────┼────────┐       │
│                    │                        │        │       │
│              ┌─────▼─────┐     ┌──────▼─────┐  ┌───▼─────┐ │
│              │ ESP32     │     │ ESP32      │  │ ESP32   │ │
│              │ 상의 105  │     │ 하의 105   │  │ 수건    │ │
│              │ (모터+LCD)│     │ (모터+LCD) │  │(모터+LCD│ │
│              └───────────┘     └────────────┘  └─────────┘ │
│                                                              │
│                           ▲                                  │
│                           │ Google Sheets 동기화             │
│                           ▼                                  │
└───────────────────────────────────────────────────────────┘
                            │
                            │ Internet
                            ▼
                  ┌──────────────────┐
                  │  Google Sheets   │
                  │  (중앙 DB)       │
                  │  - 회원 관리     │
                  │  - 금액권/구독권 │
                  │  - 대여 이력     │
                  │  - 통계/대시보드 │
                  └──────────────────┘
```

### Pull 방식 통신 흐름
```
1. 회원이 락카키 빌림
   락카키 대여기 라즈베리파이: 락카-회원 매핑 저장

2. 회원이 운동복 빌리러 옴 (NFC 태그)
   운동복 대여기 → 락카키 대여기: GET /api/member/by-locker/105
   "105번 락카키는 누구꺼야?"

3. 락카키 대여기 응답
   "A001 홍길동" (회원 ID + 이름만)

4. 운동복 대여기: 로컬 DB에서 금액권/구독권 조회 후 대여 처리
```

---

## 구성 요소

### 1. 락카키 대여기
- **역할**: 회원 인증 및 락카 배정
- **기능**:
  - 회원 인증 (NFC / QR 코드)
  - 락카 번호 배정
  - 회원-락카 매핑 정보 제공 (Pull API)
- **통신**: HTTP GET 응답 → 운동복 대여기

### 2. 라즈베리파이
- **역할**: 중앙 제어 및 통신 허브
- **구성**:
  - **MQTT 브로커** (Mosquitto)
    - ESP32 기기들과 통신
    - 포트: 1883
  - **Flask 웹 서버**
    - REST API 제공
    - 대여 UI (터치스크린)
    - 포트: 5000
  - **SQLite 데이터베이스**
    - 회원, 금액권, 구독권
    - 상품, 대여 로그
    - 트랜잭션 기록
  - **백그라운드 서비스**
    - Google Sheets 동기화 (5분마다 다운로드, 5초마다 업로드)
    - 기기 상태 모니터링

### 3. ESP32 F-BOX 기기
- **역할**: 물리적 대여 실행
- **구성**:
  - ESP32 메인 보드
  - TB6600 스텝 모터 드라이버 + NEMA17 모터
  - ST7789 TFT LCD (240x320)
  - 리미트 스위치 x2 (1층 도달, 문 닫힘)
  - GT2 벨트 시스템
- **기능**:
  - MQTT 명령 수신 (DISPENSE, SET_STOCK 등)
  - 물품 토출 (1회 = 1장)
  - 재고 관리
  - 상태 보고 (heartbeat, 이벤트)

### 4. Google Sheets
- **역할**: 중앙 데이터 저장소
- **시트 구성**:
  - `members`: 회원 정보
  - `products`: 상품 목록 (가격 포함)
  - `voucher_products`: 금액권 상품 종류
  - `member_vouchers`: 회원별 금액권
  - `voucher_transactions`: 금액권 사용 내역
  - `subscription_products`: 구독권 상품 종류
  - `member_subscriptions`: 회원별 구독권
  - `rental_history`: 대여 이력
  - `device_status`: 기기 현황

---

## 데이터 모델

### 금액권/구독권 기반 시스템

회원은 **금액권(voucher)**과 **구독권(subscription)**을 통해 대여합니다.

#### 결제 우선순위
1. 구독권 (일일 무료 한도)
2. 금액권 (잔액에서 차감)

#### 금액권 특징
- 스타벅스 금액권처럼 개별 관리
- 각 금액권마다 별도 유효기간
- 사용자가 어떤 금액권에서 차감할지 선택 가능
- 여러 금액권 쪼개기 결제 지원
- 보너스 금액권은 실제 구매 금액권 소진 시 활성화

#### 구독권 특징
- 기간 내 일일 사용 한도 (예: 상의 1, 하의 1, 수건 1)
- 한도 초과 시 금액권 사용
- 매일 자정(KST) 사용량 리셋

```
회원 (members)
  - member_id
  - name
  - phone
  - status (active, inactive)

금액권 상품 (voucher_products)
  - id, name, price (판매가)
  - amount (충전 금액)
  - bonus_amount (보너스 금액)
  - validity_days (유효기간)

회원 금액권 (member_vouchers)
  - id, member_id, product_id
  - original_amount (원래 금액)
  - remaining_amount (잔액)
  - status (active, pending, exhausted, expired)
  - valid_from, valid_until
  - parent_voucher_id (보너스인 경우)

구독권 상품 (subscription_products)
  - id, name, price
  - validity_days
  - daily_limit_top, daily_limit_pants, daily_limit_towel

회원 구독권 (member_subscriptions)
  - id, member_id, product_id
  - status, valid_from, valid_until
  - daily_limit_top, daily_limit_pants, daily_limit_towel

상품 (products)
  - product_id
  - category (top, pants, towel)
  - size (95, 100, 105...)
  - price (대여 가격, 기본 1000원)
  - device_uuid (연결된 F-BOX)
```

---

## 통신 프로토콜

### MQTT (라즈베리파이 ↔ ESP32)

**토픽 구조:**
```
fbox/{deviceId}/cmd      # 명령 (라즈베리파이 → ESP32)
fbox/{deviceId}/status   # 이벤트 (ESP32 → 라즈베리파이)
```

**주요 명령:**
- `DISPENSE`: 토출
- `SET_STOCK <n>`: 재고 설정
- `STATUS`: 상태 조회

**주요 이벤트:**
- `boot_complete`: 부팅 완료
- `heartbeat`: 생존 신호 (1분마다)
- `dispense_complete`: 토출 완료
- `dispense_failed`: 토출 실패
- `door_closed`: 문 닫힘 + 홈 복귀

자세한 내용: `docs/MQTT_PROTOCOL.md`

### HTTP REST API

#### 락카키 대여기 API (Pull 방식)
```
GET  /api/member/by-locker/{locker_number}  # 락카로 회원 조회
POST /api/locker/assign     # 락카 배정 (내부용)
POST /api/locker/release    # 락카 해제 (내부용)
GET  /api/locker/list       # 현재 배정된 락카 목록
```

**응답 예시:**
```json
{
  "status": "ok",
  "locker_number": 105,
  "member_id": "A001",
  "name": "홍길동",
  "assigned_at": "2024-12-01T10:00:00"
}
```

#### 운동복 대여기 API
```
POST /api/auth/phone              # 전화번호 로그인
GET  /api/products                # 상품 목록 (가격 포함)
GET  /api/payment-methods/{id}    # 결제 수단 조회
GET  /api/member/{id}/cards       # 마이페이지 (금액권/구독권 목록)
POST /api/rental/subscription     # 구독권으로 대여
POST /api/rental/voucher          # 금액권으로 대여
```

자세한 내용: `docs/API_SPECIFICATION.md`

---

## 주요 플로우

### 1. 락카키 배정
```
1. 회원 인증 (락카키 대여기)
2. 락카 105번 배정
3. SQLite에 락카-회원 매핑 저장
4. Google Sheets 기록 (비동기)
```

### 2. 운동복/수건 대여 (Pull 방식)
```
1. 락카키 NFC 태그 (105번)
2. 락카키 대여기 API 호출: GET /api/member/by-locker/105
   → 회원 ID + 이름만 반환
3. 로컬 DB에서 금액권/구독권 조회
4. 상품 선택 화면 표시 (가격 + 사용 가능 횟수)
5. 결제 수단 선택 (구독권 or 금액권)
6. 트랜잭션:
   - 구독권: 일일 사용량 기록
   - 금액권: 잔액 차감 + voucher_transactions 기록
   - rental_logs 기록
7. MQTT 명령 전송: DISPENSE
8. ESP32 토출 완료 이벤트 수신
9. Google Sheets 동기화
```

### 3. 금액권 쪼개기 결제
```
1. 상품 선택: 상의 1개 (1,000원)
2. 금액권 A 잔액 200원, 금액권 B 잔액 5,000원
3. 금액권 A에서 200원, 금액권 B에서 800원 선택
4. DISPENSE 성공 시:
   - voucher_transactions 2건 생성
   - 금액권 A: 200원 → 0원 (exhausted)
   - 금액권 B: 5,000원 → 4,200원
   - 금액권 A 연결 보너스 금액권 활성화
```

---

## 기술 스택

### 라즈베리파이 (Python)
- **Flask**: 웹 서버 / REST API
- **Mosquitto**: MQTT 브로커
- **SQLite**: 로컬 데이터베이스
- **paho-mqtt**: MQTT 클라이언트
- **gspread**: Google Sheets API

### ESP32 (C++/Arduino)
- **WiFi**: 네트워크 연결
- **PubSubClient**: MQTT 클라이언트
- **Adafruit GFX / ST7789**: LCD 제어
- **NVS (Preferences)**: 설정 저장

### 클라우드
- **Google Sheets**: 중앙 데이터 저장소
- **Google Sheets API**: 데이터 동기화

---

## 디렉토리 구조

```
gym-rental-system/
├── app/                          # Flask 애플리케이션
│   ├── routes/
│   │   ├── main.py               # 대여 UI 라우트
│   │   └── api_locker.py         # 락카키 대여기 API
│   ├── services/
│   │   ├── local_cache.py        # SQLite + 메모리 캐시
│   │   ├── rental_service.py     # 대여 비즈니스 로직
│   │   ├── mqtt_service.py       # MQTT 통신
│   │   └── sheets_sync.py        # Google Sheets 동기화
│   └── templates/                # 웹 UI 템플릿
├── database/
│   ├── local_schema.sql          # SQLite 스키마
│   └── migrate_to_voucher_system.py  # 마이그레이션 스크립트
├── docs/
│   ├── MQTT_PROTOCOL.md          # MQTT 통신 규격
│   ├── GOOGLE_SHEETS_SCHEMA.md   # Google Sheets 구조
│   ├── API_SPECIFICATION.md      # REST API 명세
│   └── SYSTEM_ARCHITECTURE.md    # 이 문서
├── esp32code/
│   └── ...                       # ESP32 펌웨어
├── instance/
│   └── fbox_local.db             # SQLite DB 파일
├── config/
│   └── credentials.json          # Google 서비스 계정 키
├── requirements.txt              # Python 패키지 목록
└── run.py                        # 메인 실행 파일
```

---

## 버전 이력

- **v1.0.0** (2024-12-01): 초기 시스템 설계 (횟수 기반)
- **v2.0.0** (2024-12-02): MQTT 통신 및 ESP32 연동 구현
- **v3.0.0** (2024-12-03): 금액권/구독권 기반 시스템으로 전환
