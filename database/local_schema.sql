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

-- 상품 가격표 (헬스장별 커스터마이징)
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    gym_id TEXT NOT NULL DEFAULT 'GYM001',
    category TEXT NOT NULL,          -- 'upper', 'lower', 'towel'
    size TEXT,                       -- '95', '100', '105', '110', '115', 'XL', 'FREE' 등
    name TEXT NOT NULL,              -- 표시명 ("운동복 상의 105")
    device_id TEXT NOT NULL,         -- 연결된 F-BOX 기기 ID
    stock INT DEFAULT 0,             -- 현재 재고 (device_cache와 동기화)
    enabled BOOLEAN DEFAULT 1,       -- 활성화 여부
    display_order INT DEFAULT 0,     -- 화면 표시 순서
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gym_id, device_id)
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

-- F-BOX 기기 상태 캐시
CREATE TABLE IF NOT EXISTS device_cache (
    device_id TEXT PRIMARY KEY,
    size TEXT,                       -- ESP32의 size (예: "105")
    stock INT DEFAULT 0,
    door_state TEXT,                 -- 'open', 'closed'
    floor_state TEXT,                -- 'reached', 'moving'
    locked BOOLEAN DEFAULT 0,        -- 점검 모드 여부
    last_heartbeat TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    device_id TEXT NOT NULL,
    quantity INT DEFAULT 1,          -- 대여 수량 (= 차감 횟수)
    count_before INT NOT NULL,       -- 대여 전 남은 횟수
    count_after INT NOT NULL,        -- 대여 후 남은 횟수
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
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
-- 7. MQTT 이벤트 로그
-- =============================

-- MQTT 이벤트 로그 (디버깅/모니터링)
CREATE TABLE IF NOT EXISTS mqtt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,                    -- JSON 형식
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================
-- 8. 인덱스
-- =============================

CREATE INDEX IF NOT EXISTS idx_usage_logs_member ON usage_logs(member_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_products_gym ON products(gym_id, enabled);
CREATE INDEX IF NOT EXISTS idx_products_device ON products(device_id);
CREATE INDEX IF NOT EXISTS idx_rental_logs_member ON rental_logs(member_id);
CREATE INDEX IF NOT EXISTS idx_rental_logs_created ON rental_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_rental_logs_sync ON rental_logs(synced_to_sheets);
CREATE INDEX IF NOT EXISTS idx_locker_mapping_member ON locker_mapping(member_id);
CREATE INDEX IF NOT EXISTS idx_mqtt_events_device ON mqtt_events(device_id);
CREATE INDEX IF NOT EXISTS idx_mqtt_events_created ON mqtt_events(created_at);

-- =============================
-- 9. 초기 데이터
-- =============================

-- 예시 상품 데이터 (운동복 상의) - 횟수 기반 (1개 = 1회)
INSERT OR IGNORE INTO products (product_id, category, size, name, device_id, enabled, display_order) VALUES
('P-UPPER-095', 'upper', '95',  '운동복 상의 95',  'FBOX-UPPER-095', 1, 1),
('P-UPPER-100', 'upper', '100', '운동복 상의 100', 'FBOX-UPPER-100', 1, 2),
('P-UPPER-105', 'upper', '105', '운동복 상의 105', 'FBOX-UPPER-105', 1, 3),
('P-UPPER-110', 'upper', '110', '운동복 상의 110', 'FBOX-UPPER-110', 1, 4),
('P-UPPER-115', 'upper', '115', '운동복 상의 115', 'FBOX-UPPER-115', 1, 5);

-- 예시 상품 데이터 (운동복 하의) - 횟수 기반 (1개 = 1회)
INSERT OR IGNORE INTO products (product_id, category, size, name, device_id, enabled, display_order) VALUES
('P-LOWER-095', 'lower', '95',  '운동복 하의 95',  'FBOX-LOWER-095', 1, 11),
('P-LOWER-100', 'lower', '100', '운동복 하의 100', 'FBOX-LOWER-100', 1, 12),
('P-LOWER-105', 'lower', '105', '운동복 하의 105', 'FBOX-LOWER-105', 1, 13),
('P-LOWER-110', 'lower', '110', '운동복 하의 110', 'FBOX-LOWER-110', 1, 14),
('P-LOWER-115', 'lower', '115', '운동복 하의 115', 'FBOX-LOWER-115', 1, 15);

-- 예시 상품 데이터 (수건) - 횟수 기반 (1개 = 1회)
INSERT OR IGNORE INTO products (product_id, category, size, name, device_id, enabled, display_order) VALUES
('P-TOWEL', 'towel', '', '수건', 'FBOX-TOWEL-01', 1, 21);

-- 예시 프로모션 데이터 (10회 이상 충전 시 1회 보너스)
INSERT OR IGNORE INTO promotions (promo_id, name, promo_type, condition_count, reward_count, active) VALUES
('PROMO001', '충전 보너스', 'charge_bonus', 10, 1, 1);

-- 예시 회원 데이터 (테스트용)
INSERT OR IGNORE INTO members (member_id, name, remaining_count, total_charged, total_used) VALUES
('TEST001', '테스트회원', 10, 10, 0);

