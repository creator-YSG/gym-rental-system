#!/usr/bin/env python3
"""
마이그레이션 스크립트: 횟수 기반 → 금액권/구독권 기반

기존 데이터를 새 스키마로 마이그레이션:
1. 기존 remaining_count를 금액권으로 변환 (1회 = 1000원)
2. products 테이블에 price 컬럼 추가
3. 새 테이블 생성 (voucher_products, member_vouchers 등)
4. 기존 rental_logs 호환성 유지

사용법:
    python database/migrate_to_voucher_system.py
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def get_db_path():
    """데이터베이스 경로 반환"""
    project_root = Path(__file__).parent.parent
    return project_root / 'instance' / 'fbox_local.db'


def backup_database(db_path: Path):
    """데이터베이스 백업"""
    backup_path = db_path.with_suffix(f'.db.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    shutil.copy(db_path, backup_path)
    print(f"✅ 데이터베이스 백업 완료: {backup_path}")
    return backup_path


def check_already_migrated(conn):
    """이미 마이그레이션되었는지 확인"""
    cursor = conn.cursor()
    
    # voucher_products 테이블이 있으면 이미 마이그레이션됨
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='voucher_products'")
    return cursor.fetchone() is not None


def create_new_tables(conn):
    """새 테이블 생성"""
    cursor = conn.cursor()
    
    # 금액권 상품 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voucher_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price INT NOT NULL,
            charge_amount INT NOT NULL,
            validity_days INT DEFAULT 365,
            bonus_product_id TEXT,
            is_bonus BOOLEAN DEFAULT 0,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bonus_product_id) REFERENCES voucher_products(product_id)
        )
    ''')
    
    # 회원 금액권 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_vouchers (
            voucher_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT NOT NULL,
            voucher_product_id TEXT NOT NULL,
            original_amount INT NOT NULL,
            remaining_amount INT NOT NULL,
            parent_voucher_id INT,
            valid_from TIMESTAMP,
            valid_until TIMESTAMP,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_to_sheets BOOLEAN DEFAULT 0,
            FOREIGN KEY (member_id) REFERENCES members(member_id),
            FOREIGN KEY (voucher_product_id) REFERENCES voucher_products(product_id),
            FOREIGN KEY (parent_voucher_id) REFERENCES member_vouchers(voucher_id)
        )
    ''')
    
    # 금액권 거래 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voucher_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INT NOT NULL,
            member_id TEXT NOT NULL,
            amount INT NOT NULL,
            balance_before INT NOT NULL,
            balance_after INT NOT NULL,
            transaction_type TEXT NOT NULL,
            rental_log_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_to_sheets BOOLEAN DEFAULT 0,
            FOREIGN KEY (voucher_id) REFERENCES member_vouchers(voucher_id),
            FOREIGN KEY (member_id) REFERENCES members(member_id),
            FOREIGN KEY (rental_log_id) REFERENCES rental_logs(id)
        )
    ''')
    
    # 구독 상품 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price INT NOT NULL,
            validity_days INT NOT NULL,
            daily_limits TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 회원 구독권 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_subscriptions (
            subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT NOT NULL,
            subscription_product_id TEXT NOT NULL,
            valid_from TIMESTAMP NOT NULL,
            valid_until TIMESTAMP NOT NULL,
            daily_limits TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_to_sheets BOOLEAN DEFAULT 0,
            FOREIGN KEY (member_id) REFERENCES members(member_id),
            FOREIGN KEY (subscription_product_id) REFERENCES subscription_products(product_id)
        )
    ''')
    
    # 구독권 일일 사용량 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INT NOT NULL,
            usage_date DATE NOT NULL,
            category TEXT NOT NULL,
            used_count INT DEFAULT 0,
            UNIQUE(subscription_id, usage_date, category),
            FOREIGN KEY (subscription_id) REFERENCES member_subscriptions(subscription_id)
        )
    ''')
    
    conn.commit()
    print("✅ 새 테이블 생성 완료")


def add_price_column_to_products(conn):
    """products 테이블에 price 컬럼 추가"""
    cursor = conn.cursor()
    
    # 컬럼 존재 여부 확인
    cursor.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'price' not in columns:
        cursor.execute('ALTER TABLE products ADD COLUMN price INT DEFAULT 1000')
        conn.commit()
        print("✅ products 테이블에 price 컬럼 추가 완료")
    else:
        print("ℹ️ products 테이블에 이미 price 컬럼이 있습니다")


def update_rental_logs_schema(conn):
    """rental_logs 테이블 스키마 업데이트 (호환성 유지)"""
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(rental_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_columns = [
        ('payment_type', 'TEXT DEFAULT "voucher"'),
        ('subscription_id', 'INT'),
        ('amount', 'INT DEFAULT 0'),
    ]
    
    for col_name, col_def in new_columns:
        if col_name not in columns:
            cursor.execute(f'ALTER TABLE rental_logs ADD COLUMN {col_name} {col_def}')
            print(f"✅ rental_logs 테이블에 {col_name} 컬럼 추가 완료")
    
    conn.commit()


def insert_default_voucher_products(conn):
    """기본 금액권 상품 삽입"""
    cursor = conn.cursor()
    
    default_products = [
        ('VCH-MIGRATION', '마이그레이션 금액권', 0, 0, 3650, None, 0),
        ('VCH-10K', '1만원 금액권', 10000, 10000, 365, None, 0),
        ('VCH-50K', '5만원 금액권', 50000, 50000, 365, None, 0),
        ('VCH-100K', '10만원 금액권', 100000, 100000, 365, 'VCH-BONUS-10K', 0),
        ('VCH-BONUS-5K', '5천원 보너스', 0, 5000, 30, None, 1),
        ('VCH-BONUS-10K', '1만원 보너스', 0, 10000, 30, None, 1),
    ]
    
    for product in default_products:
        cursor.execute('''
            INSERT OR IGNORE INTO voucher_products 
            (product_id, name, price, charge_amount, validity_days, bonus_product_id, is_bonus)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', product)
    
    conn.commit()
    print("✅ 기본 금액권 상품 삽입 완료")


def insert_default_subscription_products(conn):
    """기본 구독 상품 삽입"""
    cursor = conn.cursor()
    
    import json
    default_products = [
        ('SUB-1M-BASIC', '1개월 기본 이용권', 50000, 30, json.dumps({"top":1,"pants":1,"towel":1})),
        ('SUB-3M-BASIC', '3개월 기본 이용권', 120000, 90, json.dumps({"top":1,"pants":1,"towel":1})),
        ('SUB-3M-PREMIUM', '3개월 프리미엄 이용권', 180000, 90, json.dumps({"top":2,"pants":2,"towel":3})),
    ]
    
    for product in default_products:
        cursor.execute('''
            INSERT OR IGNORE INTO subscription_products 
            (product_id, name, price, validity_days, daily_limits)
            VALUES (?, ?, ?, ?, ?)
        ''', product)
    
    conn.commit()
    print("✅ 기본 구독 상품 삽입 완료")


def migrate_remaining_count_to_vouchers(conn):
    """
    기존 remaining_count를 금액권으로 변환
    1회 = 1000원으로 계산
    """
    cursor = conn.cursor()
    
    # remaining_count 컬럼 존재 확인
    cursor.execute("PRAGMA table_info(members)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'remaining_count' not in columns:
        print("ℹ️ remaining_count 컬럼이 없습니다 (이미 마이그레이션됨)")
        return
    
    # 잔여 횟수가 있는 회원 조회
    cursor.execute('SELECT member_id, remaining_count FROM members WHERE remaining_count > 0')
    members_with_count = cursor.fetchall()
    
    if not members_with_count:
        print("ℹ️ 마이그레이션할 잔여 횟수가 있는 회원이 없습니다")
        return
    
    now = datetime.now().isoformat()
    valid_until = (datetime.now() + timedelta(days=3650)).isoformat()  # 10년
    
    migrated_count = 0
    for member_id, remaining_count in members_with_count:
        amount = remaining_count * 1000  # 1회 = 1000원
        
        cursor.execute('''
            INSERT INTO member_vouchers 
            (member_id, voucher_product_id, original_amount, remaining_amount,
             valid_from, valid_until, status, created_at, updated_at)
            VALUES (?, 'VCH-MIGRATION', ?, ?, ?, ?, 'active', ?, ?)
        ''', (member_id, amount, amount, now, valid_until, now, now))
        
        migrated_count += 1
    
    conn.commit()
    print(f"✅ {migrated_count}명의 잔여 횟수를 금액권으로 변환 완료")


def create_new_indexes(conn):
    """새 인덱스 생성"""
    cursor = conn.cursor()
    
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_member_vouchers_member ON member_vouchers(member_id)',
        'CREATE INDEX IF NOT EXISTS idx_member_vouchers_status ON member_vouchers(status)',
        'CREATE INDEX IF NOT EXISTS idx_member_vouchers_parent ON member_vouchers(parent_voucher_id)',
        'CREATE INDEX IF NOT EXISTS idx_voucher_transactions_voucher ON voucher_transactions(voucher_id)',
        'CREATE INDEX IF NOT EXISTS idx_voucher_transactions_rental ON voucher_transactions(rental_log_id)',
        'CREATE INDEX IF NOT EXISTS idx_voucher_transactions_member ON voucher_transactions(member_id)',
        'CREATE INDEX IF NOT EXISTS idx_member_subscriptions_member ON member_subscriptions(member_id)',
        'CREATE INDEX IF NOT EXISTS idx_member_subscriptions_status ON member_subscriptions(status)',
        'CREATE INDEX IF NOT EXISTS idx_subscription_usage_subscription ON subscription_usage(subscription_id)',
        'CREATE INDEX IF NOT EXISTS idx_subscription_usage_date ON subscription_usage(usage_date)',
        'CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)',
        'CREATE INDEX IF NOT EXISTS idx_rental_logs_payment_type ON rental_logs(payment_type)',
    ]
    
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except sqlite3.OperationalError:
            pass  # 이미 존재하면 무시
    
    conn.commit()
    print("✅ 인덱스 생성 완료")


def verify_migration(conn):
    """마이그레이션 검증"""
    cursor = conn.cursor()
    
    print("\n=== 마이그레이션 검증 ===")
    
    # 테이블 확인
    tables = ['voucher_products', 'member_vouchers', 'voucher_transactions',
              'subscription_products', 'member_subscriptions', 'subscription_usage']
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count}개")
    
    # products 테이블 price 컬럼 확인
    cursor.execute("SELECT COUNT(*) FROM products WHERE price IS NOT NULL")
    products_with_price = cursor.fetchone()[0]
    print(f"  products (with price): {products_with_price}개")
    
    # 마이그레이션된 금액권 확인
    cursor.execute("SELECT COUNT(*) FROM member_vouchers WHERE voucher_product_id = 'VCH-MIGRATION'")
    migrated_vouchers = cursor.fetchone()[0]
    print(f"  마이그레이션된 금액권: {migrated_vouchers}개")
    
    print("\n✅ 마이그레이션 검증 완료")


def main():
    print("=" * 50)
    print("금액권/구독권 시스템 마이그레이션")
    print("=" * 50)
    
    db_path = get_db_path()
    
    if not db_path.exists():
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        print("새 스키마로 데이터베이스를 초기화하려면 local_schema.sql을 실행하세요.")
        return
    
    # 백업
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # 이미 마이그레이션되었는지 확인
        if check_already_migrated(conn):
            print("ℹ️ 이미 마이그레이션된 데이터베이스입니다")
            verify_migration(conn)
            conn.close()
            return
        
        print("\n1. 새 테이블 생성...")
        create_new_tables(conn)
        
        print("\n2. products 테이블 업데이트...")
        add_price_column_to_products(conn)
        
        print("\n3. rental_logs 테이블 업데이트...")
        update_rental_logs_schema(conn)
        
        print("\n4. 기본 금액권 상품 삽입...")
        insert_default_voucher_products(conn)
        
        print("\n5. 기본 구독 상품 삽입...")
        insert_default_subscription_products(conn)
        
        print("\n6. 잔여 횟수 → 금액권 변환...")
        migrate_remaining_count_to_vouchers(conn)
        
        print("\n7. 인덱스 생성...")
        create_new_indexes(conn)
        
        verify_migration(conn)
        
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ 마이그레이션 완료!")
        print(f"백업 파일: {backup_path}")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 마이그레이션 오류: {e}")
        print(f"백업에서 복원하세요: {backup_path}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

