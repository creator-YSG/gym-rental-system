#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트
"""
import os
import sqlite3

def init_database():
    """데이터베이스 초기화"""
    # scripts/setup 디렉토리에서 프로젝트 루트로 이동 (두 단계 위)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, 'instance', 'rental_system.db')
    schema_path = os.path.join(base_dir, 'database', 'schema.sql')
    
    # instance 폴더 생성
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 데이터베이스 생성 및 스키마 실행
    print(f"📊 데이터베이스 초기화 중...")
    print(f"   경로: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()
        conn.executescript(schema)
    
    conn.commit()
    conn.close()
    
    print("✅ 데이터베이스 초기화 완료!")

if __name__ == '__main__':
    init_database()

