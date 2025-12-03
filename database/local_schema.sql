-- =============================
-- F-BOX 횟수 기반 대여 시스템
-- 로컬 DB 스키마 (SQLite)
-- =============================

-- =============================
-- 1. 회원 및 횟수 관리
-- =============================

-- 회원 정보 (Google Sheets에서 동기화)
CREATE TABLE IF NOT EXISTS members (
    member_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    remaining_count INT DEFAULT 0,   -- 남은 횟수
    total_charged INT DEFAULT 0,     -- 누적 충전 횟수
    total_used INT DEFAULT 0,        -- 누적 사용 횟수
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 횟수 변동 이력
CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    amount INT NOT NULL,             -- 양수: 충전, 음수: 차감
    count_before INT NOT NULL,
    count_after INT NOT NULL,
    transaction_type TEXT NOT NULL,  -- 'charge', 'rental', 'refund', 'bonus'
    description TEXT,
    reference_id INT,                -- rental_logs.id 참조
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

-- =============================
-- 2. 상품 및 가격 관리
-- =============================

-- 상품 정보 (ESP32 기기 등록 시 자동 생성)
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    gym_id TEXT NOT NULL DEFAULT 'GYM001',
    category TEXT NOT NULL,          -- 'top', 'pants', 'towel', 'sweat_towel', 'other'
    size TEXT,                       -- '95', '100', '105', '110', '115', 'FREE' 등
    name TEXT NOT NULL,              -- 상품명 (ESP32에서 설정, 한글 가능)
    device_uuid TEXT,                -- 연결된 F-BOX 기기 UUID (MAC 기반)
    stock INT DEFAULT 0,             -- 현재 재고 (device_cache와 동기화)
    enabled BOOLEAN DEFAULT 1,       -- 활성화 여부
    display_order INT DEFAULT 0,     -- 화면 표시 순서
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gym_id, device_uuid),
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid)
);

-- =============================
-- 3. 락카 매핑
-- =============================

-- 락카-회원 매핑 (실시간 업데이트)
CREATE TABLE IF NOT EXISTS locker_mapping (
    locker_number INT PRIMARY KEY,
    member_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

-- =============================
-- 4. F-BOX 기기 관리
-- =============================

-- F-BOX 기기 레지스트리 (MAC 기반 고유 ID)
CREATE TABLE IF NOT EXISTS device_registry (
    device_uuid TEXT PRIMARY KEY,    -- MAC 기반 UUID (예: "FBOX-A4CF12345678")
    mac_address TEXT UNIQUE,         -- 원본 MAC 주소 (예: "A4:CF:12:34:56:78")
    device_name TEXT,                -- 관리자가 설정하는 표시 이름 (예: "상의 105호기")
    size TEXT,                       -- 사이즈 (예: "105")
    category TEXT,                   -- 카테고리: 'upper', 'lower', 'towel'
    product_id TEXT,                 -- 연결된 상품 ID
    ip_address TEXT,                 -- 마지막 IP 주소
    firmware_version TEXT,           -- 펌웨어 버전
    first_seen_at TIMESTAMP,         -- 최초 연결 시각
    last_seen_at TIMESTAMP,          -- 마지막 연결 시각
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- F-BOX 기기 상태 캐시 (실시간 상태)
CREATE TABLE IF NOT EXISTS device_cache (
    device_uuid TEXT PRIMARY KEY,    -- MAC 기반 UUID (device_registry 참조)
    size TEXT,                       -- ESP32의 size (예: "105")
    stock INT DEFAULT 0,
    door_state TEXT,                 -- 'open', 'closed'
    floor_state TEXT,                -- 'reached', 'moving'
    locked BOOLEAN DEFAULT 0,        -- 점검 모드 여부
    wifi_rssi INT,                   -- Wi-Fi 신호 강도
    last_heartbeat TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid)
);

-- =============================
-- 5. 대여 트랜잭션
-- =============================

-- 대여 이력
CREATE TABLE IF NOT EXISTS rental_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    locker_number INT,
    product_id TEXT NOT NULL,
    device_uuid TEXT NOT NULL,       -- F-BOX 기기 UUID (MAC 기반)
    quantity INT DEFAULT 1,          -- 대여 수량 (= 차감 횟수)
    count_before INT NOT NULL,       -- 대여 전 남은 횟수
    count_after INT NOT NULL,        -- 대여 후 남은 횟수
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid)
);

-- =============================
-- 6. 프로모션 (횟수 기반)
-- =============================

-- 프로모션/이벤트
CREATE TABLE IF NOT EXISTS promotions (
    promo_id TEXT PRIMARY KEY,
    gym_id TEXT NOT NULL DEFAULT 'GYM001',
    name TEXT NOT NULL,
    promo_type TEXT NOT NULL,        -- 'charge_bonus' (충전 보너스)
    condition_count INT,             -- 조건 횟수 (예: 10회 이상 충전 시)
    reward_count INT,                -- 보너스 횟수 (예: 1회 추가)
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    active BOOLEAN DEFAULT 1
);

-- 예시: "10회 이상 충전 시 1회 보너스"
INSERT OR IGNORE INTO promotions (promo_id, name, promo_type, condition_count, reward_count, active) VALUES
('PROMO001', '충전 보너스', 'charge_bonus', 10, 1, 1);

-- =============================
-- 7. MQTT 이벤트 로그 (Raw - 7일 보관)
-- =============================

-- MQTT 이벤트 로그 (디버깅/모니터링용, 7일 후 자동 삭제)
CREATE TABLE IF NOT EXISTS mqtt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,                    -- JSON 형식
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================
-- 7-1. 비즈니스 이벤트 로그 (Sheets 동기화용)
-- =============================

-- 비즈니스 이벤트 로그 (영구 보관, Sheets 업로드)
CREATE TABLE IF NOT EXISTS event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,        -- rental_success, rental_failed, stock_low, device_offline 등
    severity TEXT DEFAULT 'info',    -- info, warning, error
    device_uuid TEXT,                -- 관련 기기 UUID
    member_id TEXT,                  -- 관련 회원 ID
    product_id TEXT,                 -- 관련 상품 ID
    details TEXT,                    -- JSON 형식 상세 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- =============================
-- 8. 인덱스
-- =============================

CREATE INDEX IF NOT EXISTS idx_usage_logs_member ON usage_logs(member_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_products_gym ON products(gym_id, enabled);
CREATE INDEX IF NOT EXISTS idx_products_device_uuid ON products(device_uuid);
CREATE INDEX IF NOT EXISTS idx_rental_logs_member ON rental_logs(member_id);
CREATE INDEX IF NOT EXISTS idx_rental_logs_created ON rental_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_rental_logs_sync ON rental_logs(synced_to_sheets);
CREATE INDEX IF NOT EXISTS idx_rental_logs_device_uuid ON rental_logs(device_uuid);
CREATE INDEX IF NOT EXISTS idx_locker_mapping_member ON locker_mapping(member_id);
CREATE INDEX IF NOT EXISTS idx_mqtt_events_device ON mqtt_events(device_id);
CREATE INDEX IF NOT EXISTS idx_mqtt_events_created ON mqtt_events(created_at);
CREATE INDEX IF NOT EXISTS idx_device_registry_mac ON device_registry(mac_address);
CREATE INDEX IF NOT EXISTS idx_device_registry_product ON device_registry(product_id);
CREATE INDEX IF NOT EXISTS idx_event_logs_type ON event_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_event_logs_created ON event_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_event_logs_sync ON event_logs(synced_to_sheets);
CREATE INDEX IF NOT EXISTS idx_event_logs_device ON event_logs(device_uuid);
CREATE INDEX IF NOT EXISTS idx_event_logs_severity ON event_logs(severity);

-- =============================
-- 9. 초기 데이터
-- =============================

-- 상품 데이터는 ESP32 기기 등록 시 자동 생성됨
-- (category + size + deviceName → products 테이블에 자동 INSERT)

-- 예시 프로모션 데이터 (10회 이상 충전 시 1회 보너스)
INSERT OR IGNORE INTO promotions (promo_id, name, promo_type, condition_count, reward_count, active) VALUES
('PROMO001', '충전 보너스', 'charge_bonus', 10, 1, 1);

-- 예시 회원 데이터 (테스트용)
INSERT OR IGNORE INTO members (member_id, name, remaining_count, total_charged, total_used) VALUES
('TEST001', '테스트회원', 10, 10, 0);
