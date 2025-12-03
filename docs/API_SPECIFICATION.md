# F-BOX REST API 명세서

## 개요

F-BOX 시스템의 REST API 명세입니다.
**결제 방식**: 금액권/구독권 기반 시스템

### 통신 구조 (Pull 방식)

```
[운동복/수건 대여기]                     [락카키 대여기]
       │                                      │
       │  GET /api/member/by-locker/105       │
       │ ─────────────────────────────────────>│
       │                                      │
       │  {"member_id": "A001", "name": "홍길동"}  │
       │ <─────────────────────────────────────│
       │                                      │
```

**왜 Pull 방식인가?**
- 락카만 빌리고 운동복 안 빌리는 사람이 많음
- 불필요한 API 호출 제거
- 항상 최신 정보 조회
- 운동복 대여기가 락카 매핑 데이터를 저장할 필요 없음

---

## 락카키 대여기 API

락카키 대여기 라즈베리파이에서 실행되는 Flask API 서버

**Base URL:** `http://{락카키대여기IP}:5000`

---

### 1. 락카로 회원 조회 (핵심 API)

운동복 대여기에서 NFC 태그 시 호출하는 API

**Endpoint:** `GET /api/member/by-locker/{locker_number}`

**Parameters:**
| 이름 | 위치 | 필수 | 타입 | 설명 |
|------|------|------|------|------|
| locker_number | path | O | int | 락카 번호 |

**Response (200 OK):**
```json
{
  "status": "ok",
  "locker_number": 105,
  "member_id": "A001",
  "name": "홍길동",
  "assigned_at": "2024-12-01T10:00:00"
}
```

**Response (404 Not Found):**
```json
{
  "status": "error",
  "locker_number": 105,
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**참고**: 금액권/구독권 정보는 운동복 대여기 로컬 DB에서 직접 조회

---

### 2. 락카 배정 (내부용)

락카키 대여 시 내부적으로 호출

**Endpoint:** `POST /api/locker/assign`

**Request Body:**
```json
{
  "locker": 105,
  "member": "A001"
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "locker": 105,
  "member_id": "A001",
  "name": "홍길동",
  "assigned_at": "2024-12-01T10:00:00"
}
```

---

### 3. 락카 해제 (내부용)

**Endpoint:** `POST /api/locker/release`

**Request Body:**
```json
{
  "locker": 105
}
```

---

### 4. 배정된 락카 목록 조회

**Endpoint:** `GET /api/locker/list`

**Response (200 OK):**
```json
{
  "status": "ok",
  "count": 3,
  "lockers": [
    {"locker": 105, "member_id": "A001", "name": "홍길동"},
    {"locker": 106, "member_id": "A002", "name": "김철수"}
  ]
}
```

---

### 5. 헬스 체크

**Endpoint:** `GET /api/health`

---

## 운동복/수건 대여기 API

운동복/수건 대여기 라즈베리파이에서 실행되는 Flask API 서버

**Base URL:** `http://{운동복대여기IP}:5000`

---

### 1. 전화번호 로그인

**Endpoint:** `POST /api/auth/phone`

**Request Body:**
```json
{
  "phone": "01012345678"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "member": {
    "member_id": "A001",
    "name": "홍길동",
    "phone": "01012345678",
    "status": "active",
    "total_balance": 50000,
    "active_vouchers_count": 2,
    "active_subscriptions_count": 1
  }
}
```

---

### 2. 상품 목록 조회

**Endpoint:** `GET /api/products`

**Response (200 OK):**
```json
{
  "products": [
    {
      "product_id": "P-TOP-105",
      "name": "운동복 상의 105",
      "category": "top",
      "size": "105",
      "price": 1000,
      "stock": 30,
      "device_uuid": "FBOX-004B1238C424",
      "connected": true,
      "online": true
    }
  ]
}
```

---

### 3. 결제 수단 조회

**Endpoint:** `GET /api/payment-methods/{member_id}`

**Query Parameters:**
| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| category | X | string | 카테고리 (구독권 잔여 횟수 확인용) |

**Response (200 OK):**
```json
{
  "subscriptions": [
    {
      "subscription_id": 1,
      "product_name": "3개월 기본 이용권",
      "valid_until": "2025-03-01T00:00:00",
      "remaining_today": 1,
      "daily_limits": {"top": 1, "pants": 1, "towel": 1}
    }
  ],
  "vouchers": [
    {
      "voucher_id": 1,
      "product_name": "10만원 금액권",
      "remaining_amount": 45000,
      "valid_until": "2025-12-01T00:00:00",
      "status": "active"
    }
  ],
  "total_balance": 45000
}
```

---

### 4. 회원 카드 목록 (마이페이지)

**Endpoint:** `GET /api/member/{member_id}/cards`

**Response (200 OK):**
```json
{
  "subscriptions": [
    {
      "subscription_id": 1,
      "product_name": "3개월 기본 이용권",
      "status": "active",
      "valid_from": "2024-12-01",
      "valid_until": "2025-03-01",
      "daily_limits": {"top": 1, "pants": 1, "towel": 1}
    }
  ],
  "vouchers": [
    {
      "voucher_id": 1,
      "product_name": "10만원 금액권",
      "original_amount": 100000,
      "remaining_amount": 45000,
      "status": "active"
    },
    {
      "voucher_id": 2,
      "product_name": "1만원 보너스",
      "original_amount": 10000,
      "remaining_amount": 10000,
      "status": "pending"
    }
  ]
}
```

---

### 5. 대여 비용 계산

**Endpoint:** `POST /api/rental/calculate`

**Request Body:**
```json
{
  "items": [
    {"product_id": "P-TOP-105", "quantity": 1},
    {"product_id": "P-TOWEL-FREE", "quantity": 2}
  ]
}
```

**Response (200 OK):**
```json
{
  "total_amount": 2000
}
```

---

### 6. 구독권으로 대여

**Endpoint:** `POST /api/rental/subscription`

**Request Body:**
```json
{
  "member_id": "A001",
  "subscription_id": 1,
  "items": [
    {"product_id": "P-TOP-105", "quantity": 1, "device_uuid": "FBOX-..."}
  ]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "대여 완료 (1개)",
  "payment_type": "subscription",
  "dispense_results": [
    {"product_id": "P-TOP-105", "requested": 1, "dispensed": 1, "success": true}
  ]
}
```

---

### 7. 금액권으로 대여 (쪼개기 지원)

**Endpoint:** `POST /api/rental/voucher`

**Request Body:**
```json
{
  "member_id": "A001",
  "items": [
    {"product_id": "P-TOP-105", "quantity": 1, "device_uuid": "FBOX-..."}
  ],
  "voucher_selections": [
    {"voucher_id": 1, "amount": 500},
    {"voucher_id": 2, "amount": 500}
  ]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "대여 완료 (1000원 차감)",
  "payment_type": "voucher",
  "total_amount": 1000,
  "dispense_results": [
    {"product_id": "P-TOP-105", "requested": 1, "dispensed": 1, "success": true}
  ]
}
```

---

### 8. 재고 현황 조회

**Endpoint:** `GET /api/inventory`

---

## 에러 코드

| HTTP 상태 | status | 설명 |
|-----------|--------|------|
| 200 | ok/true | 성공 |
| 400 | error/false | 잘못된 요청 (파라미터 누락/오류) |
| 404 | error/false | 리소스 없음 (회원, 락카, 상품 등) |
| 500 | error/false | 서버 내부 오류 |

---

## 결제 플로우

### 구독권 사용 플로우
```
1. 회원 로그인 → 금액권/구독권 요약 정보 반환
2. 상품 선택 → 카테고리별 가격 표시
3. 결제 수단 선택 → 활성 구독권/금액권 목록 표시
4. 구독권 선택 → 일일 잔여 횟수 확인
5. 대여 처리 → DISPENSE 성공 시에만 사용량 기록
```

### 금액권 사용 플로우 (쪼개기)
```
1. 금액권 A에서 200원, 금액권 B에서 800원 선택
2. 대여 처리 → DISPENSE 성공 시에만 차감
3. voucher_transactions에 쪼개진 거래 기록
4. 금액권 잔액 0 → 연결된 보너스 금액권 활성화
```

---

## 버전 이력

- **v1.0.0** (2024-12-01): 초기 버전 (횟수 기반)
- **v2.0.0** (2024-12-03): 금액권/구독권 기반으로 변경
