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
   "A001 홍길동, 잔여 횟수 10회"

4. 운동복 대여기: 대여 처리 + MQTT 명령 전송
```

---

## 구성 요소

### 1. 락카키 대여기
- **역할**: 회원 인증 및 락카 배정
- **기능**:
  - 회원 인증 (NFC / QR 코드)
  - 락카 번호 배정
  - 운동복 대여기에 회원-락카 매핑 정보 전송
- **통신**: HTTP POST → 라즈베리파이

### 2. 라즈베리파이
- **역할**: 중앙 제어 및 통신 허브
- **구성**:
  - **MQTT 브로커** (Mosquitto)
    - ESP32 기기들과 통신
    - 포트: 1883
  - **Flask 웹 서버**
    - REST API 제공 (락카키 대여기용)
    - 관리자 웹 UI
    - 포트: 5000
  - **SQLite 데이터베이스**
    - 로컬 캐시 (회원, 상품, 락카 매핑)
    - 트랜잭션 로그
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
  - `members`: 회원 정보 (잔여 횟수, 사용 이력)
  - `products`: 상품 목록
  - `rental_history`: 대여 이력
  - `usage_history`: 횟수 변동 이력
  - `device_status`: 기기 현황
  - `locker_assignments`: 락카 배정 이력

---

## 데이터 모델

### 횟수 기반 시스템

회원은 **잔여 횟수(remaining_count)**를 보유하고, 대여 시 **1개당 1회** 차감합니다.
예: 상의 1개 + 하의 1개 + 수건 1개 = 총 3회 차감

```
회원 (members)
  - member_id
  - name
  - remaining_count ← 잔여 횟수
  - total_charged (누적 충전 횟수)
  - total_used (누적 사용 횟수)

상품 (products)
  - product_id
  - category (upper, lower, towel)
  - size (95, 100, 105, 110, 115...)
  - device_id ← 연결된 F-BOX

대여 (rental_logs)
  - member_id
  - product_id
  - quantity ← 대여 수량 (= 차감 횟수)
  - count_before
  - count_after
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
- `door_closed`: 문 닫힘 + 홈 복귀
- `stock_low`: 재고 부족

자세한 내용: `docs/MQTT_PROTOCOL.md`

### HTTP REST API

#### 락카키 대여기 API (락카키 대여기 라즈베리파이에서 실행)

**운동복 대여기가 호출하는 API (Pull 방식):**
```
GET  /api/member/by-locker/{locker_number}  # 락카로 회원 조회 ⭐ 핵심
```

**락카키 대여기 내부용 API:**
```
POST /api/locker/assign     # 락카 배정 (내부용)
POST /api/locker/release    # 락카 해제 (내부용)
GET  /api/locker/list       # 현재 배정된 락카 목록
GET  /api/member/{id}       # 회원 정보 조회
```

#### Pull 방식 동작
```
1. 회원이 락카키 빌림 → 락카키 대여기만 알고 있음
2. 회원이 운동복 빌리러 옴 → NFC 태그
3. 운동복 대여기 → 락카키 대여기: "105번 키 누구꺼야?"
4. 락카키 대여기 → 운동복 대여기: "A001 홍길동, 잔여 10회"
5. 운동복 대여기: 대여 진행
```

**장점:**
- 락카만 빌리고 운동복 안 빌리는 사람은 불필요한 API 호출 없음
- 항상 최신 정보 조회
- 운동복 대여기가 락카 매핑 데이터를 저장할 필요 없음

---

## 주요 플로우

### 1. 락카키 배정 (락카키 대여기에서 처리)
```
1. 회원 인증 (락카키 대여기)
2. 락카 105번 배정
3. 내부 API로 SQLite에 락카-회원 매핑 저장
4. Google Sheets 기록 (비동기)
*** 운동복 대여기에는 아직 전달 안 함 ***
```

### 2. 운동복/수건 대여 (Pull 방식)
```
1. 락카키 NFC 태그 (105번)
2. 락카키 대여기 API 호출: GET /api/member/by-locker/105
   *** 이때 락카키 대여기에서 회원 정보 받아옴 ***
3. 회원 잔여 횟수 확인 (10회)
4. 상품 선택 화면 표시
5. 사용자 선택 (상의 1 + 하의 1 + 수건 1 = 3회 차감)
6. 트랜잭션 (운동복 대여기에서):
   - 횟수 차감 (10회 → 7회)
   - rental_logs 기록
   - usage_logs 기록
7. MQTT 명령 전송:
   - DISPENSE → FBOX-UPPER-105
   - DISPENSE → FBOX-LOWER-105
   - DISPENSE x2 → FBOX-TOWEL-01
8. ESP32 토출 실행
9. dispense_complete 이벤트 수신
10. Google Sheets 동기화 (5초 배치)
```

### 3. 재고 보충
```
1. 관리자가 F-BOX 문 열기
2. ESP32: door_opened 이벤트
3. 재고 보충 (15개 넣음)
4. 문 닫기 → 홈 복귀
5. 웹/앱에서 재고 수동 설정
6. MQTT: SET_STOCK 15 명령
7. ESP32: stock_updated 이벤트
8. 재고 동기화 (SQLite, Google Sheets)
```

자세한 내용: `docs/DATA_FLOW.md`

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
│   │   └── api_locker.py         # 락카키 대여기 API
│   ├── services/
│   │   ├── local_cache.py        # SQLite + 메모리 캐시
│   │   ├── mqtt_service.py       # MQTT 통신
│   │   └── sheets_sync.py        # Google Sheets 동기화
│   └── templates/                # 웹 UI 템플릿
├── database/
│   ├── local_schema.sql          # SQLite 스키마
│   └── init_db.py                # DB 초기화 스크립트
├── docs/
│   ├── MQTT_PROTOCOL.md          # MQTT 통신 규격
│   ├── GOOGLE_SHEETS_SCHEMA.md   # Google Sheets 구조
│   ├── DATA_FLOW.md              # 데이터 흐름도
│   └── SYSTEM_ARCHITECTURE.md    # 이 문서
├── esp32code/
│   ├── 251130_2040_v1_wifi       # v1 펌웨어 (Wi-Fi 기본)
│   └── README.md                 # ESP32 펌웨어 설명
├── instance/
│   └── fbox_local.db             # SQLite DB 파일
├── config/
│   └── credentials.json          # Google 서비스 계정 키 (비공개)
├── requirements.txt              # Python 패키지 목록
└── run.py                        # 메인 실행 파일
```

---

## 개발 로드맵

### Phase 1: 기본 인프라 ✅
- [x] SQLite 스키마 설계
- [x] MQTT 프로토콜 문서
- [x] Google Sheets 구조 설계

### Phase 2: 핵심 기능 ✅
- [x] LocalCache 구현
- [x] MQTTService 구현
- [x] 락카키 대여기 API
- [x] Google Sheets 동기화

### Phase 3: ESP32 펌웨어
- [ ] MQTT 통신 코드 추가
- [ ] 재고 카운트 로직
- [ ] 센서 감지 (재고 자동 인식)

### Phase 4: 웹 UI
- [ ] 관리자 대시보드
- [ ] 기기 상태 모니터링
- [ ] 재고 관리 화면
- [ ] 통계/리포트

### Phase 5: 고급 기능
- [ ] 쿠폰 시스템
- [ ] 프로모션 이벤트
- [ ] 오프라인 모드
- [ ] 에러 복구 로직

---

## 배포

### 라즈베리파이 설정
1. Mosquitto 설치
```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
```

2. Python 환경 설정
```bash
cd /home/pi/gym-rental-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. 데이터베이스 초기화
```bash
python database/init_db.py
```

4. Google 서비스 계정 설정
- `config/credentials.json` 파일 배치
- 스프레드시트 공유 (편집 권한)

5. 서비스 시작
```bash
python run.py
```

자세한 내용: `docs/RASPBERRY_PI_SETUP.md`

---

## 보안

### 현재 (개발 단계)
- MQTT: 인증 없음 (allow_anonymous)
- HTTP: 인증 없음
- Google Sheets: 서비스 계정 키 파일

### 향후 (프로덕션)
- [ ] MQTT TLS/SSL 암호화
- [ ] MQTT 사용자 인증
- [ ] HTTP 토큰 인증
- [ ] Google Sheets 접근 제한
- [ ] 데이터 암호화

---

## 라이선스

MIT License

---

## 연락처

프로젝트 관리자: [yunseong-geun]

---

## 버전 이력

- **v1.0.0** (2024-12-01): 초기 시스템 설계 및 문서화
- **v1.1.0** (2024-12-01): 금액 기반 시스템으로 전환
- **v2.0.0** (계획): MQTT 통신 및 전체 시스템 통합

