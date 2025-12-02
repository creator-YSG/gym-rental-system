# F-BOX Google Sheets 데이터베이스 구조

## 개요

F-BOX 시스템의 중앙 데이터 저장소로 Google Sheets를 사용합니다.
각 시트는 하나의 테이블 역할을 하며, 라즈베리파이와 양방향 동기화됩니다.

---

## 스프레드시트 구성

하나의 Google Spreadsheet에 여러 시트(탭)를 포함합니다:

**스프레드시트 이름:** `F-BOX 관리 시스템`

**시트 목록:**
1. `members` - 회원 정보
2. `products` - 상품 가격표
3. `locker_assignments` - 락카 배정 이력
4. `rental_history` - 대여 이력
5. `usage_history` - 횟수 변동 이력
6. `device_status` - 기기 현황
7. `config` - 시스템 설정 (선택)

---

## 시트 1: members (회원 정보)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| member_id | TEXT | O | 회원 고유 ID | A001 |
| name | TEXT | O | 회원 이름 | 홍길동 |
| phone | TEXT | | 전화번호 | 010-1234-5678 |
| remaining_count | NUMBER | O | 남은 횟수 | 7 |
| total_charged | NUMBER | O | 누적 충전 횟수 | 10 |
| total_used | NUMBER | O | 누적 사용 횟수 | 3 |
| created_at | DATETIME | O | 가입일시 | 2024-12-01 09:00:00 |
| updated_at | DATETIME | O | 최종 수정일시 | 2024-12-01 10:05:00 |
| status | TEXT | | 회원 상태 | active, inactive, suspended |
| notes | TEXT | | 비고 | |

### 예시 데이터

```
| member_id | name   | phone         | remaining_count | total_charged | total_used | created_at          | updated_at          | status | notes |
|-----------|--------|---------------|-----------------|---------------|------------|---------------------|---------------------|--------|-------|
| A001      | 홍길동 | 010-1234-5678 | 7               | 10            | 3          | 2024-12-01 09:00:00 | 2024-12-01 10:05:00 | active |       |
| A002      | 김철수 | 010-2345-6789 | 5               | 5             | 0          | 2024-12-01 09:30:00 | 2024-12-01 09:30:00 | active |       |
```

### 횟수 기반 대여 시스템
- 대여 1개 = 1회 차감
- 예: 상의 1 + 하의 1 + 수건 1 = 총 3회 차감

### 데이터 흐름
- **라즈베리파이 → Sheets**: 대여 시 remaining_count, total_used 업데이트
- **Sheets → 라즈베리파이**: 부팅 시 전체 회원 정보 동기화 (5분마다)

---

## 시트 2: products (상품 정보)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| product_id | TEXT | O | 상품 고유 ID (자동 생성) | P-TOP-105 |
| gym_id | TEXT | O | 헬스장 ID | GYM001 |
| category | TEXT | O | 카테고리 | top, pants, towel, sweat_towel, other |
| size | TEXT | | 사이즈 | 95, 100, 105, FREE |
| name | TEXT | O | 상품명 (ESP32에서 설정) | 운동복 상의 105 |
| device_uuid | TEXT | O | 연결된 F-BOX 기기 UUID (MAC 기반) | FBOX-004B1238C424 |
| stock | NUMBER | | 현재 재고 | 15 |
| enabled | BOOLEAN | O | 활성화 여부 | TRUE, FALSE |
| display_order | NUMBER | | 화면 표시 순서 | 1, 2, 3... |
| updated_at | DATETIME | | 최종 수정일시 | 2024-12-01 10:00:00 |

### 카테고리 값
| 영어 값 | 한글 표시 |
|---------|----------|
| top | 상의 |
| pants | 하의 |
| towel | 수건 |
| sweat_towel | 땀수건 |
| other | 기타 |

### 예시 데이터

```
| product_id   | gym_id | category | size | name           | device_uuid        | stock | enabled | display_order | updated_at          |
|--------------|--------|----------|------|----------------|--------------------|-------|---------|---------------|---------------------|
| P-TOP-105    | GYM001 | top      | 105  | 운동복 상의 105 | FBOX-004B1238C424  | 30    | TRUE    | 1             | 2024-12-01 10:00:00 |
| P-PANTS-105  | GYM001 | pants    | 105  | 운동복 하의 105 | FBOX-A1B2C3D4E5F6  | 25    | TRUE    | 11            | 2024-12-01 10:05:00 |
| P-TOWEL-FREE | GYM001 | towel    | FREE | 수건            | FBOX-112233445566  | 50    | TRUE    | 21            | 2024-12-01 10:05:00 |
```

### 상품 자동 생성 플로우
1. **ESP32 설정**: 관리자가 카테고리, 사이즈, 상품명 설정
2. **boot_complete 이벤트**: ESP32가 서버로 정보 전송
3. **자동 생성**: 서버가 products 테이블에 상품 자동 INSERT
4. **device_uuid 연결**: MAC 기반 UUID로 연결되어 상품명 변경해도 기록 유지

### 데이터 흐름
- **ESP32 → 라즈베리파이 → Sheets**: 기기 등록 시 상품 자동 생성/업데이트
- **라즈베리파이 → Sheets**: 재고 변동 시 stock 업데이트

### 상품 관리
- ESP32 설정 시 상품 자동 생성 (관리자가 수동 생성 불필요)
- device_uuid로 연결되어 상품명/사이즈 변경해도 대여 기록 유지
- 횟수 기반: 1개 대여 = 1회 차감

---

## 시트 3: locker_assignments (락카 배정 이력)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| id | NUMBER | O | 자동 증가 ID | 1 |
| locker_number | NUMBER | O | 락카 번호 | 105 |
| member_id | TEXT | O | 회원 ID | A001 |
| assigned_at | DATETIME | O | 배정 시각 | 2024-12-01 10:00:00 |
| returned_at | DATETIME | | 반납 시각 | 2024-12-01 12:00:00 |
| status | TEXT | O | 상태 | active, returned |
| notes | TEXT | | 비고 | |

### 예시 데이터

```
| id | locker_number | member_id | assigned_at         | returned_at         | status   | notes |
|----|---------------|-----------|---------------------|---------------------|----------|-------|
| 1  | 105           | A001      | 2024-12-01 10:00:00 |                     | active   |       |
| 2  | 106           | A002      | 2024-12-01 10:05:00 |                     | active   |       |
| 3  | 107           | A003      | 2024-12-01 09:00:00 | 2024-12-01 11:30:00 | returned |       |
```

### 데이터 흐름
- **락카키 대여기 → Sheets**: 락카 배정 시 새 행 추가
- **Sheets → 라즈베리파이**: 락카 반납 시 returned_at 업데이트 (수동 또는 자동)

---

## 시트 4: rental_history (대여 이력)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| rental_id | NUMBER | O | 대여 ID (자동 증가) | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| locker_number | NUMBER | | 락카 번호 | 105 |
| product_id | TEXT | O | 상품 ID | P-TOP-105 |
| product_name | TEXT | | 상품명 | 운동복 상의 105 |
| device_uuid | TEXT | O | 기기 UUID (MAC 기반) | FBOX-004B1238C424 |
| quantity | NUMBER | O | 수량 (= 차감 횟수) | 1 |
| count_before | NUMBER | O | 대여 전 잔여 횟수 | 10 |
| count_after | NUMBER | O | 대여 후 잔여 횟수 | 9 |
| created_at | DATETIME | O | 대여 시각 | 2024-12-01 10:05:00 |

### 예시 데이터

```
| rental_id | member_id | locker | product_id   | product_name       | device_uuid        | qty | count_before | count_after | created_at          |
|-----------|-----------|--------|--------------|--------------------|--------------------|-----|--------------|-------------|---------------------|
| 1         | A001      | 105    | P-TOP-105    | 운동복 상의 105     | FBOX-004B1238C424  | 1   | 10           | 9           | 2024-12-01 10:05:00 |
| 2         | A001      | 105    | P-PANTS-105  | 운동복 하의 105     | FBOX-A1B2C3D4E5F6  | 1   | 9            | 8           | 2024-12-01 10:05:01 |
| 3         | A001      | 105    | P-TOWEL-FREE | 수건               | FBOX-112233445566  | 1   | 8            | 7           | 2024-12-01 10:05:02 |
```

**참고**: 1개 대여 = 1회 차감 (qty = 차감 횟수)

### 데이터 흐름
- **라즈베리파이 → Sheets**: 대여 발생 시 새 행 추가 (5초 배치)

### 통계 활용
- 일별/주별/월별 대여 현황
- 상품별 인기도 분석
- 회원별 사용 패턴 분석

---

## 시트 5: usage_history (횟수 변동 이력)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| log_id | NUMBER | O | 로그 ID (자동 증가) | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| amount | NUMBER | O | 변동 횟수 (양수=충전/음수=차감) | +10 |
| count_before | NUMBER | O | 변동 전 잔여 횟수 | 0 |
| count_after | NUMBER | O | 변동 후 잔여 횟수 | 10 |
| type | TEXT | O | 거래 유형 | charge, rental, refund, bonus |
| description | TEXT | | 설명 | 10회 충전 |
| reference_id | NUMBER | | 참조 ID (rental_id 등) | 1 |
| created_at | DATETIME | O | 발생 시각 | 2024-12-01 09:00:00 |

### 예시 데이터

```
| log_id | member_id | amount | count_before | count_after | type    | description       | reference_id | created_at          |
|--------|-----------|--------|--------------|-------------|---------|-------------------|--------------|---------------------|
| 1      | A001      | +10    | 0            | 10          | charge  | 10회 충전         |              | 2024-12-01 09:00:00 |
| 2      | A001      | -1     | 10           | 9           | rental  | 운동복 상의 105   | 1            | 2024-12-01 10:05:00 |
| 3      | A001      | -1     | 9            | 8           | rental  | 운동복 하의 105   | 2            | 2024-12-01 10:05:01 |
| 4      | A001      | -1     | 8            | 7           | rental  | 수건              | 3            | 2024-12-01 10:05:02 |
| 5      | A002      | +10    | 0            | 10          | charge  | 10회 충전         |              | 2024-12-01 09:30:00 |
| 6      | A002      | +1     | 10           | 11          | bonus   | 충전 보너스 1회   |              | 2024-12-01 09:30:01 |
```

### 데이터 흐름
- **라즈베리파이 → Sheets**: 모든 횟수 변동 시 새 행 추가

### 통계 활용
- 회원별 충전/사용 패턴
- 대여 횟수 현황
- 프로모션 효과 분석

---

## 시트 6: device_status (기기 현황)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| device_uuid | TEXT | O | 기기 UUID (MAC 기반) | FBOX-004B1238C424 |
| mac_address | TEXT | O | MAC 주소 | 00:4B:12:38:C4:24 |
| device_name | TEXT | | 상품명 (ESP32에서 설정) | 운동복 상의 105 |
| category | TEXT | | 카테고리 | top, pants, towel, sweat_towel, other |
| size | TEXT | | 사이즈 | 105 |
| stock | NUMBER | O | 현재 재고 | 30 |
| status | TEXT | O | 상태 | online, offline |
| wifi_rssi | NUMBER | | Wi-Fi 신호 강도 | -35 |
| last_heartbeat | DATETIME | | 마지막 하트비트 | 2024-12-01 10:10:00 |
| ip_address | TEXT | | IP 주소 | 192.168.0.28 |
| firmware_version | TEXT | | 펌웨어 버전 | v2.1.0 |
| first_seen_at | DATETIME | | 최초 연결 시각 | 2024-12-01 09:00:00 |
| updated_at | DATETIME | O | 최종 업데이트 | 2024-12-01 10:10:00 |

### 예시 데이터

```
| device_uuid        | mac_address       | device_name      | category | size | stock | status | wifi_rssi | last_heartbeat      | ip_address   | firmware_version | first_seen_at       | updated_at          |
|--------------------|-------------------|------------------|----------|------|-------|--------|-----------|---------------------|--------------|------------------|---------------------|---------------------|
| FBOX-004B1238C424  | 00:4B:12:38:C4:24 | 운동복 상의 105   | top      | 105  | 30    | online | -35       | 2024-12-01 10:10:00 | 192.168.0.28 | v2.1.0           | 2024-12-01 09:00:00 | 2024-12-01 10:10:00 |
| FBOX-A1B2C3D4E5F6  | A1:B2:C3:D4:E5:F6 | 운동복 하의 105   | pants    | 105  | 25    | online | -42       | 2024-12-01 10:10:00 | 192.168.0.29 | v2.1.0           | 2024-12-01 09:05:00 | 2024-12-01 10:10:00 |
```

### 기기 자동 등록 플로우
1. **ESP32 부팅**: boot_complete 이벤트 발생
2. **서버 수신**: device_registry + device_cache 테이블에 저장
3. **Sheets 동기화**: device_status 시트에 반영

### 데이터 흐름
- **ESP32 → 라즈베리파이 → Sheets**: 
  - boot_complete 시 기기 등록 (MAC, IP, 펌웨어 버전 등)
  - Heartbeat 수신 시 last_heartbeat, wifi_rssi 업데이트
  - 토출 완료 시 stock 업데이트

### 모니터링 활용
- 실시간 기기 상태 대시보드
- 재고 부족 알림
- 오프라인 기기 감지 (heartbeat 2분 이상 없으면 offline)

---

## 시트 7: config (시스템 설정) [선택 사항]

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| key | TEXT | O | 설정 키 | mqtt_broker_host |
| value | TEXT | O | 설정 값 | 192.168.1.10 |
| description | TEXT | | 설명 | MQTT 브로커 주소 |
| category | TEXT | | 카테고리 | network, pricing, system |
| updated_at | DATETIME | | 최종 수정 | 2024-12-01 10:00:00 |

### 예시 데이터

```
| key                  | value           | description           | category | updated_at          |
|----------------------|-----------------|-----------------------|----------|---------------------|
| mqtt_broker_host     | 192.168.1.10    | MQTT 브로커 주소      | network  | 2024-12-01 10:00:00 |
| mqtt_broker_port     | 1883            | MQTT 브로커 포트      | network  | 2024-12-01 10:00:00 |
| stock_low_threshold  | 5               | 재고 부족 임계값      | system   | 2024-12-01 10:00:00 |
```

---

## Google Sheets API 사용

### 인증 설정

1. **Google Cloud Console** 에서 프로젝트 생성
2. **Google Sheets API** 활성화
3. **서비스 계정** 생성 및 JSON 키 다운로드
4. 스프레드시트를 서비스 계정 이메일과 공유 (편집 권한)

### Python 라이브러리

```bash
pip install gspread oauth2client
```

### 예제 코드

```python
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 인증
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# 스프레드시트 열기
sheet = client.open('F-BOX 관리 시스템')

# 특정 시트(탭) 선택
members_sheet = sheet.worksheet('members')

# 데이터 읽기
members = members_sheet.get_all_records()

# 데이터 쓰기
members_sheet.append_row(['A003', '박영희', '010-3456-7890', 10000, 10000, 0, ...])

# 특정 셀 업데이트
members_sheet.update_cell(2, 4, 9)  # 2행 4열(remaining_count)을 9로 업데이트
```

---

## 동기화 전략

### 라즈베리파이 → Google Sheets (업로드)

| 데이터 | 주기 | 방식 |
|--------|------|------|
| 대여 이력 | 5초 배치 | 누적된 rental_logs 일괄 업로드 |
| 횟수 변동 | 5초 배치 | 누적된 usage_logs 일괄 업로드 |
| 잔여 횟수 | 대여 시 | members 시트의 remaining_count 컬럼 업데이트 |
| 기기 상태 | 1분마다 | device_status 시트 전체 업데이트 |
| 재고 변동 | 즉시 | products 시트의 stock 컬럼 업데이트 |

### Google Sheets → 라즈베리파이 (다운로드)

| 데이터 | 주기 | 방식 |
|--------|------|------|
| 회원 정보 | 5분마다 | members 시트 전체 다운로드 → SQLite 동기화 |
| 상품 가격표 | 1시간마다 | products 시트 전체 다운로드 → SQLite 동기화 |
| 시스템 설정 | 10분마다 | config 시트 다운로드 → 설정 적용 |

---

## API 호출 제한 고려사항

### Google Sheets API 제한
- **무료**: 분당 60회 읽기/쓰기
- **유료**: 분당 500회

### 최적화 방법
1. **배치 처리**: 여러 행을 한 번에 추가 (`append_rows`)
2. **캐싱**: 로컬 SQLite DB에 캐시하여 읽기 호출 최소화
3. **조건부 동기화**: 변경된 데이터만 업데이트

---

## 백업 및 버전 관리

### Google Sheets 자동 백업
- **버전 기록**: Google Sheets는 자동으로 수정 이력 보관 (30일)
- **일일 백업**: Google Apps Script로 매일 자동 백업 스크립트 실행
- **CSV 내보내기**: 주기적으로 CSV 파일로 내보내기

### 백업 스크립트 예시 (Google Apps Script)
```javascript
function dailyBackup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var folder = DriveApp.getFolderById('BACKUP_FOLDER_ID');
  var date = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd');
  var filename = 'F-BOX_Backup_' + date;
  ss.copy(filename).moveTo(folder);
}
```

---

## 대시보드 및 시각화

Google Sheets의 차트 기능을 활용하여 대시보드 구성:

1. **일별 대여 현황** (선 그래프)
2. **상품별 인기도** (막대 그래프)
3. **재고 현황** (테이블 + 조건부 서식)
4. **기기 상태 모니터링** (테이블 + 상태 표시)

---

## 보안 고려사항

1. **서비스 계정 키 파일**: 절대 public 저장소에 업로드 금지
2. **스프레드시트 공유**: 필요한 계정에만 최소 권한 부여
3. **데이터 암호화**: 민감한 정보 (전화번호 등)는 마스킹 처리
4. **접근 로그**: Google Sheets 수정 이력 정기 확인

---

## 마이그레이션 계획

나중에 PostgreSQL 등으로 이전할 경우:

1. Google Sheets 데이터를 CSV로 내보내기
2. PostgreSQL 테이블 생성 (스키마 변환)
3. CSV 데이터 임포트
4. 라즈베리파이 코드 수정 (SQLAlchemy ORM 사용)
5. Google Sheets는 읽기 전용 아카이브로 보존

