#!/usr/bin/env python3
"""
마이그레이션: members 테이블에 payment_password 칼럼 추가

실행: python database/migrate_add_payment_password.py
"""

import sqlite3
from pathlib import Path


def migrate():
    """payment_password 칼럼을 members 테이블에 추가"""
    db_path = Path(__file__).parent.parent / 'instance' / 'fbox_local.db'
    
    if not db_path.exists():
        print(f"❌ DB 파일이 없습니다: {db_path}")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # 현재 칼럼 확인
        cursor.execute("PRAGMA table_info(members)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'payment_password' in columns:
            print("✓ payment_password 칼럼이 이미 존재합니다.")
            return True
        
        # 칼럼 추가
        cursor.execute("ALTER TABLE members ADD COLUMN payment_password TEXT")
        conn.commit()
        
        print("✅ payment_password 칼럼 추가 완료!")
        
        # 결과 확인
        cursor.execute("PRAGMA table_info(members)")
        print("\n현재 members 테이블 구조:")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")
        
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        return False
        
    finally:
        conn.close()


if __name__ == '__main__':
    migrate()


