-- 운동복/수건 대여 시스템 데이터베이스 스키마
-- SQLite3

-- 1. 회원 테이블
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT UNIQUE NOT NULL,          -- 회원 바코드 번호
    name TEXT NOT NULL,                      -- 회원 이름
    phone TEXT,                              -- 전화번호
    status TEXT DEFAULT 'active',            -- active, inactive, expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 물품 재고 테이블
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,                 -- 'uniform' 또는 'towel'
    item_size TEXT,                          -- 'S', 'M', 'L', 'XL' (운동복만 해당)
    total_quantity INTEGER DEFAULT 0,        -- 전체 수량
    available_quantity INTEGER DEFAULT 0,    -- 사용 가능 수량
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_type, item_size)
);

-- 3. 대여 기록 테이블
CREATE TABLE IF NOT EXISTS rentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL,                 -- 회원 ID
    item_type TEXT NOT NULL,                 -- 'uniform' 또는 'towel'
    item_size TEXT,                          -- 사이즈 (운동복만)
    rental_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    return_date TIMESTAMP,                   -- 반납일 (NULL이면 미반납)
    status TEXT DEFAULT 'rented',            -- 'rented', 'returned'
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

-- 4. 시스템 설정 테이블
CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_members_member_id ON members(member_id);
CREATE INDEX IF NOT EXISTS idx_rentals_member_id ON rentals(member_id);
CREATE INDEX IF NOT EXISTS idx_rentals_status ON rentals(status);
CREATE INDEX IF NOT EXISTS idx_inventory_type_size ON inventory(item_type, item_size);

-- 기본 재고 데이터 삽입
INSERT OR IGNORE INTO inventory (item_type, item_size, total_quantity, available_quantity) VALUES
    ('uniform', 'S', 20, 20),
    ('uniform', 'M', 30, 30),
    ('uniform', 'L', 30, 30),
    ('uniform', 'XL', 20, 20),
    ('towel', NULL, 100, 100);

-- 기본 시스템 설정
INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
    ('system_name', '운동복/수건 대여 시스템', '시스템 이름'),
    ('max_rental_per_member', '1', '회원당 최대 대여 가능 수량'),
    ('allow_duplicate_rental', 'false', '중복 대여 허용 여부');


