"""
로컬 캐시 서비스 (횟수 기반)

SQLite + 메모리 캐시 조합으로 빠른 데이터 접근 제공
- 읽기: 메모리 캐시 (빠름)
- 쓰기: 메모리 + SQLite 동시 (영속성)
- 회원 잔여 횟수 관리 (1개 대여 = 1회 차감)
"""

import sqlite3
import threading
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from pathlib import Path


class LocalCache:
    """로컬 캐시 관리 클래스"""
    
    def __init__(self, db_path: str = None):
        """
        초기화
        
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        if db_path is None:
            # 기본 경로: instance/fbox_local.db
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / 'instance' / 'fbox_local.db'
        
        self.db_path = str(db_path)
        self.conn = None
        self.lock = threading.Lock()  # 동시 접근 제어
        
        # 메모리 캐시
        self._members_cache: Dict[str, Dict] = {}  # {member_id: member_data}
        self._locker_cache: Dict[int, str] = {}    # {locker_number: member_id}
        self._products_cache: Dict[str, Dict] = {} # {product_id: product_data}
        self._device_cache: Dict[str, Dict] = {}   # {device_uuid: device_data}
        self._device_registry: Dict[str, Dict] = {} # {device_uuid: registry_data}
        
        self._connect()
        self._load_cache()
    
    def _connect(self):
        """데이터베이스 연결"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
    
    def _load_cache(self):
        """데이터베이스에서 메모리 캐시로 로드"""
        with self.lock:
            cursor = self.conn.cursor()
            
            # 회원 정보 로드
            cursor.execute('SELECT * FROM members')
            for row in cursor.fetchall():
                self._members_cache[row['member_id']] = dict(row)
            
            # 락카 매핑 로드
            cursor.execute('SELECT locker_number, member_id FROM locker_mapping')
            for row in cursor.fetchall():
                self._locker_cache[row['locker_number']] = row['member_id']
            
            # 상품 정보 로드
            cursor.execute('SELECT * FROM products WHERE enabled = 1')
            for row in cursor.fetchall():
                self._products_cache[row['product_id']] = dict(row)
            
            # 기기 레지스트리 로드
            try:
                cursor.execute('SELECT * FROM device_registry')
                for row in cursor.fetchall():
                    self._device_registry[row['device_uuid']] = dict(row)
            except sqlite3.OperationalError:
                # 테이블이 없으면 무시 (마이그레이션 전)
                pass
            
            # 기기 상태 로드 (device_uuid 기반)
            try:
                cursor.execute('SELECT * FROM device_cache')
                for row in cursor.fetchall():
                    # device_uuid 컬럼이 있으면 사용, 없으면 device_id 사용 (호환성)
                    key = row['device_uuid'] if 'device_uuid' in row.keys() else row.get('device_id')
                    if key:
                        self._device_cache[key] = dict(row)
            except sqlite3.OperationalError:
                pass
            
            print(f"[LocalCache] 캐시 로드 완료:")
            print(f"  - 회원: {len(self._members_cache)}명")
            print(f"  - 락카: {len(self._locker_cache)}개")
            print(f"  - 상품: {len(self._products_cache)}개")
            print(f"  - 기기 레지스트리: {len(self._device_registry)}개")
            print(f"  - 기기 상태: {len(self._device_cache)}개")
    
    # =============================
    # 회원 관련
    # =============================
    
    def get_member(self, member_id: str) -> Optional[Dict]:
        """회원 정보 조회 (메모리 캐시)"""
        return self._members_cache.get(member_id)
    
    def get_member_count(self, member_id: str) -> int:
        """회원 잔여 횟수 조회"""
        member = self.get_member(member_id)
        return member['remaining_count'] if member else 0
    
    def update_member_count(self, member_id: str, amount: int, 
                           transaction_type: str, description: str = '') -> Tuple[int, int]:
        """
        회원 잔여 횟수 업데이트
        
        Args:
            member_id: 회원 ID
            amount: 변동 횟수 (양수: 충전, 음수: 차감)
            transaction_type: 거래 유형 ('charge', 'rental', 'refund', 'bonus')
            description: 설명
        
        Returns:
            (변동 전 횟수, 변동 후 횟수)
        """
        with self.lock:
            member = self._members_cache.get(member_id)
            if not member:
                raise ValueError(f"회원을 찾을 수 없습니다: {member_id}")
            
            count_before = member['remaining_count']
            count_after = count_before + amount
            
            if count_after < 0:
                raise ValueError(f"잔여 횟수 부족: {count_before}회 (필요: {abs(amount)}회)")
            
            # 메모리 캐시 업데이트
            member['remaining_count'] = count_after
            if amount > 0:
                member['total_charged'] += amount
            else:
                member['total_used'] += abs(amount)
            member['updated_at'] = datetime.now().isoformat()
            
            # SQLite 업데이트
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE members 
                SET remaining_count = ?,
                    total_charged = ?,
                    total_used = ?,
                    updated_at = ?
                WHERE member_id = ?
            ''', (count_after, member['total_charged'], 
                  member['total_used'], member['updated_at'], member_id))
            
            # 횟수 변동 로그 기록
            cursor.execute('''
                INSERT INTO usage_logs 
                (member_id, amount, count_before, count_after, 
                 transaction_type, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (member_id, amount, count_before, count_after,
                  transaction_type, description, datetime.now().isoformat()))
            
            self.conn.commit()
            
            print(f"[LocalCache] 횟수 업데이트: {member_id} {count_before}회 → {count_after}회")
            
            return count_before, count_after
    
    # =============================
    # 락카 매핑
    # =============================
    
    def assign_locker(self, locker_number: int, member_id: str) -> bool:
        """
        락카 배정
        
        Args:
            locker_number: 락카 번호
            member_id: 회원 ID
        
        Returns:
            성공 여부
        """
        with self.lock:
            # 회원 존재 확인
            if member_id not in self._members_cache:
                raise ValueError(f"회원을 찾을 수 없습니다: {member_id}")
            
            # 락카가 이미 배정되어 있는지 확인
            if locker_number in self._locker_cache:
                existing_member = self._locker_cache[locker_number]
                print(f"[LocalCache] 경고: 락카 {locker_number}는 이미 {existing_member}에게 배정됨")
                # 기존 배정 해제 후 재배정
            
            # 메모리 캐시 업데이트
            self._locker_cache[locker_number] = member_id
            
            # SQLite 업데이트
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO locker_mapping 
                (locker_number, member_id, assigned_at)
                VALUES (?, ?, ?)
            ''', (locker_number, member_id, datetime.now().isoformat()))
            
            self.conn.commit()
            
            print(f"[LocalCache] 락카 배정: {locker_number}번 → {member_id}")
            
            return True
    
    def get_member_by_locker(self, locker_number: int) -> Optional[str]:
        """락카 번호로 회원 ID 조회 (메모리 캐시)"""
        return self._locker_cache.get(locker_number)
    
    def release_locker(self, locker_number: int) -> bool:
        """
        락카 해제
        
        Args:
            locker_number: 락카 번호
        
        Returns:
            성공 여부
        """
        with self.lock:
            if locker_number not in self._locker_cache:
                return False
            
            # 메모리 캐시에서 삭제
            del self._locker_cache[locker_number]
            
            # SQLite에서 삭제
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM locker_mapping WHERE locker_number = ?', 
                         (locker_number,))
            self.conn.commit()
            
            print(f"[LocalCache] 락카 해제: {locker_number}번")
            
            return True
    
    def get_locker_info(self, locker_number: int) -> Optional[Dict]:
        """
        락카 배정 정보 조회
        
        Args:
            locker_number: 락카 번호
        
        Returns:
            {'member_id': ..., 'assigned_at': ...} 또는 None
        """
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT member_id, assigned_at FROM locker_mapping 
                WHERE locker_number = ?
            ''', (locker_number,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'member_id': row['member_id'],
                    'assigned_at': row['assigned_at']
                }
            return None
    
    def get_all_lockers(self) -> Dict[int, str]:
        """
        모든 배정된 락카 목록 조회
        
        Returns:
            {locker_number: member_id, ...}
        """
        return dict(self._locker_cache)
    
    # =============================
    # 상품 관련
    # =============================
    
    def get_products(self, gym_id: str = 'GYM001', enabled_only: bool = True) -> List[Dict]:
        """
        상품 목록 조회
        
        Args:
            gym_id: 헬스장 ID
            enabled_only: 활성화된 상품만 조회
        
        Returns:
            상품 리스트 (display_order 순서)
        """
        products = [
            p for p in self._products_cache.values()
            if p['gym_id'] == gym_id and (not enabled_only or p['enabled'])
        ]
        return sorted(products, key=lambda x: x['display_order'])
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """상품 정보 조회 (메모리 캐시)"""
        return self._products_cache.get(product_id)
    
    def get_product_by_device(self, device_id: str) -> Optional[Dict]:
        """기기 ID로 상품 조회"""
        for product in self._products_cache.values():
            if product['device_id'] == device_id:
                return product
        return None
    
    def update_product_stock(self, product_id: str, stock: int) -> bool:
        """
        상품 재고 업데이트
        
        Args:
            product_id: 상품 ID
            stock: 새 재고 수량
        
        Returns:
            성공 여부
        """
        with self.lock:
            product = self._products_cache.get(product_id)
            if not product:
                return False
            
            # 메모리 캐시 업데이트
            product['stock'] = stock
            product['updated_at'] = datetime.now().isoformat()
            
            # SQLite 업데이트
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE products 
                SET stock = ?, updated_at = ?
                WHERE product_id = ?
            ''', (stock, product['updated_at'], product_id))
            
            self.conn.commit()
            
            return True
    
    # =============================
    # 기기 레지스트리 (MAC 기반 고유 ID)
    # =============================
    
    def register_device(self, device_uuid: str, mac_address: str, 
                       size: str = '', category: str = '', 
                       device_name: str = '', ip_address: str = '', 
                       firmware_version: str = '', stock: int = 0) -> Dict:
        """
        새 기기 등록 또는 기존 기기 정보 업데이트
        + products 테이블에도 자동 생성/업데이트
        
        Args:
            device_uuid: MAC 기반 고유 ID (예: "FBOX-A4CF12345678")
            mac_address: 원본 MAC 주소 (예: "A4:CF:12:34:56:78")
            size: 사이즈 (예: "105")
            category: 카테고리 (top/pants/towel/sweat_towel/other)
            device_name: 상품명 (ESP32에서 설정, 한글 가능)
            ip_address: IP 주소
            firmware_version: 펌웨어 버전
            stock: 현재 재고
        
        Returns:
            등록된 기기 정보
        """
        with self.lock:
            now = datetime.now().isoformat()
            cursor = self.conn.cursor()
            
            # 기존 기기 확인
            existing = self._device_registry.get(device_uuid)
            
            if existing:
                # 기존 기기 업데이트
                cursor.execute('''
                    UPDATE device_registry 
                    SET size = ?, category = ?, device_name = ?,
                        ip_address = ?, firmware_version = ?, 
                        last_seen_at = ?, updated_at = ?
                    WHERE device_uuid = ?
                ''', (size, category, device_name, ip_address, firmware_version, 
                      now, now, device_uuid))
                
                existing['size'] = size
                existing['category'] = category
                existing['device_name'] = device_name
                existing['ip_address'] = ip_address
                existing['firmware_version'] = firmware_version
                existing['last_seen_at'] = now
                existing['updated_at'] = now
                
                print(f"[LocalCache] 기기 정보 업데이트: {device_uuid} ({device_name})")
                device_info = existing
            else:
                # 새 기기 등록
                cursor.execute('''
                    INSERT INTO device_registry 
                    (device_uuid, mac_address, size, category, device_name,
                     ip_address, firmware_version, first_seen_at, last_seen_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (device_uuid, mac_address, size, category, device_name,
                      ip_address, firmware_version, now, now, now))
                
                device_info = {
                    'device_uuid': device_uuid,
                    'mac_address': mac_address,
                    'device_name': device_name,
                    'size': size,
                    'category': category,
                    'product_id': None,
                    'ip_address': ip_address,
                    'firmware_version': firmware_version,
                    'first_seen_at': now,
                    'last_seen_at': now,
                    'updated_at': now
                }
                self._device_registry[device_uuid] = device_info
                
                print(f"[LocalCache] ✅ 새 기기 등록: {device_uuid} ({device_name or 'No Name'})")
            
            self.conn.commit()
            
            # products 테이블에도 생성/업데이트
            if category and size:
                product_id = self._create_or_update_product(
                    device_uuid=device_uuid,
                    category=category,
                    size=size,
                    name=device_name,
                    stock=stock
                )
                device_info['product_id'] = product_id
                
                # device_registry에 product_id 업데이트
                cursor.execute('''
                    UPDATE device_registry SET product_id = ? WHERE device_uuid = ?
                ''', (product_id, device_uuid))
                self.conn.commit()
            
            return device_info
    
    def _create_or_update_product(self, device_uuid: str, category: str, 
                                   size: str, name: str, stock: int = 0) -> str:
        """
        products 테이블에 상품 생성 또는 업데이트
        
        Args:
            device_uuid: 기기 UUID (FK)
            category: 카테고리
            size: 사이즈
            name: 상품명
            stock: 재고
        
        Returns:
            product_id
        """
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        
        # device_uuid로 기존 상품 확인
        cursor.execute('SELECT product_id FROM products WHERE device_uuid = ?', (device_uuid,))
        row = cursor.fetchone()
        
        if row:
            # 기존 상품 업데이트
            product_id = row[0]
            cursor.execute('''
                UPDATE products 
                SET category = ?, size = ?, name = ?, stock = ?, updated_at = ?
                WHERE device_uuid = ?
            ''', (category, size, name, stock, now, device_uuid))
            print(f"[LocalCache] 상품 업데이트: {product_id} ({name})")
        else:
            # 새 상품 생성
            # product_id 형식: P-{CATEGORY}-{SIZE} (예: P-TOP-105)
            category_upper = category.upper()
            product_id = f"P-{category_upper}-{size}"
            
            # 중복 체크 (같은 product_id가 있으면 UUID 추가)
            cursor.execute('SELECT 1 FROM products WHERE product_id = ?', (product_id,))
            if cursor.fetchone():
                # 중복 시 UUID 일부 추가
                product_id = f"P-{category_upper}-{size}-{device_uuid[-4:]}"
            
            cursor.execute('''
                INSERT INTO products 
                (product_id, gym_id, category, size, name, device_uuid, stock, enabled, display_order, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, 'GYM001', category, size, name, device_uuid, stock, 1, 0, now))
            
            # 캐시에도 추가
            self._products_cache[product_id] = {
                'product_id': product_id,
                'gym_id': 'GYM001',
                'category': category,
                'size': size,
                'name': name,
                'device_uuid': device_uuid,
                'stock': stock,
                'enabled': True,
                'display_order': 0,
                'updated_at': now
            }
            
            print(f"[LocalCache] ✅ 새 상품 생성: {product_id} ({name})")
        
        self.conn.commit()
        return product_id
    
    def get_device_registry(self, device_uuid: str) -> Optional[Dict]:
        """기기 레지스트리 정보 조회"""
        return self._device_registry.get(device_uuid)
    
    def get_all_registered_devices(self) -> List[Dict]:
        """모든 등록된 기기 조회"""
        return list(self._device_registry.values())
    
    def update_device_registry(self, device_uuid: str, **kwargs) -> bool:
        """
        기기 레지스트리 정보 업데이트 (이름, 카테고리, 상품 연결 등)
        
        Args:
            device_uuid: 기기 UUID
            **kwargs: device_name, category, product_id 등
        """
        with self.lock:
            device = self._device_registry.get(device_uuid)
            if not device:
                return False
            
            # 메모리 캐시 업데이트
            for key, value in kwargs.items():
                if key in device:
                    device[key] = value
            device['updated_at'] = datetime.now().isoformat()
            
            # SQLite 업데이트
            cursor = self.conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [device['updated_at'], device_uuid]
            
            cursor.execute(f'''
                UPDATE device_registry 
                SET {set_clause}, updated_at = ?
                WHERE device_uuid = ?
            ''', values)
            
            self.conn.commit()
            return True
    
    # =============================
    # 기기 상태 (실시간)
    # =============================
    
    def get_device(self, device_uuid: str) -> Optional[Dict]:
        """기기 상태 조회 (메모리 캐시)"""
        return self._device_cache.get(device_uuid)
    
    def get_all_devices(self) -> List[Dict]:
        """모든 기기 상태 조회"""
        return list(self._device_cache.values())
    
    def update_device_status(self, device_uuid: str, **kwargs) -> bool:
        """
        기기 상태 업데이트
        
        Args:
            device_uuid: 기기 UUID (MAC 기반)
            **kwargs: 업데이트할 필드 (stock, door_state, floor_state, locked 등)
        
        Returns:
            성공 여부
        """
        with self.lock:
            device = self._device_cache.get(device_uuid)
            if device is None:
                # 기기가 없으면 새로 생성
                device = {
                    'device_uuid': device_uuid,
                    'size': kwargs.get('size', ''),
                    'stock': 0,
                    'door_state': 'closed',
                    'floor_state': 'reached',
                    'locked': False,
                    'wifi_rssi': None,
                    'last_heartbeat': None,
                    'updated_at': datetime.now().isoformat()
                }
                self._device_cache[device_uuid] = device
            
            # 메모리 캐시 업데이트
            for key, value in kwargs.items():
                device[key] = value
            device['updated_at'] = datetime.now().isoformat()
            
            # SQLite 업데이트
            cursor = self.conn.cursor()
            
            # UPSERT 구문 (SQLite 3.24+)
            fields = ['device_uuid'] + list(kwargs.keys()) + ['updated_at']
            placeholders = ', '.join(['?' for _ in fields])
            update_clause = ', '.join([f"{f} = excluded.{f}" for f in fields if f != 'device_uuid'])
            
            values = [device_uuid] + [kwargs.get(f) for f in kwargs.keys()] + [device['updated_at']]
            
            cursor.execute(f'''
                INSERT INTO device_cache ({', '.join(fields)})
                VALUES ({placeholders})
                ON CONFLICT(device_uuid) DO UPDATE SET {update_clause}
            ''', values)
            
            self.conn.commit()
            
            return True
    
    def update_heartbeat(self, device_uuid: str, wifi_rssi: int = None) -> bool:
        """
        기기 하트비트 업데이트
        
        Args:
            device_uuid: 기기 UUID
            wifi_rssi: Wi-Fi 신호 강도
        
        Returns:
            성공 여부
        """
        kwargs = {'last_heartbeat': datetime.now().isoformat()}
        if wifi_rssi is not None:
            kwargs['wifi_rssi'] = wifi_rssi
        
        return self.update_device_status(device_uuid, **kwargs)
    
    def get_product_by_device_uuid(self, device_uuid: str) -> Optional[Dict]:
        """기기 UUID로 연결된 상품 조회"""
        registry = self._device_registry.get(device_uuid)
        if registry and registry.get('product_id'):
            return self._products_cache.get(registry['product_id'])
        return None
    
    # =============================
    # 대여 로그
    # =============================
    
    def add_rental_log(self, member_id: str, locker_number: int, 
                      product_id: str, device_id: str,
                      quantity: int, count_before: int, count_after: int) -> int:
        """
        대여 로그 추가 (횟수 기반)
        
        Args:
            member_id: 회원 ID
            locker_number: 락카 번호
            product_id: 상품 ID
            device_id: 기기 ID
            quantity: 대여 수량 (= 차감 횟수)
            count_before: 대여 전 잔여 횟수
            count_after: 대여 후 잔여 횟수
        
        Returns:
            rental_id
        """
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO rental_logs 
                (member_id, locker_number, product_id, device_id, 
                 quantity, count_before, count_after, created_at, synced_to_sheets)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (member_id, locker_number, product_id, device_id,
                  quantity, count_before, count_after, datetime.now().isoformat()))
            
            rental_id = cursor.lastrowid
            self.conn.commit()
            
            return rental_id
    
    def get_unsynced_rentals(self) -> List[Dict]:
        """Google Sheets에 동기화되지 않은 대여 로그 조회"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM rental_logs 
                WHERE synced_to_sheets = 0 
                ORDER BY created_at
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_rentals_synced(self, rental_ids: List[int]):
        """대여 로그를 동기화 완료로 표시"""
        if not rental_ids:
            return
        
        with self.lock:
            cursor = self.conn.cursor()
            placeholders = ', '.join(['?' for _ in rental_ids])
            cursor.execute(f'''
                UPDATE rental_logs 
                SET synced_to_sheets = 1 
                WHERE id IN ({placeholders})
            ''', rental_ids)
            self.conn.commit()
    
    # =============================
    # MQTT 이벤트 로깅
    # =============================
    
    def log_mqtt_event(self, device_id: str, event_type: str, payload: dict) -> int:
        """
        MQTT 이벤트 DB 로깅
        
        Args:
            device_id: 기기 ID
            event_type: 이벤트 타입
            payload: 이벤트 페이로드 (JSON으로 저장)
        
        Returns:
            event_id
        """
        import json
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO mqtt_events (device_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
            ''', (device_id, event_type, json.dumps(payload), datetime.now().isoformat()))
            
            event_id = cursor.lastrowid
            self.conn.commit()
            
            return event_id
    
    def get_recent_events(self, device_id: str = None, limit: int = 50) -> List[Dict]:
        """
        최근 MQTT 이벤트 조회
        
        Args:
            device_id: 기기 ID (None이면 전체)
            limit: 조회 개수
        """
        import json
        with self.lock:
            cursor = self.conn.cursor()
            
            if device_id:
                cursor.execute('''
                    SELECT * FROM mqtt_events 
                    WHERE device_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (device_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM mqtt_events 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
            
            results = []
            for row in cursor.fetchall():
                event = dict(row)
                if event.get('payload'):
                    event['payload'] = json.loads(event['payload'])
                results.append(event)
            
            return results
    
    # =============================
    # 동기화
    # =============================
    
    def reload_members(self):
        """회원 정보 재로드 (Google Sheets 동기화 후)"""
        with self.lock:
            self._members_cache.clear()
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM members')
            for row in cursor.fetchall():
                self._members_cache[row['member_id']] = dict(row)
            print(f"[LocalCache] 회원 정보 재로드: {len(self._members_cache)}명")
    
    def reload_products(self):
        """상품 정보 재로드 (Google Sheets 동기화 후)"""
        with self.lock:
            self._products_cache.clear()
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM products WHERE enabled = 1')
            for row in cursor.fetchall():
                self._products_cache[row['product_id']] = dict(row)
            print(f"[LocalCache] 상품 정보 재로드: {len(self._products_cache)}개")
    
    # =============================
    # 유틸리티
    # =============================
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            print("[LocalCache] 데이터베이스 연결 종료")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

