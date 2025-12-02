# F-BOX REST API 명세서

## 개요

F-BOX 시스템의 REST API 명세입니다.

### 통신 구조 (Pull 방식)

```
[운동복/수건 대여기]                     [락카키 대여기]
       │                                      │
       │  GET /api/member/by-locker/105       │
       │ ─────────────────────────────────────>│
       │                                      │
       │  {"member": "A001", "remaining_count": ...}  │
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

### 1. 락카로 회원 조회 ⭐ (핵심 API)

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
  "remaining_count": 10,
  "total_charged": 15,
  "total_used": 5,
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

**사용 예시:**
```bash
curl http://192.168.1.10:5000/api/member/by-locker/105
```

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

**Response (400 Bad Request):**
```json
{
  "status": "error",
  "message": "필수 파라미터 누락 (locker, member)"
}
```

**Response (404 Not Found):**
```json
{
  "status": "error",
  "message": "회원을 찾을 수 없습니다: A001"
}
```

---

### 3. 락카 해제 (내부용)

락카키 반납 시 내부적으로 호출

**Endpoint:** `POST /api/locker/release`

**Request Body:**
```json
{
  "locker": 105
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "locker": 105
}
```

**Response (404 Not Found):**
```json
{
  "status": "error",
  "message": "락카 105번이 배정되어 있지 않습니다"
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
    {"locker": 106, "member_id": "A002", "name": "김철수"},
    {"locker": 107, "member_id": "A003", "name": "박영희"}
  ]
}
```

---

### 5. 회원 정보 조회

**Endpoint:** `GET /api/member/{member_id}`

**Parameters:**
| 이름 | 위치 | 필수 | 타입 | 설명 |
|------|------|------|------|------|
| member_id | path | O | string | 회원 ID |

**Response (200 OK):**
```json
{
  "status": "ok",
  "member_id": "A001",
  "name": "홍길동",
  "remaining_count": 10,
  "total_charged": 15,
  "total_used": 5,
  "synced_at": "2024-12-01T09:00:00",
  "updated_at": "2024-12-01T10:00:00"
}
```

**Response (404 Not Found):**
```json
{
  "status": "error",
  "message": "회원을 찾을 수 없습니다: A001"
}
```

---

### 6. 헬스 체크

**Endpoint:** `GET /api/health`

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "locker-api",
  "timestamp": "2024-12-01T10:00:00"
}
```

---

## 운동복/수건 대여기 API

운동복/수건 대여기 라즈베리파이에서 실행되는 Flask API 서버
(ESP32 기기 관리용, 관리자 웹 UI용)

**Base URL:** `http://{운동복대여기IP}:5000`

---

### 1. 대여 처리

**Endpoint:** `POST /api/rental/process`

**Request Body:**
```json
{
  "locker_number": 105,
  "items": [
    {"product_id": "P-UPPER-105", "quantity": 1},
    {"product_id": "P-LOWER-105", "quantity": 1},
    {"product_id": "P-TOWEL", "quantity": 2}
  ]
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "member_id": "A001",
  "total_items": 3,
  "count_after": 7,
  "rentals": [
    {"product_id": "P-UPPER-105", "device_id": "FBOX-UPPER-105", "status": "dispensed"},
    {"product_id": "P-LOWER-105", "device_id": "FBOX-LOWER-105", "status": "dispensed"},
    {"product_id": "P-TOWEL", "device_id": "FBOX-TOWEL-01", "status": "dispensed"}
  ]
}
```

**참고**: 횟수 기반 - 1개 대여 = 1회 차감 (상의 1 + 하의 1 + 수건 1 = 3회 차감)

---

### 2. 상품 목록 조회

**Endpoint:** `GET /api/products`

**Query Parameters:**
| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| gym_id | X | string | 헬스장 ID (기본: GYM001) |
| category | X | string | 카테고리 필터 (upper, lower, towel) |

**Response (200 OK):**
```json
{
  "status": "ok",
  "products": [
    {
      "product_id": "P-UPPER-105",
      "category": "upper",
      "size": "105",
      "name": "운동복 상의 105",
      "device_id": "FBOX-UPPER-105",
      "stock": 14,
      "enabled": true
    },
    ...
  ]
}
```

---

### 3. 기기 상태 조회

**Endpoint:** `GET /api/devices`

**Response (200 OK):**
```json
{
  "status": "ok",
  "devices": [
    {
      "device_id": "FBOX-UPPER-105",
      "size": "105",
      "stock": 14,
      "door_state": "closed",
      "floor_state": "reached",
      "locked": false,
      "last_heartbeat": "2024-12-01T10:09:00"
    },
    ...
  ]
}
```

---

### 4. 기기 명령 전송

**Endpoint:** `POST /api/devices/{device_id}/command`

**Parameters:**
| 이름 | 위치 | 필수 | 타입 | 설명 |
|------|------|------|------|------|
| device_id | path | O | string | 기기 ID |

**Request Body:**
```json
{
  "command": "DISPENSE"
}
```

또는:
```json
{
  "command": "SET_STOCK",
  "stock": 20
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "device_id": "FBOX-UPPER-105",
  "command": "DISPENSE",
  "sent_at": "2024-12-01T10:10:00"
}
```

---

## 에러 코드

| HTTP 상태 | status | 설명 |
|-----------|--------|------|
| 200 | ok | 성공 |
| 400 | error | 잘못된 요청 (파라미터 누락/오류) |
| 404 | error | 리소스 없음 (회원, 락카, 상품 등) |
| 500 | error | 서버 내부 오류 |

---

## 인증 (향후)

현재 개발 단계에서는 인증 없이 운영합니다.

**향후 추가 예정:**
- API Key 인증
- JWT 토큰
- IP 화이트리스트

---

## 사용 시나리오

### 시나리오 1: 운동복 대여

```sequence
사용자 -> 운동복대여기: NFC 태그 (락카 105번)
운동복대여기 -> 락카키대여기: GET /api/member/by-locker/105
락카키대여기 --> 운동복대여기: {member: A001, remaining_count: 10}
운동복대여기 -> 운동복대여기: 상품 선택 화면 표시
사용자 -> 운동복대여기: 상품 선택 (상의+하의+수건 = 3회)
운동복대여기 -> 운동복대여기: 횟수 차감 (10→7) + 로그 기록
운동복대여기 -> ESP32: MQTT DISPENSE 명령
ESP32 --> 운동복대여기: dispense_complete 이벤트
운동복대여기 -> 운동복대여기: 재고 업데이트
```

### 시나리오 2: 관리자 재고 설정

```sequence
관리자 -> 웹UI: 재고 20개로 설정
웹UI -> 운동복대여기: POST /api/devices/FBOX-UPPER-105/command
Note: {command: SET_STOCK, stock: 20}
운동복대여기 -> ESP32: MQTT SET_STOCK 명령
ESP32 --> 운동복대여기: stock_updated 이벤트
운동복대여기 -> 웹UI: 성공 응답
```

---

## Python 클라이언트 예시

### 운동복 대여기에서 락카키 대여기 API 호출

```python
import requests

LOCKER_API_BASE = "http://192.168.1.10:5000"

def get_member_by_locker(locker_number: int) -> dict:
    """락카 번호로 회원 정보 조회"""
    url = f"{LOCKER_API_BASE}/api/member/by-locker/{locker_number}"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if response.status_code == 200 and data.get('status') == 'ok':
            return {
                'found': True,
                'member_id': data['member_id'],
                'name': data['name'],
                'remaining_count': data['remaining_count']
            }
        else:
            return {
                'found': False,
                'error': data.get('message', '알 수 없는 오류')
            }
    except requests.exceptions.RequestException as e:
        return {
            'found': False,
            'error': f'네트워크 오류: {e}'
        }


# 사용 예시
result = get_member_by_locker(105)

if result['found']:
    print(f"회원: {result['name']} (잔여 횟수: {result['remaining_count']}회)")
    # 대여 처리 진행...
else:
    print(f"오류: {result['error']}")
```

---

## 버전 이력

- **v1.0.0** (2024-12-01): 초기 버전 (Push 방식)
- **v2.0.0** (2024-12-01): Pull 방식으로 변경

