#!/usr/bin/env python3
"""
F-BOX 로컬 데이터베이스 초기화 스크립트

사용법:
    python database/init_db.py
"""

import sqlite3
import os
from pathlib import Path

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent

# 데이터베이스 파일 경로
DB_PATH = PROJECT_ROOT / 'instance' / 'fbox_local.db'
SCHEMA_PATH = PROJECT_ROOT / 'database' / 'local_schema.sql'


def init_database():
    """데이터베이스 초기화 및 스키마 적용"""
    
    # instance 디렉토리 생성
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # 기존 DB 파일 존재 여부 확인
    if DB_PATH.exists():
        response = input(f"기존 데이터베이스 파일이 존재합니다 ({DB_PATH}). 삭제하고 재생성하시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("초기화 취소됨")
            return
        os.remove(DB_PATH)
        print(f"기존 파일 삭제: {DB_PATH}")
    
    # 스키마 파일 읽기
    if not SCHEMA_PATH.exists():
        print(f"스키마 파일을 찾을 수 없습니다: {SCHEMA_PATH}")
        return
    
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # 데이터베이스 생성 및 스키마 적용
    print(f"데이터베이스 생성 중: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    
    try:
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        print("✓ 스키마 적용 완료")
        
        # 테이블 목록 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        print(f"\n생성된 테이블 ({len(tables)}개):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 초기 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        print(f"\n초기 상품 데이터: {product_count}개")
        
        cursor.execute("SELECT COUNT(*) FROM promotions")
        promo_count = cursor.fetchone()[0]
        print(f"초기 프로모션 데이터: {promo_count}개")
        
        cursor.execute("SELECT COUNT(*) FROM members")
        member_count = cursor.fetchone()[0]
        print(f"초기 회원 데이터: {member_count}개")
        
        print("\n✅ 데이터베이스 초기화 성공!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()


def test_connection():
    """데이터베이스 연결 테스트"""
    if not DB_PATH.exists():
        print(f"데이터베이스 파일이 없습니다: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count = cursor.fetchone()[0]
        conn.close()
        print(f"✓ 데이터베이스 연결 성공 (테이블 {count}개)")
        return True
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False


if __name__ == '__main__':
    print("="*50)
    print("F-BOX 로컬 데이터베이스 초기화")
    print("="*50)
    init_database()
    print("\n" + "="*50)
    print("연결 테스트")
    print("="*50)
    test_connection()

