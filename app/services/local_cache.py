"""
로컬 캐시 서비스 (금액권/구독권 기반)

SQLite + 메모리 캐시 조합으로 빠른 데이터 접근 제공
- 읽기: 메모리 캐시 (빠름)
- 쓰기: 메모리 + SQLite 동시 (영속성)
- 금액권/구독권 관리
"""

import sqlite3
import threading
import json
from datetime import datetime, date, timedelta
from typing import Dict, Optional, List, Tuple
from pathlib import Path
import pytz

# 한국 시간대
KST = pytz.timezone('Asia/Seoul')


def get_kst_now() -> datetime:
    """현재 한국 시간 반환"""
    return datetime.now(KST)


def get_kst_today() -> date:
    """현재 한국 날짜 반환"""
    return get_kst_now().date()


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
        self._voucher_products_cache: Dict[str, Dict] = {}  # {product_id: voucher_product}
        self._subscription_products_cache: Dict[str, Dict] = {}  # {product_id: subscription_product}
        
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
            try:
                cursor.execute('SELECT * FROM members')
                for row in cursor.fetchall():
                    self._members_cache[row['member_id']] = dict(row)
            except sqlite3.OperationalError:
                pass
            
            # 락카 매핑 로드
            try:
                cursor.execute('SELECT locker_number, member_id FROM locker_mapping')
                for row in cursor.fetchall():
                    self._locker_cache[row['locker_number']] = row['member_id']
            except sqlite3.OperationalError:
                pass
            
            # 상품 정보 로드
            try:
                cursor.execute('SELECT * FROM products WHERE enabled = 1')
                for row in cursor.fetchall():
                    self._products_cache[row['product_id']] = dict(row)
            except sqlite3.OperationalError:
                pass
            
            # 금액권 상품 로드
            try:
                cursor.execute('SELECT * FROM voucher_products WHERE enabled = 1')
                for row in cursor.fetchall():
                    self._voucher_products_cache[row['product_id']] = dict(row)
            except sqlite3.OperationalError:
                pass
            
            # 구독 상품 로드
            try:
                cursor.execute('SELECT * FROM subscription_products WHERE enabled = 1')
                for row in cursor.fetchall():
                    product = dict(row)
                    # JSON 파싱
                    if product.get('daily_limits'):
                        product['daily_limits'] = json.loads(product['daily_limits'])
                    self._subscription_products_cache[row['product_id']] = product
            except sqlite3.OperationalError:
                pass
            
            # 기기 레지스트리 로드
            try:
                cursor.execute('SELECT * FROM device_registry')
                for row in cursor.fetchall():
                    self._device_registry[row['device_uuid']] = dict(row)
            except sqlite3.OperationalError:
                pass
            
            # 기기 상태 로드
            try:
                cursor.execute('SELECT * FROM device_cache')
                for row in cursor.fetchall():
                    key = row['device_uuid'] if 'device_uuid' in row.keys() else row.get('device_id')
                    if key:
                        self._device_cache[key] = dict(row)
            except sqlite3.OperationalError:
                pass
            
            print(f"[LocalCache] 캐시 로드 완료:")
            print(f"  - 회원: {len(self._members_cache)}명")
            print(f"  - 상품: {len(self._products_cache)}개")
            print(f"  - 금액권 상품: {len(self._voucher_products_cache)}개")
            print(f"  - 구독 상품: {len(self._subscription_products_cache)}개")
            print(f"  - 기기: {len(self._device_registry)}개")
    
    # =============================
    # 회원 관련
    # =============================
    
    def get_member(self, member_id: str) -> Optional[Dict]:
        """회원 정보 조회 (캐시 → DB fallback)"""
        # 1. 캐시에서 조회
        if member_id in self._members_cache:
            return self._members_cache[member_id]
        
        # 2. 캐시에 없으면 DB에서 직접 조회
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM members WHERE member_id = ?', (member_id,))
            row = cursor.fetchone()
            if row:
                member = dict(row)
                self._members_cache[member_id] = member  # 캐시에 추가
                return member
        return None
    
    def get_member_by_phone(self, phone: str) -> Optional[Dict]:
        """전화번호로 회원 조회 (캐시 → DB fallback)"""
        # 하이픈 제거
        phone_normalized = phone.replace('-', '').replace(' ', '')
        
        # 1. 캐시에서 조회
        for member in self._members_cache.values():
            member_phone = (member.get('phone') or '').replace('-', '').replace(' ', '')
            if member_phone == phone_normalized:
                return member
        
        # 2. 캐시에 없으면 DB에서 직접 조회
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM members WHERE phone = ? OR phone = ?', 
                          (phone, phone_normalized))
            row = cursor.fetchone()
            if row:
                member = dict(row)
                self._members_cache[member['member_id']] = member  # 캐시에 추가
                print(f"[LocalCache] DB에서 회원 로드: {member['member_id']} - {member['name']}")
                return member
        return None
    
    def verify_payment_password(self, member_id: str, password: str) -> Tuple[bool, str]:
        """
        결제 비밀번호 검증
        
        Args:
            member_id: 회원 ID
            password: 입력된 비밀번호 (6자리 숫자)
        
        Returns:
            (성공 여부, 메시지)
        """
        member = self.get_member(member_id)
        
        if not member:
            return False, "회원 정보를 찾을 수 없습니다."
        
        stored_password = member.get('payment_password')
        
        if not stored_password:
            return False, "결제 비밀번호가 설정되지 않았습니다. 관리자에게 문의하세요."
        
        # 문자열로 비교 (숫자가 문자열로 저장될 수 있음)
        if str(password).strip() == str(stored_password).strip():
            return True, "비밀번호 확인 완료"
        else:
            return False, "비밀번호가 일치하지 않습니다."
    
    def has_payment_password(self, member_id: str) -> bool:
        """결제 비밀번호 설정 여부 확인"""
        member = self.get_member(member_id)
        if not member:
            return False
        return bool(member.get('payment_password'))
    
    # =============================
    # 금액권 관련
    # =============================
    
    def get_voucher_product(self, product_id: str) -> Optional[Dict]:
        """금액권 상품 조회"""
        return self._voucher_products_cache.get(product_id)
    
    def get_member_vouchers(self, member_id: str, include_all: bool = False) -> List[Dict]:
        """
        회원의 금액권 목록 조회
        
        Args:
            member_id: 회원 ID
            include_all: True면 만료/소진 포함, False면 사용가능한 것만
        
        Returns:
            금액권 목록
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            if include_all:
                cursor.execute('''
                    SELECT mv.*, vp.name as product_name, vp.is_bonus
                    FROM member_vouchers mv
                    JOIN voucher_products vp ON mv.voucher_product_id = vp.product_id
                    WHERE mv.member_id = ?
                    ORDER BY mv.created_at DESC
                ''', (member_id,))
            else:
                cursor.execute('''
                    SELECT mv.*, vp.name as product_name, vp.is_bonus
                    FROM member_vouchers mv
                    JOIN voucher_products vp ON mv.voucher_product_id = vp.product_id
                    WHERE mv.member_id = ? 
                    AND mv.status IN ('active', 'pending')
                    ORDER BY mv.created_at DESC
                ''', (member_id,))
            
            vouchers = []
            now = get_kst_now()
            
            for row in cursor.fetchall():
                voucher = dict(row)
                
                # 유효기간 만료 체크 (조회 시점)
                if voucher['valid_until']:
                    valid_until = datetime.fromisoformat(voucher['valid_until'])
                    if valid_until.tzinfo is None:
                        valid_until = KST.localize(valid_until)
                    
                    if now > valid_until and voucher['status'] == 'active':
                        # 만료 처리
                        self._expire_voucher(voucher['voucher_id'])
                        voucher['status'] = 'expired'
                        
                        # 연결된 pending 보너스도 만료
                        self._expire_pending_bonus_vouchers(voucher['voucher_id'])
                
                vouchers.append(voucher)
            
            return vouchers
    
    def get_active_vouchers(self, member_id: str) -> List[Dict]:
        """
        회원의 활성 금액권만 조회 (사용 가능한 것)
        
        Returns:
            활성 금액권 목록 (잔액 있고, 기간 내, status='active')
        """
        vouchers = self.get_member_vouchers(member_id, include_all=False)
        return [v for v in vouchers if v['status'] == 'active' and v['remaining_amount'] > 0]
    
    def get_total_balance(self, member_id: str) -> int:
        """회원의 총 사용 가능 금액권 잔액"""
        active_vouchers = self.get_active_vouchers(member_id)
        return sum(v['remaining_amount'] for v in active_vouchers)
    
    def create_voucher(self, member_id: str, voucher_product_id: str,
                       parent_voucher_id: int = None) -> int:
        """
        금액권 생성
        
        Args:
            member_id: 회원 ID
            voucher_product_id: 금액권 상품 ID
            parent_voucher_id: 부모 금액권 ID (보너스인 경우)
        
        Returns:
            voucher_id
        """
        product = self.get_voucher_product(voucher_product_id)
        if not product:
            raise ValueError(f"금액권 상품을 찾을 수 없습니다: {voucher_product_id}")
        
        now = get_kst_now()
        
        # 보너스는 pending으로 시작, 일반은 active로 시작
        if product['is_bonus']:
            status = 'pending'
            valid_from = None
            valid_until = None
        else:
            status = 'active'
            valid_from = now.isoformat()
            valid_until = (now + timedelta(days=product['validity_days'])).isoformat()
        
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO member_vouchers 
                (member_id, voucher_product_id, original_amount, remaining_amount,
                 parent_voucher_id, valid_from, valid_until, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (member_id, voucher_product_id, product['charge_amount'], 
                  product['charge_amount'], parent_voucher_id,
                  valid_from, valid_until, status, now.isoformat(), now.isoformat()))
            
            voucher_id = cursor.lastrowid
            self.conn.commit()
            
            # 연결된 보너스 상품이 있으면 함께 생성
            if product.get('bonus_product_id') and not product['is_bonus']:
                self.create_voucher(member_id, product['bonus_product_id'], 
                                   parent_voucher_id=voucher_id)
            
            print(f"[LocalCache] 금액권 생성: #{voucher_id} ({product['name']}) - {member_id}")
            
            return voucher_id
    
    def deduct_voucher(self, voucher_id: int, amount: int, rental_log_id: int = None) -> Tuple[int, int]:
        """
        금액권에서 차감
        
        Args:
            voucher_id: 금액권 ID
            amount: 차감 금액
            rental_log_id: 대여 로그 ID (참조용)
        
        Returns:
            (차감 전 잔액, 차감 후 잔액)
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            # 현재 잔액 조회
            cursor.execute('SELECT * FROM member_vouchers WHERE voucher_id = ?', (voucher_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"금액권을 찾을 수 없습니다: {voucher_id}")
            
            voucher = dict(row)
            balance_before = voucher['remaining_amount']
            balance_after = balance_before - amount
            
            if balance_after < 0:
                raise ValueError(f"잔액 부족: {balance_before}원 (필요: {amount}원)")
            
            now = get_kst_now()
            
            # 잔액 업데이트
            new_status = 'exhausted' if balance_after == 0 else 'active'
            cursor.execute('''
                UPDATE member_vouchers 
                SET remaining_amount = ?, status = ?, updated_at = ?
                WHERE voucher_id = ?
            ''', (balance_after, new_status, now.isoformat(), voucher_id))
            
            # 거래 기록
            cursor.execute('''
                INSERT INTO voucher_transactions 
                (voucher_id, member_id, amount, balance_before, balance_after,
                 transaction_type, rental_log_id, created_at)
                VALUES (?, ?, ?, ?, ?, 'rental', ?, ?)
            ''', (voucher_id, voucher['member_id'], amount, balance_before, 
                  balance_after, rental_log_id, now.isoformat()))
            
            self.conn.commit()
            
            # 잔액 0이 되면 연결된 보너스 활성화
            if balance_after == 0:
                self._activate_bonus_vouchers(voucher_id)
            
            return balance_before, balance_after
    
    def _activate_bonus_vouchers(self, parent_voucher_id: int):
        """부모 금액권 소진 시 보너스 금액권 활성화"""
        cursor = self.conn.cursor()
        
        # pending 상태의 보너스 찾기
        cursor.execute('''
            SELECT mv.*, vp.validity_days
            FROM member_vouchers mv
            JOIN voucher_products vp ON mv.voucher_product_id = vp.product_id
            WHERE mv.parent_voucher_id = ? AND mv.status = 'pending'
        ''', (parent_voucher_id,))
        
        now = get_kst_now()
        
        for row in cursor.fetchall():
            bonus = dict(row)
            valid_from = now.isoformat()
            valid_until = (now + timedelta(days=bonus['validity_days'])).isoformat()
            
            cursor.execute('''
                UPDATE member_vouchers 
                SET status = 'active', valid_from = ?, valid_until = ?, updated_at = ?
                WHERE voucher_id = ?
            ''', (valid_from, valid_until, now.isoformat(), bonus['voucher_id']))
            
            print(f"[LocalCache] 보너스 활성화: #{bonus['voucher_id']}")
        
        self.conn.commit()
    
    def _expire_voucher(self, voucher_id: int):
        """금액권 만료 처리"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE member_vouchers SET status = 'expired', updated_at = ?
            WHERE voucher_id = ?
        ''', (get_kst_now().isoformat(), voucher_id))
        self.conn.commit()
    
    def _expire_pending_bonus_vouchers(self, parent_voucher_id: int):
        """부모 금액권 만료 시 pending 보너스도 만료"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE member_vouchers 
            SET status = 'expired', updated_at = ?
            WHERE parent_voucher_id = ? AND status = 'pending'
        ''', (get_kst_now().isoformat(), parent_voucher_id))
        self.conn.commit()
    
    # =============================
    # 구독권 관련
    # =============================
    
    def get_subscription_product(self, product_id: str) -> Optional[Dict]:
        """구독 상품 조회"""
        return self._subscription_products_cache.get(product_id)
    
    def get_member_subscriptions(self, member_id: str, include_all: bool = False) -> List[Dict]:
        """
        회원의 구독권 목록 조회
        
        Args:
            member_id: 회원 ID
            include_all: True면 만료 포함, False면 활성만
        
        Returns:
            구독권 목록
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            if include_all:
                cursor.execute('''
                    SELECT ms.*, sp.name as product_name
                    FROM member_subscriptions ms
                    JOIN subscription_products sp ON ms.subscription_product_id = sp.product_id
                    WHERE ms.member_id = ?
                    ORDER BY ms.created_at DESC
                ''', (member_id,))
            else:
                cursor.execute('''
                    SELECT ms.*, sp.name as product_name
                    FROM member_subscriptions ms
                    JOIN subscription_products sp ON ms.subscription_product_id = sp.product_id
                    WHERE ms.member_id = ? AND ms.status = 'active'
                    ORDER BY ms.created_at DESC
                ''', (member_id,))
            
            subscriptions = []
            now = get_kst_now()
            
            for row in cursor.fetchall():
                sub = dict(row)
                
                # JSON 파싱
                if sub.get('daily_limits') and isinstance(sub['daily_limits'], str):
                    sub['daily_limits'] = json.loads(sub['daily_limits'])
                
                # 유효기간 만료 체크 (조회 시점)
                if sub['valid_until']:
                    valid_until = datetime.fromisoformat(sub['valid_until'])
                    if valid_until.tzinfo is None:
                        valid_until = KST.localize(valid_until)
                    
                    if now > valid_until and sub['status'] == 'active':
                        self._expire_subscription(sub['subscription_id'])
                        sub['status'] = 'expired'
                
                subscriptions.append(sub)
            
            return subscriptions
    
    def get_active_subscriptions(self, member_id: str) -> List[Dict]:
        """회원의 활성 구독권만 조회"""
        subs = self.get_member_subscriptions(member_id, include_all=False)
        return [s for s in subs if s['status'] == 'active']
    
    def create_subscription(self, member_id: str, subscription_product_id: str,
                           valid_from: datetime = None) -> int:
        """
        구독권 생성
        
        Args:
            member_id: 회원 ID
            subscription_product_id: 구독 상품 ID
            valid_from: 시작일 (None이면 현재)
        
        Returns:
            subscription_id
        """
        product = self.get_subscription_product(subscription_product_id)
        if not product:
            raise ValueError(f"구독 상품을 찾을 수 없습니다: {subscription_product_id}")
        
        if valid_from is None:
            valid_from = get_kst_now()
        
        valid_until = valid_from + timedelta(days=product['validity_days'])
        
        # daily_limits를 JSON 문자열로
        daily_limits = product['daily_limits']
        if isinstance(daily_limits, dict):
            daily_limits = json.dumps(daily_limits)
        
        now = get_kst_now()
        
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO member_subscriptions 
                (member_id, subscription_product_id, valid_from, valid_until,
                 daily_limits, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            ''', (member_id, subscription_product_id, valid_from.isoformat(),
                  valid_until.isoformat(), daily_limits, now.isoformat(), now.isoformat()))
            
            subscription_id = cursor.lastrowid
            self.conn.commit()
            
            print(f"[LocalCache] 구독권 생성: #{subscription_id} ({product['name']}) - {member_id}")
            
            return subscription_id
    
    def _expire_subscription(self, subscription_id: int):
        """구독권 만료 처리"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE member_subscriptions SET status = 'expired', updated_at = ?
            WHERE subscription_id = ?
        ''', (get_kst_now().isoformat(), subscription_id))
        self.conn.commit()
    
    def get_subscription_remaining(self, subscription_id: int, category: str) -> int:
        """
        구독권의 오늘 남은 횟수 조회
        
        Args:
            subscription_id: 구독권 ID
            category: 카테고리 (top, pants, towel 등)
        
        Returns:
            남은 횟수
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            # 구독권 정보
            cursor.execute('SELECT daily_limits FROM member_subscriptions WHERE subscription_id = ?',
                          (subscription_id,))
            row = cursor.fetchone()
            if not row:
                return 0
            
            daily_limits = json.loads(row['daily_limits']) if isinstance(row['daily_limits'], str) else row['daily_limits']
            daily_limit = daily_limits.get(category, 0)
            
            # 오늘 사용량
            today = get_kst_today().isoformat()
            cursor.execute('''
                SELECT used_count FROM subscription_usage
                WHERE subscription_id = ? AND usage_date = ? AND category = ?
            ''', (subscription_id, today, category))
            
            usage_row = cursor.fetchone()
            used = usage_row['used_count'] if usage_row else 0
            
            return max(0, daily_limit - used)
    
    def use_subscription(self, subscription_id: int, category: str, count: int = 1) -> bool:
        """
        구독권 사용 (일일 사용량 증가)
        
        Args:
            subscription_id: 구독권 ID
            category: 카테고리
            count: 사용 횟수
        
        Returns:
            성공 여부
        """
        remaining = self.get_subscription_remaining(subscription_id, category)
        if remaining < count:
            return False
        
        today = get_kst_today().isoformat()
        
        with self.lock:
            cursor = self.conn.cursor()
            
            # UPSERT
            cursor.execute('''
                INSERT INTO subscription_usage (subscription_id, usage_date, category, used_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(subscription_id, usage_date, category) 
                DO UPDATE SET used_count = used_count + ?
            ''', (subscription_id, today, category, count, count))
            
            self.conn.commit()
            
            return True
    
    # =============================
    # 락카 매핑
    # =============================
    
    def assign_locker(self, locker_number: int, member_id: str) -> bool:
        """락카 배정"""
        with self.lock:
            if member_id not in self._members_cache:
                raise ValueError(f"회원을 찾을 수 없습니다: {member_id}")
            
            self._locker_cache[locker_number] = member_id
            
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO locker_mapping 
                (locker_number, member_id, assigned_at)
                VALUES (?, ?, ?)
            ''', (locker_number, member_id, get_kst_now().isoformat()))
            
            self.conn.commit()
            print(f"[LocalCache] 락카 배정: {locker_number}번 → {member_id}")
            
            return True
    
    def get_member_by_locker(self, locker_number: int) -> Optional[str]:
        """락카 번호로 회원 ID 조회"""
        return self._locker_cache.get(locker_number)
    
    def release_locker(self, locker_number: int) -> bool:
        """락카 해제"""
        with self.lock:
            if locker_number not in self._locker_cache:
                return False
            
            del self._locker_cache[locker_number]
            
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM locker_mapping WHERE locker_number = ?', (locker_number,))
            self.conn.commit()
            
            return True
    
    def get_locker_info(self, locker_number: int) -> Optional[Dict]:
        """락카 배정 정보 조회"""
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
        """모든 배정된 락카 목록 조회"""
        return dict(self._locker_cache)
    
    # =============================
    # 상품 관련
    # =============================
    
    def get_products(self, gym_id: str = 'GYM001', enabled_only: bool = True) -> List[Dict]:
        """상품 목록 조회"""
        products = [
            p for p in self._products_cache.values()
            if p['gym_id'] == gym_id and (not enabled_only or p['enabled'])
        ]
        return sorted(products, key=lambda x: x.get('display_order', 0))
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """상품 정보 조회"""
        return self._products_cache.get(product_id)
    
    def update_product_stock(self, product_id: str, stock: int) -> bool:
        """상품 재고 업데이트"""
        with self.lock:
            product = self._products_cache.get(product_id)
            if not product:
                return False
            
            product['stock'] = stock
            product['updated_at'] = get_kst_now().isoformat()
            
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE products SET stock = ?, updated_at = ? WHERE product_id = ?
            ''', (stock, product['updated_at'], product_id))
            
            self.conn.commit()
            return True
    
    # =============================
    # 기기 레지스트리
    # =============================
    
    def register_device(self, device_uuid: str, mac_address: str, 
                       size: str = '', category: str = '', 
                       device_name: str = '', ip_address: str = '', 
                       firmware_version: str = '', stock: int = 0) -> Dict:
        """새 기기 등록 또는 업데이트 + products 테이블에도 자동 생성"""
        with self.lock:
            now = get_kst_now().isoformat()
            cursor = self.conn.cursor()
            
            existing = self._device_registry.get(device_uuid)
            
            if existing:
                cursor.execute('''
                    UPDATE device_registry 
                    SET size = ?, category = ?, device_name = ?,
                        ip_address = ?, firmware_version = ?, 
                        last_seen_at = ?, updated_at = ?
                    WHERE device_uuid = ?
                ''', (size, category, device_name, ip_address, firmware_version, 
                      now, now, device_uuid))
                
                existing.update({
                    'size': size, 'category': category, 'device_name': device_name,
                    'ip_address': ip_address, 'firmware_version': firmware_version,
                    'last_seen_at': now, 'updated_at': now
                })
                device_info = existing
            else:
                cursor.execute('''
                    INSERT INTO device_registry 
                    (device_uuid, mac_address, size, category, device_name,
                     ip_address, firmware_version, first_seen_at, last_seen_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (device_uuid, mac_address, size, category, device_name,
                      ip_address, firmware_version, now, now, now))
                
                device_info = {
                    'device_uuid': device_uuid, 'mac_address': mac_address,
                    'device_name': device_name, 'size': size, 'category': category,
                    'product_id': None, 'ip_address': ip_address,
                    'firmware_version': firmware_version,
                    'first_seen_at': now, 'last_seen_at': now, 'updated_at': now
                }
                self._device_registry[device_uuid] = device_info
                print(f"[LocalCache] ✅ 새 기기 등록: {device_uuid}")
            
            self.conn.commit()
            
            # products 테이블에도 생성/업데이트
            if category and size:
                product_id = self._create_or_update_product(
                    device_uuid=device_uuid, category=category,
                    size=size, name=device_name, stock=stock
                )
                device_info['product_id'] = product_id
                
                cursor.execute('UPDATE device_registry SET product_id = ? WHERE device_uuid = ?',
                              (product_id, device_uuid))
                self.conn.commit()
            
            return device_info
    
    def _create_or_update_product(self, device_uuid: str, category: str, 
                                   size: str, name: str, stock: int = 0,
                                   price: int = 1000) -> str:
        """products 테이블에 상품 생성 또는 업데이트"""
        now = get_kst_now().isoformat()
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT product_id, price FROM products WHERE device_uuid = ?', (device_uuid,))
        row = cursor.fetchone()
        
        if row:
            product_id = row[0]
            existing_price = row[1] or 1000
            cursor.execute('''
                UPDATE products 
                SET category = ?, size = ?, name = ?, stock = ?, updated_at = ?
                WHERE device_uuid = ?
            ''', (category, size, name, stock, now, device_uuid))
            
            # 캐시 업데이트
            if product_id in self._products_cache:
                self._products_cache[product_id].update({
                    'category': category, 'size': size, 'name': name,
                    'stock': stock, 'updated_at': now
                })
        else:
            category_upper = category.upper()
            product_id = f"P-{category_upper}-{size}"
            
            cursor.execute('SELECT 1 FROM products WHERE product_id = ?', (product_id,))
            if cursor.fetchone():
                product_id = f"P-{category_upper}-{size}-{device_uuid[-4:]}"
            
            cursor.execute('''
                INSERT INTO products 
                (product_id, gym_id, category, size, name, price, device_uuid, 
                 stock, enabled, display_order, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, 'GYM001', category, size, name, price, device_uuid, 
                  stock, 1, 0, now))
            
            self._products_cache[product_id] = {
                'product_id': product_id, 'gym_id': 'GYM001',
                'category': category, 'size': size, 'name': name,
                'price': price, 'device_uuid': device_uuid,
                'stock': stock, 'enabled': True, 'display_order': 0, 'updated_at': now
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
    
    def get_device(self, device_uuid: str) -> Optional[Dict]:
        """기기 상태 조회"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM device_cache WHERE device_uuid = ?', (device_uuid,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_devices(self) -> List[Dict]:
        """모든 기기 상태 조회"""
        return list(self._device_cache.values())
    
    def update_device_status(self, device_uuid: str, **kwargs) -> bool:
        """기기 상태 업데이트"""
        with self.lock:
            device = self._device_cache.get(device_uuid)
            if device is None:
                device = {
                    'device_uuid': device_uuid, 'size': kwargs.get('size', ''),
                    'stock': 0, 'door_state': 'closed', 'floor_state': 'reached',
                    'locked': False, 'wifi_rssi': None, 'last_heartbeat': None,
                    'updated_at': get_kst_now().isoformat()
                }
                self._device_cache[device_uuid] = device
            
            for key, value in kwargs.items():
                device[key] = value
            device['updated_at'] = get_kst_now().isoformat()
            
            cursor = self.conn.cursor()
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
        """기기 하트비트 업데이트"""
        kwargs = {'last_heartbeat': get_kst_now().isoformat()}
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
    
    def add_rental_log(self, member_id: str, product_id: str, device_uuid: str,
                      quantity: int, payment_type: str, 
                      subscription_id: int = None, amount: int = 0,
                      locker_number: int = None, product_name: str = None) -> int:
        """
        대여 로그 추가 (금액권/구독권 기반)
        
        Args:
            member_id: 회원 ID
            product_id: 상품 ID
            device_uuid: 기기 UUID
            quantity: 대여 수량
            payment_type: 결제 유형 ('voucher', 'subscription')
            subscription_id: 구독권 ID (구독권 사용 시)
            amount: 차감 금액 (구독권이면 0)
            locker_number: 락카 번호
            product_name: 상품명
        
        Returns:
            rental_id
        """
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO rental_logs 
                (member_id, locker_number, product_id, product_name, device_uuid,
                 quantity, payment_type, subscription_id, amount, created_at, synced_to_sheets)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (member_id, locker_number, product_id, product_name, device_uuid,
                  quantity, payment_type, subscription_id, amount, get_kst_now().isoformat()))
            
            rental_id = cursor.lastrowid
            self.conn.commit()
            
            return rental_id
    
    def get_unsynced_rentals(self) -> List[Dict]:
        """동기화되지 않은 대여 로그 조회"""
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
                UPDATE rental_logs SET synced_to_sheets = 1 WHERE id IN ({placeholders})
            ''', rental_ids)
            self.conn.commit()
    
    def get_unsynced_voucher_transactions(self) -> List[Dict]:
        """동기화되지 않은 금액권 거래 조회"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM voucher_transactions 
                WHERE synced_to_sheets = 0 
                ORDER BY created_at
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_voucher_transactions_synced(self, transaction_ids: List[int]):
        """금액권 거래를 동기화 완료로 표시"""
        if not transaction_ids:
            return
        
        with self.lock:
            cursor = self.conn.cursor()
            placeholders = ', '.join(['?' for _ in transaction_ids])
            cursor.execute(f'''
                UPDATE voucher_transactions SET synced_to_sheets = 1 WHERE id IN ({placeholders})
            ''', transaction_ids)
            self.conn.commit()
    
    # =============================
    # MQTT 이벤트 로깅
    # =============================
    
    def log_mqtt_event(self, device_id: str, event_type: str, payload: dict) -> int:
        """MQTT 이벤트 DB 로깅"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO mqtt_events (device_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
            ''', (device_id, event_type, json.dumps(payload), get_kst_now().isoformat()))
            
            event_id = cursor.lastrowid
            self.conn.commit()
            return event_id
    
    def get_recent_events(self, device_id: str = None, limit: int = 50) -> List[Dict]:
        """최근 MQTT 이벤트 조회"""
        with self.lock:
            cursor = self.conn.cursor()
            
            if device_id:
                cursor.execute('''
                    SELECT * FROM mqtt_events 
                    WHERE device_id = ?
                    ORDER BY created_at DESC LIMIT ?
                ''', (device_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM mqtt_events 
                    ORDER BY created_at DESC LIMIT ?
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
        """회원 정보 재로드"""
        with self.lock:
            self._members_cache.clear()
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM members')
            for row in cursor.fetchall():
                self._members_cache[row['member_id']] = dict(row)
            print(f"[LocalCache] 회원 정보 재로드: {len(self._members_cache)}명")
    
    def reload_products(self):
        """상품 정보 재로드"""
        with self.lock:
            self._products_cache.clear()
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM products WHERE enabled = 1')
            for row in cursor.fetchall():
                self._products_cache[row['product_id']] = dict(row)
            print(f"[LocalCache] 상품 정보 재로드: {len(self._products_cache)}개")
    
    def reload_voucher_products(self):
        """금액권 상품 재로드"""
        with self.lock:
            self._voucher_products_cache.clear()
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM voucher_products WHERE enabled = 1')
            for row in cursor.fetchall():
                self._voucher_products_cache[row['product_id']] = dict(row)
            print(f"[LocalCache] 금액권 상품 재로드: {len(self._voucher_products_cache)}개")
    
    def reload_subscription_products(self):
        """구독 상품 재로드"""
        with self.lock:
            self._subscription_products_cache.clear()
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM subscription_products WHERE enabled = 1')
            for row in cursor.fetchall():
                product = dict(row)
                if product.get('daily_limits'):
                    product['daily_limits'] = json.loads(product['daily_limits'])
                self._subscription_products_cache[row['product_id']] = product
            print(f"[LocalCache] 구독 상품 재로드: {len(self._subscription_products_cache)}개")
    
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
