# MQTT 동기화 문제 분석 및 해결 기록

## 📋 목차
1. [발생한 문제들](#발생한-문제들)
2. [시도한 해결 방법들](#시도한-해결-방법들)
3. [최종 해결된 구성](#최종-해결된-구성)
4. [잠재적 문제 및 개선 필요 사항](#잠재적-문제-및-개선-필요-사항)

---

## 발생한 문제들

### 문제 1: MQTT 연결이 반복적으로 끊어짐 (RC=7)

**증상:**
```
[MQTT] ⚠️ 예기치 않은 연결 해제: RC=7, 자동 재연결 시도 중...
```
- Flask 로그에 위 메시지가 반복적으로 출력
- 디바이스가 온라인/오프라인을 반복

**원인 분석:**
1. **Client ID 충돌**: Mosquitto 로그에 `Client fbox-server already connected, closing old connection.` 메시지 확인
2. **재연결 간격 너무 짧음**: paho-mqtt 기본값 `min_delay=1초`로 인해 이전 연결이 정리되기 전에 새 연결 시도
3. **Flask-SocketIO async_mode 충돌**: `eventlet` 모드가 paho-mqtt의 내부 스레딩과 충돌

**해결:**
```python
# mqtt_service.py
self.client = mqtt.Client(client_id=f"fbox-server-{os.getpid()}")
self.client.reconnect_delay_set(min_delay=5, max_delay=120)

# app/__init__.py
socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
```

---

### 문제 2: Heartbeat 핸들러 미등록

**증상:**
```
[MQTT] ← FBOX-004B1238C424: heartbeat
[MQTT] 미등록 이벤트: heartbeat
```
- ESP32에서 heartbeat를 보내지만 Flask에서 처리 안 됨
- 디바이스가 계속 오프라인으로 표시

**원인 분석:**
- `register_default_handlers()`가 2번 호출됨
  1. MQTT 초기화 시 (line 66)
  2. Sheets 초기화 후 (line 116)
- 두 번째 호출 시 오류 발생하여 핸들러 등록 불완전

**해결:**
```python
# app/__init__.py - 핸들러 등록을 한 번만 수행
# MQTT 초기화 시에는 핸들러 등록 안 함
# Sheets 초기화 후에만 핸들러 등록 (Sheets 유무 관계없이)
```

---

### 문제 3: API에서 디바이스 상태가 오프라인으로 표시

**증상:**
- DB의 `device_cache` 테이블: `online=True` (heartbeat 정상)
- API `/api/products` 응답: `"online": false`
- 키오스크 화면에서 상품 선택 불가

**원인 분석:**
- `local_cache.get_device()`가 **메모리 캐시**(`_device_cache`)에서 조회
- MQTT 핸들러가 DB는 업데이트하지만 메모리 캐시는 별도 인스턴스일 수 있음
- Flask 요청마다 새 LocalCache 인스턴스 생성 가능성

**해결:**
```python
# local_cache.py
def get_device(self, device_uuid: str) -> Optional[Dict]:
    """기기 상태 조회 (DB에서 직접 조회)"""
    cursor = self.conn.cursor()
    cursor.execute('SELECT * FROM device_cache WHERE device_uuid = ?', (device_uuid,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None
```

---

### 문제 4: 대여 후 재고가 화면에 즉시 반영 안 됨

**증상:**
- 대여 성공 후 complete 페이지 → rental 페이지 복귀
- 상품 재고가 이전 값 그대로 표시

**원인 분석:**
- `rental_service.py`의 `on_dispense_complete` 핸들러가 `mqtt_service.py`의 핸들러를 **덮어씀**
- `rental_service`의 핸들러는 `local_cache.update_product_stock()` 호출 안 함

**해결:**
```python
# rental_service.py
def on_dispense_complete(device_uuid: str, payload: dict):
    stock = payload.get('stock', 0)
    
    # 로컬 DB 재고 즉시 업데이트 추가
    if self.local_cache:
        product = self.local_cache.get_product_by_device_uuid(device_uuid)
        if product:
            self.local_cache.update_product_stock(product['product_id'], stock)
        self.local_cache.update_device_status(device_uuid, stock=stock)
    
    # 기존 로직...
```

---

## 시도한 해결 방법들

### ❌ 실패한 방법

| 방법 | 시도 이유 | 실패 원인 |
|------|----------|----------|
| `reconnect_delay_set(min_delay=1)` | 빠른 재연결 | 브로커가 이전 연결 정리하기 전에 새 연결 시도 |
| `async_mode='eventlet'` | Flask-SocketIO 기본값 | paho-mqtt의 `loop_start()` 스레딩과 충돌 |
| 메모리 캐시 사용 | 성능 향상 | 멀티 인스턴스 환경에서 동기화 안 됨 |

### ✅ 성공한 방법

| 방법 | 효과 |
|------|------|
| `client_id`에 PID 추가 | Client ID 충돌 방지 |
| `reconnect_delay_set(min_delay=5)` | 안정적인 재연결 |
| `async_mode='threading'` | paho-mqtt와 호환 |
| DB 직접 조회 | 항상 최신 상태 반환 |
| 핸들러에서 재고 업데이트 | 즉시 반영 |

---

## 최종 해결된 구성

### 현재 아키텍처

```
┌─────────────┐     MQTT      ┌─────────────┐
│   ESP32     │ ───────────── │  Mosquitto  │
│  (기기 2대)  │   heartbeat   │   (브로커)   │
└─────────────┘   dispense    └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │ Flask App   │
                              │ (paho-mqtt) │
                              │             │
                              │ threading   │
                              │ mode        │
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │   SQLite    │
                              │ (device_    │
                              │  cache)     │
                              └─────────────┘
```

### 주요 설정값

```python
# mqtt_service.py
client_id = f"fbox-server-{os.getpid()}"
reconnect_delay = (5, 120)  # min, max seconds

# app/__init__.py
socketio_async_mode = 'threading'

# local_cache.py
get_device() → DB 직접 조회

# 타임아웃 기준
heartbeat_timeout = 120초 (2분)
dispense_timeout = 10초
```

---

## 잠재적 문제 및 개선 필요 사항

### 🔴 높은 우선순위

#### 1. 재부팅 시 데이터 덮어쓰기
**현상:** 
- 대여로 잔여횟수/재고 차감 → 재부팅 → Google Sheets 값으로 복원

**원인:**
- `download_members()`가 Sheets 데이터로 로컬 DB 덮어씀
- 로컬 변경사항이 Sheets에 반영되기 전 재부팅

**해결 방향:**
```python
# 옵션 1: 양방향 동기화
def sync_members():
    local = get_local_members()
    sheets = get_sheets_members()
    
    for member in members:
        if local.updated_at > sheets.updated_at:
            upload_to_sheets(member)
        else:
            download_to_local(member)

# 옵션 2: 재고는 ESP32 기준
# boot_complete 이벤트의 stock 값을 신뢰
```

#### 2. RentalService 별도 MQTT 인스턴스
**현상:**
- `rental_service.py`가 자체 `MQTTService` 생성 (line 100-107)
- 핸들러 충돌 발생

**권장 수정:**
```python
# rental_service.py
class RentalService:
    def __init__(self, local_cache, mqtt_service=None):
        self._mqtt_service = mqtt_service  # 외부에서 주입
```

### 🟡 중간 우선순위

#### 3. SQLite 동시 접근
**현상:**
- MQTT 스레드, Flask 요청 스레드가 동시에 DB 접근
- `database is locked` 에러 가능성

**해결 방향:**
```python
# 연결 풀 또는 WAL 모드 사용
conn = sqlite3.connect('fbox_local.db', check_same_thread=False)
conn.execute('PRAGMA journal_mode=WAL')
```

#### 4. 메모리 캐시 무용지물
**현상:**
- `_device_cache`, `_device_registry` 메모리 캐시 사용 안 함
- DB 직접 조회로 변경하면서 메모리 캐시가 무의미해짐

**해결 방향:**
- 메모리 캐시 완전 제거하거나
- 단일 인스턴스 보장 후 메모리 캐시 활용

### 🟢 낮은 우선순위

#### 5. Heartbeat 주기 최적화
**현재:** 60초
**문제:** 네트워크 불안정 시 최대 2분간 오프라인 미감지

**권장:**
- heartbeat 주기 30초로 단축
- 타임아웃 90초로 조정

#### 6. MQTT QoS 레벨
**현재:** QoS 0 (최선 전달)
**문제:** 메시지 손실 가능

**권장:**
- 중요 이벤트 (dispense_complete, dispense_failed): QoS 1
- heartbeat: QoS 0 유지

---

## 모니터링 체크리스트

### 일일 확인 사항

```bash
# 1. MQTT 연결 상태
cat /tmp/flask.log | grep -E "(disconnect|reconnect)" | tail -20

# 2. 디바이스 온라인 상태
sqlite3 /home/pi/gym-rental-system/instance/fbox_local.db \
  "SELECT device_uuid, 
          (julianday('now') - julianday(last_heartbeat)) * 86400 as seconds_ago 
   FROM device_cache"

# 3. 이벤트 로그
sqlite3 /home/pi/gym-rental-system/instance/fbox_local.db \
  "SELECT * FROM event_logs ORDER BY created_at DESC LIMIT 10"
```

### 문제 발생 시 확인 순서

1. ESP32 시리얼 모니터 - heartbeat 전송 확인
2. Mosquitto 로그 - 메시지 수신 확인
3. Flask 로그 - 핸들러 호출 확인
4. SQLite device_cache - DB 업데이트 확인
5. API 응답 - 최종 상태 확인

---

## 변경 이력

| 날짜 | 변경 내용 | 파일 |
|------|----------|------|
| 2025-12-03 | async_mode를 threading으로 변경 | `app/__init__.py` |
| 2025-12-03 | client_id에 PID 추가, reconnect_delay 5초 | `mqtt_service.py` |
| 2025-12-03 | 핸들러 중복 등록 제거 | `app/__init__.py` |
| 2025-12-03 | get_device() DB 직접 조회 | `local_cache.py` |
| 2025-12-03 | dispense_complete에서 재고 업데이트 | `rental_service.py` |

