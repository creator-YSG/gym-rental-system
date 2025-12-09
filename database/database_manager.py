"""
데이터베이스 매니저
"""
import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

class DatabaseManager:
    """SQLite 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        if db_path is None:
            # 기본 경로: instance/rental_system.db
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, 'instance', 'rental_system.db')
        
        self.db_path = db_path
        self.connection = None
        
    def connect(self):
        """데이터베이스 연결"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Row 형태로 결과 반환
            return True
        except sqlite3.Error as e:
            print(f"❌ 데이터베이스 연결 실패: {e}")
            return False
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[sqlite3.Cursor]:
        """쿼리 실행"""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor
        except sqlite3.Error as e:
            print(f"❌ 쿼리 실행 실패: {e}")
            print(f"   쿼리: {query}")
            print(f"   파라미터: {params}")
            return None
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """단일 레코드 조회"""
        cursor = self.execute_query(query, params)
        if cursor:
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """여러 레코드 조회"""
        cursor = self.execute_query(query, params)
        if cursor:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        return []
    
    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """회원 정보 조회"""
        query = "SELECT * FROM members WHERE member_id = ?"
        return self.fetch_one(query, (member_id,))
    
    def get_inventory(self, item_type: str, item_size: str = None) -> Optional[Dict[str, Any]]:
        """재고 조회"""
        if item_size:
            query = "SELECT * FROM inventory WHERE item_type = ? AND item_size = ?"
            return self.fetch_one(query, (item_type, item_size))
        else:
            query = "SELECT * FROM inventory WHERE item_type = ? AND item_size IS NULL"
            return self.fetch_one(query, (item_type,))
    
    def get_active_rentals(self, member_id: str) -> List[Dict[str, Any]]:
        """회원의 미반납 대여 목록 조회"""
        query = """
            SELECT * FROM rentals 
            WHERE member_id = ? AND status = 'rented'
            ORDER BY rental_date DESC
        """
        return self.fetch_all(query, (member_id,))
    
    def update_inventory(self, item_type: str, item_size: str, quantity_change: int) -> bool:
        """재고 업데이트"""
        if item_size:
            query = """
                UPDATE inventory 
                SET available_quantity = available_quantity + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE item_type = ? AND item_size = ?
            """
            cursor = self.execute_query(query, (quantity_change, item_type, item_size))
        else:
            query = """
                UPDATE inventory 
                SET available_quantity = available_quantity + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE item_type = ? AND item_size IS NULL
            """
            cursor = self.execute_query(query, (quantity_change, item_type))
        
        return cursor is not None
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.close()


