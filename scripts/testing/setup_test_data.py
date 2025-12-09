#!/usr/bin/env python3
"""
테스트 회원 및 이용권 데이터 생성 스크립트

6가지 시나리오를 위한 테스트 회원 생성:
- 회원A: 이용권 없음
- 회원B: 구독권만 (상의3/하의3/수건3)
- 회원C: 금액권만 (50,000원)
- 회원D1: 구독권(상의3/하의3) + 금액권(10,000원)
- 회원D2: 구독권(상의1/하의0) + 금액권 2개(5,000원 + 3,000원)
- 회원D3: 구독권(상의0/하의0 소진) + 금액권(10,000원)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / 'instance' / 'fbox_local.db'

# 한국 시간 기준으로 현재 날짜와 유효기간 계산
KST_NOW = datetime.now()
VALID_FROM = KST_NOW.replace(hour=0, minute=0, second=0, microsecond=0)
VALID_UNTIL_30D = (VALID_FROM + timedelta(days=30)).isoformat()
VALID_UNTIL_90D = (VALID_FROM + timedelta(days=90)).isoformat()
VALID_FROM_ISO = VALID_FROM.isoformat()

# 테스트 회원 데이터
TEST_MEMBERS = [
    {
        'member_id': 'TEST-A',
        'name': '이용권없음',
        'phone': '01011111111',
        'payment_password': '123456',
        'description': '이용권 없는 회원',
    },
    {
        'member_id': 'TEST-B',
        'name': '구독권만',
        'phone': '01022222222',
        'payment_password': '123456',
        'description': '구독권만 있는 회원 (상의3/하의3/수건3)',
    },
    {
        'member_id': 'TEST-C',
        'name': '금액권만',
        'phone': '01033333333',
        'payment_password': '123456',
        'description': '금액권만 있는 회원 (50,000원)',
    },
    {
        'member_id': 'TEST-D1',
        'name': '구독금액둘다',
        'phone': '01044444444',
        'payment_password': '123456',
        'description': '구독권 + 금액권 둘 다 (구독권으로 전부 커버 가능)',
    },
    {
        'member_id': 'TEST-D2',
        'name': '구독일부금액일부',
        'phone': '01055555555',
        'payment_password': '123456',
        'description': '구독권 일부 + 금액권 일부 (핵심 시나리오)',
    },
    {
        'member_id': 'TEST-D3',
        'name': '구독소진금액만',
        'phone': '01066666666',
        'payment_password': '123456',
        'description': '구독권 전부 소진 + 금액권',
    },
]


def get_connection():
    """DB 연결"""
    if not DB_PATH.exists():
        print(f"❌ 데이터베이스 파일이 없습니다: {DB_PATH}")
        print("   먼저 Flask 앱을 실행하여 DB를 초기화하세요.")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def clear_test_data(conn):
    """기존 테스트 데이터 삭제"""
    cursor = conn.cursor()
    
    print("\n🧹 기존 테스트 데이터 삭제 중...")
    
    # TEST- 로 시작하는 회원 관련 데이터 삭제 (역순)
    test_member_ids = "', '".join([m['member_id'] for m in TEST_MEMBERS])
    
    # 1. voucher_transactions
    cursor.execute(f"DELETE FROM voucher_transactions WHERE member_id IN ('{test_member_ids}')")
    print(f"   - voucher_transactions: {cursor.rowcount}개 삭제")
    
    # 2. subscription_usage
    cursor.execute(f"""
        DELETE FROM subscription_usage 
        WHERE subscription_id IN (
            SELECT subscription_id FROM member_subscriptions 
            WHERE member_id IN ('{test_member_ids}')
        )
    """)
    print(f"   - subscription_usage: {cursor.rowcount}개 삭제")
    
    # 3. rental_logs
    cursor.execute(f"DELETE FROM rental_logs WHERE member_id IN ('{test_member_ids}')")
    print(f"   - rental_logs: {cursor.rowcount}개 삭제")
    
    # 4. member_vouchers
    cursor.execute(f"DELETE FROM member_vouchers WHERE member_id IN ('{test_member_ids}')")
    print(f"   - member_vouchers: {cursor.rowcount}개 삭제")
    
    # 5. member_subscriptions
    cursor.execute(f"DELETE FROM member_subscriptions WHERE member_id IN ('{test_member_ids}')")
    print(f"   - member_subscriptions: {cursor.rowcount}개 삭제")
    
    # 6. locker_mapping
    cursor.execute(f"DELETE FROM locker_mapping WHERE member_id IN ('{test_member_ids}')")
    print(f"   - locker_mapping: {cursor.rowcount}개 삭제")
    
    # 7. members
    cursor.execute(f"DELETE FROM members WHERE member_id IN ('{test_member_ids}')")
    print(f"   - members: {cursor.rowcount}개 삭제")
    
    conn.commit()
    print("✅ 기존 테스트 데이터 삭제 완료\n")


def create_members(conn):
    """테스트 회원 생성"""
    cursor = conn.cursor()
    print("👤 테스트 회원 생성 중...")
    
    for member in TEST_MEMBERS:
        cursor.execute("""
            INSERT INTO members (member_id, name, phone, payment_password, status)
            VALUES (?, ?, ?, ?, 'active')
        """, (member['member_id'], member['name'], member['phone'], member['payment_password']))
        
        print(f"   ✓ {member['member_id']} ({member['name']}) - {member['phone']}")
    
    conn.commit()
    print(f"✅ 회원 {len(TEST_MEMBERS)}명 생성 완료\n")


def create_subscription_products(conn):
    """구독권 상품 생성 (없으면)"""
    cursor = conn.cursor()
    
    # 기존 구독권 상품 확인
    cursor.execute("SELECT COUNT(*) FROM subscription_products")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"ℹ️  구독권 상품 이미 존재: {count}개\n")
        return
    
    print("📋 구독권 상품 생성 중...")
    
    products = [
        ('SUB-1M-BASIC', '1개월 기본 이용권', 50000, 30, '{"top":1,"pants":1,"towel":1}'),
        ('SUB-3M-BASIC', '3개월 기본 이용권', 120000, 90, '{"top":1,"pants":1,"towel":1}'),
        ('SUB-3M-PREMIUM', '3개월 프리미엄 이용권', 180000, 90, '{"top":2,"pants":2,"towel":3}'),
    ]
    
    for product in products:
        cursor.execute("""
            INSERT OR IGNORE INTO subscription_products 
            (product_id, name, price, validity_days, daily_limits, enabled)
            VALUES (?, ?, ?, ?, ?, 1)
        """, product)
        print(f"   ✓ {product[0]} - {product[1]}")
    
    conn.commit()
    print("✅ 구독권 상품 생성 완료\n")


def create_voucher_products(conn):
    """금액권 상품 생성 (없으면)"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM voucher_products")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"ℹ️  금액권 상품 이미 존재: {count}개\n")
        return
    
    print("💳 금액권 상품 생성 중...")
    
    products = [
        ('VCH-5K', '5천원 금액권', 5000, 5000, 365, 0),
        ('VCH-10K', '1만원 금액권', 10000, 10000, 365, 0),
        ('VCH-50K', '5만원 금액권', 50000, 50000, 365, 0),
        ('VCH-100K', '10만원 금액권', 100000, 100000, 365, 0),
    ]
    
    for product in products:
        cursor.execute("""
            INSERT OR IGNORE INTO voucher_products 
            (product_id, name, price, charge_amount, validity_days, is_bonus, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, product)
        print(f"   ✓ {product[0]} - {product[1]}")
    
    conn.commit()
    print("✅ 금액권 상품 생성 완료\n")


def create_subscriptions_for_members(conn):
    """회원별 구독권 생성"""
    cursor = conn.cursor()
    print("📋 회원별 구독권 생성 중...")
    
    subscriptions = [
        # 회원B: 구독권만 (상의3/하의3/수건3)
        {
            'member_id': 'TEST-B',
            'product_id': 'SUB-1M-BASIC',
            'daily_limits': '{"top":3,"pants":3,"towel":3}',
            'description': '구독권만 (충분한 횟수)',
        },
        # 회원D1: 구독권(상의3/하의3) + 금액권
        {
            'member_id': 'TEST-D1',
            'product_id': 'SUB-1M-BASIC',
            'daily_limits': '{"top":3,"pants":3,"towel":0}',
            'description': '구독권으로 전부 커버 가능',
        },
        # 회원D2: 구독권(상의1/하의0) - 일부만 가능
        {
            'member_id': 'TEST-D2',
            'product_id': 'SUB-1M-BASIC',
            'daily_limits': '{"top":1,"pants":0,"towel":0}',
            'description': '구독권 일부만 사용 가능 (핵심 시나리오)',
        },
        # 회원D3: 구독권 전부 소진 (오늘 이미 사용함)
        {
            'member_id': 'TEST-D3',
            'product_id': 'SUB-1M-BASIC',
            'daily_limits': '{"top":1,"pants":1,"towel":1}',
            'description': '구독권 소진 (오늘 이미 사용)',
        },
    ]
    
    for sub in subscriptions:
        cursor.execute("""
            INSERT INTO member_subscriptions 
            (member_id, subscription_product_id, valid_from, valid_until, daily_limits, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (sub['member_id'], sub['product_id'], VALID_FROM_ISO, VALID_UNTIL_30D, sub['daily_limits']))
        
        subscription_id = cursor.lastrowid
        print(f"   ✓ {sub['member_id']}: {sub['description']}")
        
        # 회원D3는 오늘 이미 사용한 것으로 처리 (소진 상태)
        if sub['member_id'] == 'TEST-D3':
            today = VALID_FROM.date().isoformat()
            # 모든 카테고리 1회씩 사용 처리
            for category in ['top', 'pants', 'towel']:
                cursor.execute("""
                    INSERT INTO subscription_usage 
                    (subscription_id, usage_date, category, used_count)
                    VALUES (?, ?, ?, 1)
                """, (subscription_id, today, category))
            print(f"      → 오늘 사용량: top 1, pants 1, towel 1 (소진)")
    
    conn.commit()
    print("✅ 구독권 생성 완료\n")


def create_vouchers_for_members(conn):
    """회원별 금액권 생성"""
    cursor = conn.cursor()
    print("💳 회원별 금액권 생성 중...")
    
    vouchers = [
        # 회원C: 금액권만 50,000원
        {
            'member_id': 'TEST-C',
            'product_id': 'VCH-50K',
            'amount': 50000,
            'description': '금액권만 (5만원)',
        },
        # 회원D1: 구독권 + 금액권 10,000원
        {
            'member_id': 'TEST-D1',
            'product_id': 'VCH-10K',
            'amount': 10000,
            'description': '구독권 + 금액권',
        },
        # 회원D2: 금액권 2개 (5,000원 + 3,000원) - 쪼개기 테스트
        {
            'member_id': 'TEST-D2',
            'product_id': 'VCH-5K',
            'amount': 5000,
            'description': '금액권 1 (쪼개기 테스트)',
        },
        {
            'member_id': 'TEST-D2',
            'product_id': 'VCH-5K',  # 같은 상품이지만 별도 인스턴스
            'amount': 3000,
            'description': '금액권 2 (쪼개기 테스트, 잔액 3천원)',
        },
        # 회원D3: 금액권 10,000원 (구독권 소진)
        {
            'member_id': 'TEST-D3',
            'product_id': 'VCH-10K',
            'amount': 10000,
            'description': '금액권만 남음 (구독권 소진)',
        },
    ]
    
    for voucher in vouchers:
        valid_until = (VALID_FROM + timedelta(days=365)).isoformat()
        
        cursor.execute("""
            INSERT INTO member_vouchers 
            (member_id, voucher_product_id, original_amount, remaining_amount, 
             valid_from, valid_until, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        """, (voucher['member_id'], voucher['product_id'], voucher['amount'], 
              voucher['amount'], VALID_FROM_ISO, valid_until))
        
        print(f"   ✓ {voucher['member_id']}: {voucher['description']}")
    
    conn.commit()
    print("✅ 금액권 생성 완료\n")


def print_summary(conn):
    """생성된 테스트 데이터 요약"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("📊 테스트 회원 요약")
    print("="*60)
    
    for member in TEST_MEMBERS:
        member_id = member['member_id']
        
        # 구독권 확인
        cursor.execute("""
            SELECT s.subscription_id, s.daily_limits, sp.name
            FROM member_subscriptions s
            JOIN subscription_products sp ON s.subscription_product_id = sp.product_id
            WHERE s.member_id = ? AND s.status = 'active'
        """, (member_id,))
        subscriptions = cursor.fetchall()
        
        # 금액권 확인
        cursor.execute("""
            SELECT v.voucher_id, v.remaining_amount, vp.name
            FROM member_vouchers v
            JOIN voucher_products vp ON v.voucher_product_id = vp.product_id
            WHERE v.member_id = ? AND v.status = 'active'
        """, (member_id,))
        vouchers = cursor.fetchall()
        
        print(f"\n[{member_id}] {member['name']}")
        print(f"  전화번호: {member['phone']}")
        print(f"  비밀번호: {member['payment_password']}")
        print(f"  설명: {member['description']}")
        
        if subscriptions:
            print(f"  📋 구독권:")
            for sub in subscriptions:
                limits = json.loads(sub['daily_limits'])
                print(f"     - {sub['name']}: {limits}")
        else:
            print(f"  📋 구독권: 없음")
        
        if vouchers:
            print(f"  💳 금액권:")
            for voucher in vouchers:
                print(f"     - {voucher['name']}: {voucher['remaining_amount']:,}원")
        else:
            print(f"  💳 금액권: 없음")
    
    print("\n" + "="*60)
    print("✅ 테스트 데이터 생성 완료!")
    print("="*60)
    print("\n📸 이제 capture_screens.py를 실행하여 화면을 캡쳐하세요.")
    print("\n예시:")
    print("  python scripts/testing/capture_screens.py --scenario A --phone 01011111111")
    print("  python scripts/testing/capture_screens.py --scenario B --phone 01022222222")
    print("  python scripts/testing/capture_screens.py --scenario D2 --phone 01055555555")
    print()


def main():
    """메인 실행"""
    print("\n" + "="*60)
    print("🚀 테스트 데이터 생성 스크립트")
    print("="*60)
    
    conn = get_connection()
    
    try:
        # 1. 기존 테스트 데이터 삭제
        clear_test_data(conn)
        
        # 2. 상품 생성 (없으면)
        create_subscription_products(conn)
        create_voucher_products(conn)
        
        # 3. 회원 생성
        create_members(conn)
        
        # 4. 구독권 생성
        create_subscriptions_for_members(conn)
        
        # 5. 금액권 생성
        create_vouchers_for_members(conn)
        
        # 6. 요약 출력
        print_summary(conn)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()


if __name__ == '__main__':
    main()

