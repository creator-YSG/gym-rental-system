-- =============================
-- F-BOX 금액권/구독권 기반 대여 시스템
-- 로컬 DB 스키마 (SQLite)
-- =============================

-- =============================
-- 1. 회원 관리
-- =============================

-- 회원 정보 (Google Sheets에서 동기화)
CREATE TABLE IF NOT EXISTS members (
    member_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,                       -- 전화번호
    payment_password TEXT,            -- 결제 비밀번호 (6자리 숫자)
    status TEXT DEFAULT 'active',     -- 'active', 'inactive', 'suspended'
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================
-- 2. 금액권 시스템
-- =============================

-- 금액권 상품 정의
CREATE TABLE IF NOT EXISTS voucher_products (
    product_id TEXT PRIMARY KEY,      -- 예: "VCH-100K"
    name TEXT NOT NULL,               -- "10만원 금액권"
    price INT NOT NULL,               -- 결제 금액 (원)
    charge_amount INT NOT NULL,       -- 충전 금액 (원)
    validity_days INT DEFAULT 365,    -- 유효 기간 (일)
    bonus_product_id TEXT,            -- 연결된 보너스 상품 ID (1단계)
    is_bonus BOOLEAN DEFAULT 0,       -- 보너스 상품 여부
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bonus_product_id) REFERENCES voucher_products(product_id)
);

-- 회원 보유 금액권
CREATE TABLE IF NOT EXISTS member_vouchers (
    voucher_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    voucher_product_id TEXT NOT NULL,
    original_amount INT NOT NULL,     -- 최초 충전 금액
    remaining_amount INT NOT NULL,    -- 남은 금액
    parent_voucher_id INT,            -- 보너스용: 연결된 부모 금액권 ID
    valid_from TIMESTAMP,             -- 유효 시작일 (보너스는 NULL로 시작, 활성화 시 설정)
    valid_until TIMESTAMP,            -- 유효 종료일
    status TEXT DEFAULT 'active',     -- 'pending'(보너스대기), 'active', 'exhausted', 'expired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (voucher_product_id) REFERENCES voucher_products(product_id),
    FOREIGN KEY (parent_voucher_id) REFERENCES member_vouchers(voucher_id)
);

-- 금액권 거래 내역 (쪼개기 지원)
CREATE TABLE IF NOT EXISTS voucher_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id INT NOT NULL,          -- 사용된 금액권 ID
    member_id TEXT NOT NULL,
    amount INT NOT NULL,              -- 이 금액권에서 차감된 금액
    balance_before INT NOT NULL,      -- 거래 전 잔액
    balance_after INT NOT NULL,       -- 거래 후 잔액
    transaction_type TEXT NOT NULL,   -- 'rental', 'refund'
    rental_log_id INT,                -- rental_logs.id 참조
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (voucher_id) REFERENCES member_vouchers(voucher_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (rental_log_id) REFERENCES rental_logs(id)
);

-- =============================
-- 3. 구독권 시스템
-- =============================

-- 구독 상품 정의 (일일 횟수 제한권)
CREATE TABLE IF NOT EXISTS subscription_products (
    product_id TEXT PRIMARY KEY,      -- 예: "SUB-3M-BASIC"
    name TEXT NOT NULL,               -- "3개월 기본 이용권"
    price INT NOT NULL,               -- 결제 금액 (원)
    validity_days INT NOT NULL,       -- 유효 기간 (일)
    daily_limits TEXT NOT NULL,       -- JSON: {"top":1,"pants":1,"towel":1}
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 회원 보유 구독권
CREATE TABLE IF NOT EXISTS member_subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    subscription_product_id TEXT NOT NULL,
    valid_from TIMESTAMP NOT NULL,    -- 구매 시 설정 가능
    valid_until TIMESTAMP NOT NULL,
    daily_limits TEXT NOT NULL,       -- JSON 복사본 (구매 시점 기준)
    status TEXT DEFAULT 'active',     -- 'active', 'expired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (subscription_product_id) REFERENCES subscription_products(product_id)
);

-- 구독권 일일 사용량 추적
CREATE TABLE IF NOT EXISTS subscription_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INT NOT NULL,
    usage_date DATE NOT NULL,         -- KST 기준 날짜
    category TEXT NOT NULL,           -- 'top', 'pants', 'towel', 'sweat_towel', 'other'
    used_count INT DEFAULT 0,
    UNIQUE(subscription_id, usage_date, category),
    FOREIGN KEY (subscription_id) REFERENCES member_subscriptions(subscription_id)
);

-- =============================
-- 4. 상품 관리 (대여 상품)
-- =============================

-- 상품 정보 (ESP32 기기 등록 시 자동 생성)
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    gym_id TEXT NOT NULL DEFAULT 'GYM001',
    category TEXT NOT NULL,           -- 'top', 'pants', 'towel', 'sweat_towel', 'other'
    size TEXT,                        -- '95', '100', '105', '110', '115', 'FREE' 등
    name TEXT NOT NULL,               -- 상품명 (ESP32에서 설정, 한글 가능)
    price INT DEFAULT 1000,           -- 대여 가격 (원, 기본 1000원)
    device_uuid TEXT,                 -- 연결된 F-BOX 기기 UUID (MAC 기반)
    stock INT DEFAULT 0,              -- 현재 재고 (device_cache와 동기화)
    enabled BOOLEAN DEFAULT 1,        -- 활성화 여부
    display_order INT DEFAULT 0,      -- 화면 표시 순서
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gym_id, device_uuid),
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid)
);

-- =============================
-- 5. 락카 매핑
-- =============================

-- 락카-회원 매핑 (실시간 업데이트)
CREATE TABLE IF NOT EXISTS locker_mapping (
    locker_number INT PRIMARY KEY,
    member_id TEXT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

-- =============================
-- 6. F-BOX 기기 관리
-- =============================

-- F-BOX 기기 레지스트리 (MAC 기반 고유 ID)
CREATE TABLE IF NOT EXISTS device_registry (
    device_uuid TEXT PRIMARY KEY,     -- MAC 기반 UUID (예: "FBOX-A4CF12345678")
    mac_address TEXT UNIQUE,          -- 원본 MAC 주소 (예: "A4:CF:12:34:56:78")
    device_name TEXT,                 -- 관리자가 설정하는 표시 이름 (예: "상의 105호기")
    size TEXT,                        -- 사이즈 (예: "105")
    category TEXT,                    -- 카테고리: 'top', 'pants', 'towel'
    product_id TEXT,                  -- 연결된 상품 ID
    ip_address TEXT,                  -- 마지막 IP 주소
    firmware_version TEXT,            -- 펌웨어 버전
    first_seen_at TIMESTAMP,          -- 최초 연결 시각
    last_seen_at TIMESTAMP,           -- 마지막 연결 시각
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- F-BOX 기기 상태 캐시 (실시간 상태)
CREATE TABLE IF NOT EXISTS device_cache (
    device_uuid TEXT PRIMARY KEY,     -- MAC 기반 UUID (device_registry 참조)
    size TEXT,                        -- ESP32의 size (예: "105")
    stock INT DEFAULT 0,
    door_state TEXT,                  -- 'open', 'closed'
    floor_state TEXT,                 -- 'reached', 'moving'
    locked BOOLEAN DEFAULT 0,         -- 점검 모드 여부
    wifi_rssi INT,                    -- Wi-Fi 신호 강도
    last_heartbeat TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid)
);

-- =============================
-- 7. 대여 트랜잭션
-- =============================

-- 대여 이력 (금액권/구독권 기반)
CREATE TABLE IF NOT EXISTS rental_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,
    locker_number INT,
    product_id TEXT NOT NULL,
    product_name TEXT,                -- 상품명 (조회 편의)
    device_uuid TEXT NOT NULL,        -- F-BOX 기기 UUID (MAC 기반)
    quantity INT DEFAULT 1,           -- 대여 수량
    payment_type TEXT NOT NULL,       -- 'voucher', 'subscription'
    subscription_id INT,              -- 구독권 사용 시
    amount INT DEFAULT 0,             -- 총 차감 금액 (구독이면 0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid),
    FOREIGN KEY (subscription_id) REFERENCES member_subscriptions(subscription_id)
);

-- =============================
-- 8. MQTT 이벤트 로그 (Raw - 7일 보관)
-- =============================

-- MQTT 이벤트 로그 (디버깅/모니터링용, 7일 후 자동 삭제)
CREATE TABLE IF NOT EXISTS mqtt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,                     -- JSON 형식
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================
-- 9. 비즈니스 이벤트 로그 (Sheets 동기화용)
-- =============================

-- 비즈니스 이벤트 로그 (영구 보관, Sheets 업로드)
CREATE TABLE IF NOT EXISTS event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,         -- rental_success, rental_failed, stock_low, device_offline 등
    severity TEXT DEFAULT 'info',     -- info, warning, error
    device_uuid TEXT,                 -- 관련 기기 UUID
    member_id TEXT,                   -- 관련 회원 ID
    product_id TEXT,                  -- 관련 상품 ID
    details TEXT,                     -- JSON 형식 상세 정보
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_to_sheets BOOLEAN DEFAULT 0,
    FOREIGN KEY (device_uuid) REFERENCES device_registry(device_uuid),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- =============================
-- 10. 인덱스
-- =============================

-- 금액권 관련
CREATE INDEX IF NOT EXISTS idx_member_vouchers_member ON member_vouchers(member_id);
CREATE INDEX IF NOT EXISTS idx_member_vouchers_status ON member_vouchers(status);
CREATE INDEX IF NOT EXISTS idx_member_vouchers_parent ON member_vouchers(parent_voucher_id);
CREATE INDEX IF NOT EXISTS idx_voucher_transactions_voucher ON voucher_transactions(voucher_id);
CREATE INDEX IF NOT EXISTS idx_voucher_transactions_rental ON voucher_transactions(rental_log_id);
CREATE INDEX IF NOT EXISTS idx_voucher_transactions_member ON voucher_transactions(member_id);

-- 구독권 관련
CREATE INDEX IF NOT EXISTS idx_member_subscriptions_member ON member_subscriptions(member_id);
CREATE INDEX IF NOT EXISTS idx_member_subscriptions_status ON member_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscription_usage_subscription ON subscription_usage(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_usage_date ON subscription_usage(usage_date);

-- 상품/기기 관련
CREATE INDEX IF NOT EXISTS idx_products_gym ON products(gym_id, enabled);
CREATE INDEX IF NOT EXISTS idx_products_device_uuid ON products(device_uuid);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_device_registry_mac ON device_registry(mac_address);
CREATE INDEX IF NOT EXISTS idx_device_registry_product ON device_registry(product_id);

-- 대여 로그 관련
CREATE INDEX IF NOT EXISTS idx_rental_logs_member ON rental_logs(member_id);
CREATE INDEX IF NOT EXISTS idx_rental_logs_created ON rental_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_rental_logs_sync ON rental_logs(synced_to_sheets);
CREATE INDEX IF NOT EXISTS idx_rental_logs_device_uuid ON rental_logs(device_uuid);
CREATE INDEX IF NOT EXISTS idx_rental_logs_payment_type ON rental_logs(payment_type);

-- 기타
CREATE INDEX IF NOT EXISTS idx_locker_mapping_member ON locker_mapping(member_id);
CREATE INDEX IF NOT EXISTS idx_mqtt_events_device ON mqtt_events(device_id);
CREATE INDEX IF NOT EXISTS idx_mqtt_events_created ON mqtt_events(created_at);
CREATE INDEX IF NOT EXISTS idx_event_logs_type ON event_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_event_logs_created ON event_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_event_logs_sync ON event_logs(synced_to_sheets);

-- =============================
-- 11. 초기 데이터 (테스트용)
-- =============================

-- 예시 금액권 상품
INSERT OR IGNORE INTO voucher_products (product_id, name, price, charge_amount, validity_days, is_bonus) VALUES
('VCH-10K', '1만원 금액권', 10000, 10000, 365, 0),
('VCH-50K', '5만원 금액권', 50000, 50000, 365, 0),
('VCH-100K', '10만원 금액권', 100000, 100000, 365, 0);

-- 보너스 금액권 상품
INSERT OR IGNORE INTO voucher_products (product_id, name, price, charge_amount, validity_days, is_bonus) VALUES
('VCH-BONUS-5K', '5천원 보너스', 0, 5000, 30, 1),
('VCH-BONUS-10K', '1만원 보너스', 0, 10000, 30, 1);

-- 10만원권에 1만원 보너스 연결
UPDATE voucher_products SET bonus_product_id = 'VCH-BONUS-10K' WHERE product_id = 'VCH-100K';

-- 예시 구독 상품
INSERT OR IGNORE INTO subscription_products (product_id, name, price, validity_days, daily_limits) VALUES
('SUB-1M-BASIC', '1개월 기본 이용권', 50000, 30, '{"top":1,"pants":1,"towel":1}'),
('SUB-3M-BASIC', '3개월 기본 이용권', 120000, 90, '{"top":1,"pants":1,"towel":1}'),
('SUB-3M-PREMIUM', '3개월 프리미엄 이용권', 180000, 90, '{"top":2,"pants":2,"towel":3}');

-- 예시 테스트 회원
INSERT OR IGNORE INTO members (member_id, name, phone, status) VALUES
('TEST001', '테스트회원', '01012345678', 'active');
