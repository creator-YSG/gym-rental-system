# F-BOX Google Sheets 데이터베이스 구조

## 개요

F-BOX 시스템의 중앙 데이터 저장소로 Google Sheets를 사용합니다.
각 시트는 하나의 테이블 역할을 하며, 라즈베리파이와 양방향 동기화됩니다.

**결제 방식**: 금액권/구독권 기반 시스템
- **금액권**: 스타벅스 금액권처럼 개별 잔액/유효기간 관리
- **구독권**: 기간 내 일일 횟수 제한 이용권

---

## 스프레드시트 구성

하나의 Google Spreadsheet에 여러 시트(탭)를 포함합니다:

**스프레드시트 이름:** `F-BOX-DB-TEST`

**시트 목록:**
1. `members` - 회원 정보
2. `products` - 대여 상품 (가격 포함)
3. `voucher_products` - 금액권 상품
4. `member_vouchers` - 회원 보유 금액권
5. `voucher_transactions` - 금액권 거래 내역
6. `subscription_products` - 구독 상품
7. `member_subscriptions` - 회원 보유 구독권
8. `subscription_usage` - 구독권 일일 사용량
9. `rental_history` - 대여 이력
10. `locker_assignments` - 락카 배정 이력
11. `device_status` - 기기 현황
12. `event_logs` - 비즈니스 이벤트 로그
13. `mqtt_events` - MQTT 이벤트 로그
14. `config` - 시스템 설정

---

## 시트 1: members (회원 정보)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| member_id | TEXT | O | 회원 고유 ID | A001 |
| name | TEXT | O | 회원 이름 | 홍길동 |
| phone | TEXT | | 전화번호 | 010-1234-5678 |
| status | TEXT | O | 회원 상태 | active, inactive, suspended |
| created_at | DATETIME | O | 가입일시 | 2024-12-01 09:00:00 |
| updated_at | DATETIME | O | 최종 수정일시 | 2024-12-01 10:05:00 |
| notes | TEXT | | 비고 | |

### 예시 데이터

```
| member_id | name   | phone         | status | created_at          | updated_at          | notes    |
|-----------|--------|---------------|--------|---------------------|---------------------|----------|
| A001      | 홍길동 | 010-1234-5678 | active | 2024-12-01 09:00:00 | 2024-12-01 10:05:00 |          |
| A002      | 김철수 | 010-2345-6789 | active | 2024-12-01 09:30:00 | 2024-12-01 09:30:00 | VIP 회원 |
```

### 데이터 흐름
- **Sheets → 라즈베리파이**: 부팅 시 전체 회원 정보 동기화 (5분마다)
- **라즈베리파이 → Sheets**: 회원 상태 변경 시 업데이트

---

## 시트 2: products (대여 상품)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| product_id | TEXT | O | 상품 고유 ID | P-TOP-105 |
| gym_id | TEXT | O | 헬스장 ID | GYM001 |
| category | TEXT | O | 카테고리 | top, pants, towel, sweat_towel, other |
| size | TEXT | | 사이즈 | 95, 100, 105, FREE |
| name | TEXT | O | 상품명 | 운동복 상의 105 |
| price | NUMBER | O | 대여 가격 (원) | 1000 |
| device_uuid | TEXT | O | 연결된 F-BOX 기기 UUID | FBOX-004B1238C424 |
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
| product_id   | gym_id | category | size | name           | price | device_uuid        | stock | enabled | display_order |
|--------------|--------|----------|------|----------------|-------|--------------------|-------|---------|---------------|
| P-TOP-105    | GYM001 | top      | 105  | 운동복 상의 105 | 1000  | FBOX-004B1238C424  | 30    | TRUE    | 1             |
| P-PANTS-105  | GYM001 | pants    | 105  | 운동복 하의 105 | 1000  | FBOX-A1B2C3D4E5F6  | 25    | TRUE    | 11            |
| P-TOWEL-FREE | GYM001 | towel    | FREE | 수건            | 500   | FBOX-112233445566  | 50    | TRUE    | 21            |
```

### 가격 활용
- 금액권 사용 시: `price` 금액만큼 금액권에서 차감
- 구독권 사용 시: 일일 제한 내 무료, 초과 시 금액권 사용

---

## 시트 3: voucher_products (금액권 상품)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| product_id | TEXT | O | 금액권 상품 ID | VCH-100K |
| name | TEXT | O | 상품명 | 10만원 금액권 |
| price | NUMBER | O | 결제 금액 (원) | 100000 |
| charge_amount | NUMBER | O | 충전 금액 (원) | 100000 |
| validity_days | NUMBER | O | 유효 기간 (일) | 365 |
| bonus_product_id | TEXT | | 연결된 보너스 상품 ID | VCH-BONUS-10K |
| is_bonus | BOOLEAN | O | 보너스 상품 여부 | FALSE |
| enabled | BOOLEAN | O | 활성화 여부 | TRUE |
| created_at | DATETIME | | 생성일시 | |
| updated_at | DATETIME | | 수정일시 | |

### 예시 데이터

```
| product_id     | name           | price  | charge_amount | validity_days | bonus_product_id | is_bonus | enabled |
|----------------|----------------|--------|---------------|---------------|------------------|----------|---------|
| VCH-10K        | 1만원 금액권   | 10000  | 10000         | 365           |                  | FALSE    | TRUE    |
| VCH-50K        | 5만원 금액권   | 50000  | 50000         | 365           |                  | FALSE    | TRUE    |
| VCH-100K       | 10만원 금액권  | 100000 | 100000        | 365           | VCH-BONUS-10K    | FALSE    | TRUE    |
| VCH-BONUS-10K  | 1만원 보너스   | 0      | 10000         | 30            |                  | TRUE     | TRUE    |
```

### 보너스 금액권 정책
- 부모 금액권(`VCH-100K`)의 잔액이 **0원으로 소진**되면 보너스(`VCH-BONUS-10K`) 활성화
- 부모 금액권이 **만료**되면 보너스도 함께 만료

---

## 시트 4: member_vouchers (회원 보유 금액권)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| voucher_id | NUMBER | O | 금액권 ID (자동 증가) | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| voucher_product_id | TEXT | O | 금액권 상품 ID | VCH-100K |
| original_amount | NUMBER | O | 최초 충전 금액 | 100000 |
| remaining_amount | NUMBER | O | 남은 금액 | 45000 |
| parent_voucher_id | NUMBER | | 부모 금액권 ID (보너스용) | 1 |
| valid_from | DATETIME | | 유효 시작일 | 2024-12-01 09:00:00 |
| valid_until | DATETIME | | 유효 종료일 | 2025-12-01 09:00:00 |
| status | TEXT | O | 상태 | pending, active, exhausted, expired |
| created_at | DATETIME | O | 생성일시 | |
| updated_at | DATETIME | | 수정일시 | |

### 상태 값
| 상태 | 설명 |
|------|------|
| pending | 보너스 대기 (미활성) |
| active | 사용 가능 |
| exhausted | 잔액 소진 |
| expired | 기간 만료 |

### 예시 데이터

```
| voucher_id | member_id | voucher_product_id | original | remaining | parent_id | valid_from          | valid_until         | status    |
|------------|-----------|--------------------| ---------|-----------|-----------|---------------------|---------------------|-----------|
| 1          | A001      | VCH-100K           | 100000   | 45000     |           | 2024-12-01 09:00:00 | 2025-12-01 09:00:00 | active    |
| 2          | A001      | VCH-BONUS-10K      | 10000    | 10000     | 1         |                     |                     | pending   |
| 3          | A001      | VCH-50K            | 50000    | 0         |           | 2024-11-01 09:00:00 | 2025-11-01 09:00:00 | exhausted |
| 4          | A002      | VCH-10K            | 10000    | 10000     |           | 2024-10-01 09:00:00 | 2024-11-01 09:00:00 | expired   |
```

### 보너스 활성화 로직
1. `voucher_id=1` (10만원권)의 `remaining_amount`가 0이 되면
2. `parent_voucher_id=1`인 보너스(`voucher_id=2`)를 찾아서
3. `status`를 `active`로 변경
4. `valid_from = NOW()`, `valid_until = NOW() + validity_days`로 설정

---

## 시트 5: voucher_transactions (금액권 거래 내역)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| id | NUMBER | O | 거래 ID | 1 |
| voucher_id | NUMBER | O | 금액권 ID | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| amount | NUMBER | O | 차감/환불 금액 | 1000 |
| balance_before | NUMBER | O | 거래 전 잔액 | 46000 |
| balance_after | NUMBER | O | 거래 후 잔액 | 45000 |
| transaction_type | TEXT | O | 거래 유형 | rental, refund |
| rental_log_id | NUMBER | | 참조 대여 ID | 1 |
| created_at | DATETIME | O | 거래 시각 | 2024-12-01 10:05:00 |

### 예시 데이터 (쪼개기 지원)

```
| id | voucher_id | member_id | amount | balance_before | balance_after | type   | rental_log_id | created_at          |
|----|------------|-----------|--------|----------------|---------------|--------|---------------|---------------------|
| 1  | 1          | A001      | 1000   | 100000         | 99000         | rental | 1             | 2024-12-01 10:05:00 |
| 2  | 1          | A001      | 200    | 99000          | 98800         | rental | 2             | 2024-12-01 10:05:01 |
| 3  | 3          | A001      | 800    | 50000          | 49200         | rental | 2             | 2024-12-01 10:05:01 |
```

**쪼개기 예시**: `rental_log_id=2`의 대여(1000원 상품)를
- `voucher_id=1`에서 200원
- `voucher_id=3`에서 800원
으로 분할 차감

---

## 시트 6: subscription_products (구독 상품)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| product_id | TEXT | O | 구독 상품 ID | SUB-3M-BASIC |
| name | TEXT | O | 상품명 | 3개월 기본 이용권 |
| price | NUMBER | O | 결제 금액 (원) | 120000 |
| validity_days | NUMBER | O | 유효 기간 (일) | 90 |
| daily_limits | TEXT | O | 일일 제한 (JSON) | {"top":1,"pants":1,"towel":1} |
| enabled | BOOLEAN | O | 활성화 여부 | TRUE |
| created_at | DATETIME | | 생성일시 | |
| updated_at | DATETIME | | 수정일시 | |

### 예시 데이터

```
| product_id     | name                   | price  | validity_days | daily_limits                      | enabled |
|----------------|------------------------|--------|---------------|-----------------------------------|---------|
| SUB-1M-BASIC   | 1개월 기본 이용권      | 50000  | 30            | {"top":1,"pants":1,"towel":1}     | TRUE    |
| SUB-3M-BASIC   | 3개월 기본 이용권      | 120000 | 90            | {"top":1,"pants":1,"towel":1}     | TRUE    |
| SUB-3M-PREMIUM | 3개월 프리미엄 이용권  | 180000 | 90            | {"top":2,"pants":2,"towel":3}     | TRUE    |
```

### daily_limits 설명
- `"top":1` → 하루에 상의 1개까지 무료
- 초과 사용 시 금액권에서 차감

---

## 시트 7: member_subscriptions (회원 보유 구독권)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| subscription_id | NUMBER | O | 구독권 ID | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| subscription_product_id | TEXT | O | 구독 상품 ID | SUB-3M-BASIC |
| valid_from | DATETIME | O | 유효 시작일 | 2024-12-01 00:00:00 |
| valid_until | DATETIME | O | 유효 종료일 | 2025-03-01 00:00:00 |
| daily_limits | TEXT | O | 일일 제한 (JSON 복사) | {"top":1,"pants":1,"towel":1} |
| status | TEXT | O | 상태 | active, expired |
| created_at | DATETIME | | 생성일시 | |
| updated_at | DATETIME | | 수정일시 | |

### 예시 데이터

```
| subscription_id | member_id | subscription_product_id | valid_from          | valid_until         | daily_limits                  | status  |
|-----------------|-----------|-------------------------|---------------------|---------------------|-------------------------------|---------|
| 1               | A001      | SUB-3M-BASIC            | 2024-12-01 00:00:00 | 2025-03-01 00:00:00 | {"top":1,"pants":1,"towel":1} | active  |
| 2               | A002      | SUB-1M-BASIC            | 2024-11-01 00:00:00 | 2024-12-01 00:00:00 | {"top":1,"pants":1,"towel":1} | expired |
```

---

## 시트 8: subscription_usage (구독권 일일 사용량)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| id | NUMBER | O | 사용량 ID | 1 |
| subscription_id | NUMBER | O | 구독권 ID | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| usage_date | DATE | O | 사용 날짜 | 2024-12-01 |
| category | TEXT | O | 카테고리 | top, pants, towel |
| used_count | NUMBER | O | 사용 횟수 | 1 |

### 예시 데이터

```
| id | subscription_id | member_id | usage_date | category | used_count |
|----|-----------------|-----------|------------|----------|------------|
| 1  | 1               | A001      | 2024-12-01 | top      | 1          |
| 2  | 1               | A001      | 2024-12-01 | pants    | 1          |
| 3  | 1               | A001      | 2024-12-01 | towel    | 2          |
```

### 일일 리셋
- 한국 시간 **자정(00:00)** 기준으로 새 날짜 레코드 생성
- `usage_date`로 날짜별 카테고리별 사용량 추적

---

## 시트 9: rental_history (대여 이력)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| rental_id | NUMBER | O | 대여 ID | 1 |
| member_id | TEXT | O | 회원 ID | A001 |
| locker_number | NUMBER | | 락카 번호 | 105 |
| product_id | TEXT | O | 상품 ID | P-TOP-105 |
| product_name | TEXT | | 상품명 | 운동복 상의 105 |
| device_uuid | TEXT | O | 기기 UUID | FBOX-004B1238C424 |
| quantity | NUMBER | O | 수량 | 1 |
| payment_type | TEXT | O | 결제 유형 | voucher, subscription |
| subscription_id | NUMBER | | 구독권 ID (구독 사용 시) | 1 |
| amount | NUMBER | O | 차감 금액 (구독이면 0) | 1000 |
| created_at | DATETIME | O | 대여 시각 | 2024-12-01 10:05:00 |

### 결제 유형
| payment_type | 설명 |
|--------------|------|
| voucher | 금액권 사용 (voucher_transactions에 상세 내역) |
| subscription | 구독권 사용 (일일 제한 내 무료) |

### 예시 데이터

```
| rental_id | member_id | locker | product_id   | product_name    | device_uuid        | qty | payment_type | subscription_id | amount | created_at          |
|-----------|-----------|--------|--------------|-----------------|--------------------| ----|--------------|-----------------|--------|---------------------|
| 1         | A001      | 105    | P-TOP-105    | 운동복 상의 105  | FBOX-004B1238C424  | 1   | subscription | 1               | 0      | 2024-12-01 10:05:00 |
| 2         | A001      | 105    | P-TOWEL-FREE | 수건            | FBOX-112233445566  | 2   | voucher      |                 | 1000   | 2024-12-01 10:05:01 |
```

---

## 시트 10: locker_assignments (락카 배정 이력)

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

---

## 시트 11: device_status (기기 현황)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| device_uuid | TEXT | O | 기기 UUID | FBOX-004B1238C424 |
| mac_address | TEXT | O | MAC 주소 | 00:4B:12:38:C4:24 |
| device_name | TEXT | | 상품명 | 운동복 상의 105 |
| category | TEXT | | 카테고리 | top, pants, towel |
| size | TEXT | | 사이즈 | 105 |
| stock | NUMBER | O | 현재 재고 | 30 |
| status | TEXT | O | 상태 | online, offline |
| wifi_rssi | NUMBER | | Wi-Fi 신호 강도 | -35 |
| last_heartbeat | DATETIME | | 마지막 하트비트 | 2024-12-01 10:10:00 |
| ip_address | TEXT | | IP 주소 | 192.168.0.28 |
| firmware_version | TEXT | | 펌웨어 버전 | v2.1.0 |
| first_seen_at | DATETIME | | 최초 연결 시각 | |
| updated_at | DATETIME | O | 최종 업데이트 | |

---

## 시트 12: event_logs (비즈니스 이벤트 로그)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| log_id | NUMBER | O | 로그 ID | 1 |
| timestamp | DATETIME | O | 발생 시각 | 2024-12-01 10:05:00 |
| event_type | TEXT | O | 이벤트 유형 | rental_success, rental_failed, dispense_failed |
| severity | TEXT | O | 심각도 | info, warning, error |
| device_uuid | TEXT | | 기기 UUID | FBOX-004B1238C424 |
| member_id | TEXT | | 회원 ID | A001 |
| product_id | TEXT | | 상품 ID | P-TOP-105 |
| details | TEXT | | 상세 정보 (JSON) | {"quantity": 1, "amount": 1000} |

### 이벤트 유형

| event_type | severity | 설명 |
|------------|----------|------|
| rental_success | info | 대여 성공 |
| rental_failed | error | 대여 실패 |
| dispense_failed | error | 토출 실패 |
| stock_low | warning | 재고 부족 (5개 이하) |
| stock_empty | error | 재고 없음 |
| device_online | info | 기기 온라인 |
| device_offline | warning | 기기 오프라인 |
| door_opened | info | 문 열림 |
| door_closed | info | 문 닫힘 |

---

## 시트 13: mqtt_events (MQTT 이벤트 로그)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| id | NUMBER | O | 이벤트 ID | 1 |
| device_uuid | TEXT | O | 기기 UUID | FBOX-004B1238C424 |
| event_type | TEXT | O | 이벤트 유형 | heartbeat, dispense_complete |
| payload | TEXT | O | 원본 페이로드 (JSON) | {"stock": 10, ...} |
| created_at | DATETIME | O | 수신 시각 | 2024-12-01 10:05:00 |

### 이벤트 유형

| event_type | 설명 |
|------------|------|
| heartbeat | 1분마다 기기 상태 |
| boot_complete | 기기 부팅 완료 |
| dispense_complete | 토출 완료 |
| dispense_failed | 토출 실패 |
| door_opened | 문 열림 |
| door_closed | 문 닫힘 |
| stock_updated | 재고 변동 |

### 보존 정책
- 7일 경과한 `heartbeat` 이벤트는 자동 삭제 (cleanup_logs.py)
- 기타 이벤트는 영구 보존

---

## 시트 14: config (시스템 설정)

### 컬럼 구조

| 컬럼명 | 타입 | 필수 | 설명 | 예시 |
|--------|------|------|------|------|
| key | TEXT | O | 설정 키 | stock_low_threshold |
| value | TEXT | O | 설정 값 | 5 |
| description | TEXT | | 설명 | 재고 부족 임계값 |
| category | TEXT | | 카테고리 | system |
| updated_at | DATETIME | | 최종 수정 | |

---

## 대여 플로우

### 1. 상품 선택
```
회원 → 카테고리 탭 → 상품 선택 (수량)
```

### 2. 결제 수단 선택
```
a) 구독권 확인
   → 활성 구독권 목록 표시
   → 해당 카테고리 오늘 잔여 횟수 표시
   → 사용자 선택

b) 금액권 선택 (구독권 없거나 초과 시)
   → 활성 금액권 목록 표시 (잔액, 유효기간)
   → 사용자 선택
   → 잔액 부족 시 추가 금액권 선택 (쪼개기)
```

### 3. 대여 처리
```
→ DISPENSE 명령 → 성공 시 차감
→ rental_logs 기록
→ voucher_transactions 기록 (금액권 사용 시)
→ subscription_usage 업데이트 (구독권 사용 시)
```

### 4. 보너스 활성화
```
금액권 잔액 0 → 연결된 보너스 금액권 활성화
```

---

## 동기화 전략

### 라즈베리파이 → Google Sheets (업로드)

| 데이터 | 주기 | 방식 |
|--------|------|------|
| 대여 이력 | 5분마다 | rental_history 업로드 |
| 금액권 거래 | 5분마다 | voucher_transactions 업로드 |
| 구독권 사용량 | 5분마다 | subscription_usage 업로드 |
| 이벤트 로그 | 5분마다 | event_logs 업로드 |
| MQTT 이벤트 | 5분마다 | mqtt_events 업로드 |
| 기기 상태 | 1분마다 | device_status 업데이트 |
| 재고 변동 | 즉시 | products.stock 업데이트 |

### Google Sheets → 라즈베리파이 (다운로드)

| 데이터 | 주기 | 방식 |
|--------|------|------|
| 회원 정보 | 5분마다 | members 동기화 |
| 상품 정보 (가격) | 10분마다 | products 동기화 |
| 금액권 상품 | 10분마다 | voucher_products 동기화 |
| 구독 상품 | 10분마다 | subscription_products 동기화 |
| 회원 금액권 | 5분마다 | member_vouchers 동기화 |
| 회원 구독권 | 5분마다 | member_subscriptions 동기화 |
| 시스템 설정 | 10분마다 | config 동기화 |

---

## 유효기간 만료 처리

### 정책
- **조회 시점**에 `valid_until < NOW()` 체크
- 만료 시 `status = 'expired'`로 표시
- 시간대: **한국 시간(KST)** 기준

### 보너스 금액권 만료
- 부모 금액권이 **만료**되면 → pending 상태의 보너스도 만료
- 부모 금액권이 **소진**(잔액 0)되면 → 보너스 활성화

---

## 일일 리셋 (구독권)

### 정책
- 한국 시간 **자정(00:00)** 기준 리셋
- `subscription_usage.usage_date`로 날짜별 관리
- 새 날짜의 첫 사용 시 새 행 생성 (또는 0으로 간주)

---

## API 호출 제한

### Google Sheets API 제한
- **무료**: 분당 60회 읽기/쓰기
- **유료**: 분당 500회

### 최적화 방법
1. **배치 처리**: 여러 행을 한 번에 추가
2. **캐싱**: 로컬 SQLite DB에 캐시
3. **조건부 동기화**: 변경된 데이터만 업데이트
