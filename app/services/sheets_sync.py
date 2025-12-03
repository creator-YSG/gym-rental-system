"""
Google Sheets 동기화 서비스 (금액권/구독권 기반)

Google Sheets ↔ SQLite 간 데이터 동기화
- 다운로드: 회원 정보, 상품 목록, 금액권/구독권 상품, 회원 금액권/구독권
- 업로드: 대여 이력, 금액권 거래, 기기 상태
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import List, Dict, Optional
import time
import json


class SheetsSync:
    """Google Sheets 동기화 클래스"""
    
    def __init__(self, credentials_path: str, spreadsheet_name: str = 'F-BOX-DB-TEST'):
        """
        초기화
        
        Args:
            credentials_path: Google 서비스 계정 JSON 키 파일 경로
            spreadsheet_name: 스프레드시트 이름
        """
        self.credentials_path = credentials_path
        self.spreadsheet_name = spreadsheet_name
        
        self.client = None
        self.spreadsheet = None
        
        # API 호출 제한 관리
        self.last_api_call = 0
        self.min_interval = 1.0  # 최소 1초 간격
        
        print(f"[Sheets] 초기화: {spreadsheet_name}")
    
    def connect(self) -> bool:
        """Google Sheets API 연결"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_path, scope
            )
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open(self.spreadsheet_name)
            
            print(f"[Sheets] ✓ 연결 성공: {self.spreadsheet_name}")
            return True
            
        except Exception as e:
            print(f"[Sheets] ✗ 연결 실패: {e}")
            return False
    
    def _rate_limit(self):
        """API 호출 제한 관리"""
        now = time.time()
        elapsed = now - self.last_api_call
        
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        self.last_api_call = time.time()
    
    def _get_or_create_sheet(self, sheet_name: str, headers: List[str]) -> gspread.Worksheet:
        """시트 가져오기 (없으면 생성)"""
        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
            sheet.append_row(headers)
            sheet.format(f'A1:{chr(64 + len(headers))}1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
        return sheet
    
    # =============================
    # 다운로드 (Sheets → SQLite)
    # =============================
    
    def download_config(self) -> dict:
        """설정 정보 다운로드"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('config')
            records = sheet.get_all_records()
            
            config = {}
            for record in records:
                key = record.get('key')
                value = record.get('value')
                if key:
                    try:
                        if '.' in str(value):
                            config[key] = float(value)
                        else:
                            config[key] = int(value)
                    except (ValueError, TypeError):
                        config[key] = value
            
            print(f"[Sheets] 설정 다운로드 완료: {len(config)}개")
            return config
            
        except Exception as e:
            print(f"[Sheets] 설정 다운로드 오류: {e}")
            return {}
    
    def download_members(self, local_cache) -> int:
        """회원 정보 다운로드 (금액권/구독권 기반 - 잔여 횟수 없음)"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('members')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                phone = record.get('phone', '')
                if phone:
                    phone = str(phone).replace('-', '').replace(' ', '')
                
                cursor.execute('''
                    INSERT OR REPLACE INTO members 
                    (member_id, name, phone, status, synced_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    record.get('member_id'),
                    record.get('name'),
                    phone,
                    record.get('status', 'active'),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            local_cache.reload_members()
            
            print(f"[Sheets] 회원 정보 다운로드 완료: {count}명")
            return count
            
        except Exception as e:
            print(f"[Sheets] 회원 다운로드 오류: {e}")
            return 0
    
    def download_products(self, local_cache) -> int:
        """상품 정보 다운로드 (가격 포함)"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('products')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                device_uuid = record.get('device_uuid', '')
                if not device_uuid:
                    continue
                
                price = record.get('price', 1000)
                try:
                    price = int(price)
                except (ValueError, TypeError):
                    price = 1000
                
                cursor.execute('''
                    INSERT OR REPLACE INTO products 
                    (product_id, gym_id, category, size, name, price, device_uuid, 
                     stock, enabled, display_order, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.get('product_id'),
                    record.get('gym_id', 'GYM001'),
                    record.get('category'),
                    record.get('size', ''),
                    record.get('name'),
                    price,
                    device_uuid,
                    record.get('stock', 0),
                    1 if record.get('enabled') == 'TRUE' else 0,
                    record.get('display_order', 0),
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            local_cache.reload_products()
            
            print(f"[Sheets] 상품 정보 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            print(f"[Sheets] 상품 다운로드 오류: {e}")
            return 0
    
    def download_voucher_products(self, local_cache) -> int:
        """금액권 상품 다운로드"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('voucher_products')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                cursor.execute('''
                    INSERT OR REPLACE INTO voucher_products 
                    (product_id, name, price, charge_amount, validity_days,
                     bonus_product_id, is_bonus, enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.get('product_id'),
                    record.get('name'),
                    int(record.get('price', 0)),
                    int(record.get('charge_amount', 0)),
                    int(record.get('validity_days', 365)),
                    record.get('bonus_product_id') or None,
                    1 if record.get('is_bonus') in ('TRUE', True, 1) else 0,
                    1 if record.get('enabled') in ('TRUE', True, 1) else 0,
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            local_cache.reload_voucher_products()
            
            print(f"[Sheets] 금액권 상품 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            print(f"[Sheets] 금액권 상품 다운로드 오류: {e}")
            return 0
    
    def download_subscription_products(self, local_cache) -> int:
        """구독 상품 다운로드"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('subscription_products')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                daily_limits = record.get('daily_limits', '{}')
                if isinstance(daily_limits, str):
                    try:
                        json.loads(daily_limits)
                    except:
                        daily_limits = '{}'
                else:
                    daily_limits = json.dumps(daily_limits)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO subscription_products 
                    (product_id, name, price, validity_days, daily_limits, enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.get('product_id'),
                    record.get('name'),
                    int(record.get('price', 0)),
                    int(record.get('validity_days', 30)),
                    daily_limits,
                    1 if record.get('enabled') in ('TRUE', True, 1) else 0,
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            local_cache.reload_subscription_products()
            
            print(f"[Sheets] 구독 상품 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            print(f"[Sheets] 구독 상품 다운로드 오류: {e}")
            return 0
    
    def download_member_vouchers(self, local_cache) -> int:
        """회원 금액권 다운로드"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('member_vouchers')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                cursor.execute('''
                    INSERT OR REPLACE INTO member_vouchers 
                    (voucher_id, member_id, voucher_product_id, original_amount, remaining_amount,
                     parent_voucher_id, valid_from, valid_until, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(record.get('voucher_id')),
                    record.get('member_id'),
                    record.get('voucher_product_id'),
                    int(record.get('original_amount', 0)),
                    int(record.get('remaining_amount', 0)),
                    int(record.get('parent_voucher_id')) if record.get('parent_voucher_id') else None,
                    record.get('valid_from') or None,
                    record.get('valid_until') or None,
                    record.get('status', 'active'),
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            print(f"[Sheets] 회원 금액권 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            print(f"[Sheets] 회원 금액권 다운로드 오류: {e}")
            return 0
    
    def download_member_subscriptions(self, local_cache) -> int:
        """회원 구독권 다운로드"""
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('member_subscriptions')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                daily_limits = record.get('daily_limits', '{}')
                if isinstance(daily_limits, str):
                    try:
                        json.loads(daily_limits)
                    except:
                        daily_limits = '{}'
                else:
                    daily_limits = json.dumps(daily_limits)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO member_subscriptions 
                    (subscription_id, member_id, subscription_product_id, 
                     valid_from, valid_until, daily_limits, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(record.get('subscription_id')),
                    record.get('member_id'),
                    record.get('subscription_product_id'),
                    record.get('valid_from'),
                    record.get('valid_until'),
                    daily_limits,
                    record.get('status', 'active'),
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            print(f"[Sheets] 회원 구독권 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            print(f"[Sheets] 회원 구독권 다운로드 오류: {e}")
            return 0
    
    # =============================
    # 업로드 (SQLite → Sheets)
    # =============================
    
    def upload_rentals(self, local_cache) -> int:
        """대여 이력 업로드 (금액권/구독권 기반)"""
        try:
            rentals = local_cache.get_unsynced_rentals()
            
            if not rentals:
                return 0
            
            self._rate_limit()
            
            headers = ['rental_id', 'member_id', 'locker_number', 'product_id', 'product_name',
                      'device_uuid', 'quantity', 'payment_type', 'subscription_id', 'amount', 'created_at']
            sheet = self._get_or_create_sheet('rental_history', headers)
            
            rows = []
            rental_ids = []
            
            for rental in rentals:
                rows.append([
                    rental['id'],
                    rental['member_id'],
                    rental.get('locker_number', ''),
                    rental['product_id'],
                    rental.get('product_name', ''),
                    rental.get('device_uuid', ''),
                    rental['quantity'],
                    rental['payment_type'],
                    rental.get('subscription_id', ''),
                    rental.get('amount', 0),
                    rental['created_at']
                ])
                rental_ids.append(rental['id'])
            
            sheet.append_rows(rows)
            local_cache.mark_rentals_synced(rental_ids)
            
            print(f"[Sheets] 대여 이력 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            print(f"[Sheets] 대여 업로드 오류: {e}")
            return 0
    
    def upload_voucher_transactions(self, local_cache) -> int:
        """금액권 거래 내역 업로드"""
        try:
            transactions = local_cache.get_unsynced_voucher_transactions()
            
            if not transactions:
                return 0
            
            self._rate_limit()
            
            headers = ['id', 'voucher_id', 'member_id', 'amount', 'balance_before',
                      'balance_after', 'transaction_type', 'rental_log_id', 'created_at']
            sheet = self._get_or_create_sheet('voucher_transactions', headers)
            
            rows = []
            transaction_ids = []
            
            for tx in transactions:
                rows.append([
                    tx['id'],
                    tx['voucher_id'],
                    tx['member_id'],
                    tx['amount'],
                    tx['balance_before'],
                    tx['balance_after'],
                    tx['transaction_type'],
                    tx.get('rental_log_id', ''),
                    tx['created_at']
                ])
                transaction_ids.append(tx['id'])
            
            sheet.append_rows(rows)
            local_cache.mark_voucher_transactions_synced(transaction_ids)
            
            print(f"[Sheets] 금액권 거래 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            print(f"[Sheets] 금액권 거래 업로드 오류: {e}")
            return 0
    
    def upload_member_vouchers(self, local_cache) -> int:
        """회원 금액권 전체 업로드 (상태 동기화)"""
        try:
            conn = local_cache.conn
            cursor = conn.cursor()
            cursor.execute('''
                SELECT voucher_id, member_id, voucher_product_id, original_amount, remaining_amount,
                       parent_voucher_id, valid_from, valid_until, status, created_at, updated_at
                FROM member_vouchers
                ORDER BY member_id, created_at
            ''')
            vouchers = cursor.fetchall()
            
            if not vouchers:
                return 0
            
            self._rate_limit()
            
            headers = ['voucher_id', 'member_id', 'voucher_product_id', 'original_amount', 'remaining_amount',
                      'parent_voucher_id', 'valid_from', 'valid_until', 'status', 'created_at', 'updated_at']
            sheet = self._get_or_create_sheet('member_vouchers', headers)
            
            sheet.clear()
            rows = [headers]
            
            for v in vouchers:
                rows.append([
                    v[0],  # voucher_id
                    v[1],  # member_id
                    v[2],  # voucher_product_id
                    v[3],  # original_amount
                    v[4],  # remaining_amount
                    v[5] or '',  # parent_voucher_id
                    v[6] or '',  # valid_from
                    v[7] or '',  # valid_until
                    v[8],  # status
                    v[9] or '',  # created_at
                    v[10] or ''  # updated_at
                ])
            
            sheet.update('A1', rows)
            sheet.format(f'A1:{chr(64 + len(headers))}1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"[Sheets] 회원 금액권 업로드 완료: {len(vouchers)}개")
            return len(vouchers)
            
        except Exception as e:
            print(f"[Sheets] 회원 금액권 업로드 오류: {e}")
            return 0
    
    def upload_member_subscriptions(self, local_cache) -> int:
        """회원 구독권 전체 업로드"""
        try:
            conn = local_cache.conn
            cursor = conn.cursor()
            cursor.execute('''
                SELECT subscription_id, member_id, subscription_product_id,
                       valid_from, valid_until, daily_limits, status, created_at, updated_at
                FROM member_subscriptions
                ORDER BY member_id, created_at
            ''')
            subscriptions = cursor.fetchall()
            
            if not subscriptions:
                return 0
            
            self._rate_limit()
            
            headers = ['subscription_id', 'member_id', 'subscription_product_id',
                      'valid_from', 'valid_until', 'daily_limits', 'status', 'created_at', 'updated_at']
            sheet = self._get_or_create_sheet('member_subscriptions', headers)
            
            sheet.clear()
            rows = [headers]
            
            for s in subscriptions:
                rows.append([
                    s[0],  # subscription_id
                    s[1],  # member_id
                    s[2],  # subscription_product_id
                    s[3] or '',  # valid_from
                    s[4] or '',  # valid_until
                    s[5],  # daily_limits
                    s[6],  # status
                    s[7] or '',  # created_at
                    s[8] or ''  # updated_at
                ])
            
            sheet.update('A1', rows)
            sheet.format(f'A1:{chr(64 + len(headers))}1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"[Sheets] 회원 구독권 업로드 완료: {len(subscriptions)}개")
            return len(subscriptions)
            
        except Exception as e:
            print(f"[Sheets] 회원 구독권 업로드 오류: {e}")
            return 0
    
    def update_device_status(self, local_cache) -> int:
        """기기 상태 업데이트"""
        try:
            devices = local_cache.get_all_devices()
            registry = {d['device_uuid']: d for d in local_cache.get_all_registered_devices()}
            
            if not devices and not registry:
                return 0
            
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('device_status')
            sheet.clear()
            
            headers = ['device_uuid', 'mac_address', 'device_name', 'category',
                      'size', 'stock', 'status', 'wifi_rssi',
                      'last_heartbeat', 'ip_address', 'firmware_version',
                      'first_seen_at', 'updated_at']
            rows = [headers]
            
            all_uuids = set(d.get('device_uuid') for d in devices) | set(registry.keys())
            
            for device_uuid in all_uuids:
                cache = next((d for d in devices if d.get('device_uuid') == device_uuid), {})
                reg = registry.get(device_uuid, {})
                
                last_heartbeat = cache.get('last_heartbeat')
                if last_heartbeat:
                    try:
                        heartbeat_time = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
                        if heartbeat_time.tzinfo:
                            heartbeat_time = heartbeat_time.replace(tzinfo=None)
                        diff = (datetime.now() - heartbeat_time).total_seconds()
                        status = 'online' if diff < 120 else 'offline'
                    except:
                        status = 'offline'
                else:
                    status = 'offline'
                
                rows.append([
                    device_uuid,
                    reg.get('mac_address', ''),
                    reg.get('device_name', ''),
                    reg.get('category', ''),
                    cache.get('size') or reg.get('size', ''),
                    cache.get('stock', 0),
                    status,
                    cache.get('wifi_rssi', ''),
                    last_heartbeat or '',
                    reg.get('ip_address', ''),
                    reg.get('firmware_version', ''),
                    reg.get('first_seen_at', ''),
                    cache.get('updated_at') or reg.get('updated_at', '')
                ])
            
            sheet.update('A1', rows)
            sheet.format('A1:M1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"[Sheets] 기기 상태 업데이트 완료: {len(rows) - 1}개")
            return len(rows) - 1
            
        except Exception as e:
            print(f"[Sheets] 기기 상태 업데이트 오류: {e}")
            return 0
    
    def upload_products(self, local_cache) -> int:
        """상품 정보 업로드 (가격 포함)"""
        try:
            conn = local_cache.conn
            cursor = conn.cursor()
            cursor.execute('''
                SELECT product_id, gym_id, category, size, name, price,
                       device_uuid, stock, enabled, display_order, updated_at
                FROM products
                ORDER BY display_order, product_id
            ''')
            products = cursor.fetchall()
            
            if not products:
                return 0
            
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('products')
            sheet.clear()
            
            headers = ['product_id', 'gym_id', 'category', 'size', 'name', 'price',
                      'device_uuid', 'stock', 'enabled', 'display_order', 'updated_at']
            rows = [headers]
            
            for p in products:
                rows.append([
                    p[0],  # product_id
                    p[1],  # gym_id
                    p[2],  # category
                    p[3],  # size
                    p[4],  # name
                    p[5] or 1000,  # price
                    p[6] or '',  # device_uuid
                    p[7],  # stock
                    'TRUE' if p[8] else 'FALSE',  # enabled
                    p[9],  # display_order
                    p[10] or ''  # updated_at
                ])
            
            sheet.update('A1', rows)
            sheet.format('A1:K1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"[Sheets] 상품 정보 업로드 완료: {len(products)}개")
            return len(products)
            
        except Exception as e:
            print(f"[Sheets] 상품 업로드 오류: {e}")
            return 0
    
    def upload_event_logs(self, local_cache, limit: int = 100) -> int:
        """비즈니스 이벤트 로그 업로드"""
        try:
            conn = local_cache.conn
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, event_type, severity, device_uuid, member_id, 
                       product_id, details, created_at
                FROM event_logs 
                WHERE synced_to_sheets = 0 
                ORDER BY created_at
                LIMIT ?
            ''', (limit,))
            
            events = cursor.fetchall()
            
            if not events:
                return 0
            
            self._rate_limit()
            
            headers = ['log_id', 'timestamp', 'event_type', 'severity', 
                      'device_uuid', 'member_id', 'product_id', 'details']
            sheet = self._get_or_create_sheet('event_logs', headers)
            
            rows = []
            event_ids = []
            
            for event in events:
                event_id, event_type, severity, device_uuid, member_id, product_id, details, created_at = event
                rows.append([
                    event_id,
                    created_at,
                    event_type,
                    severity,
                    device_uuid or '',
                    member_id or '',
                    product_id or '',
                    details or ''
                ])
                event_ids.append(event_id)
            
            sheet.append_rows(rows)
            
            placeholders = ', '.join(['?' for _ in event_ids])
            cursor.execute(f'''
                UPDATE event_logs 
                SET synced_to_sheets = 1 
                WHERE id IN ({placeholders})
            ''', event_ids)
            conn.commit()
            
            print(f"[Sheets] 이벤트 로그 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            print(f"[Sheets] 이벤트 로그 업로드 오류: {e}")
            return 0
    
    # =============================
    # 배치 동기화
    # =============================
    
    def sync_all_downloads(self, local_cache) -> Dict[str, int]:
        """모든 다운로드 동기화 실행"""
        result = {
            'members': self.download_members(local_cache),
            'products': self.download_products(local_cache),
            'voucher_products': self.download_voucher_products(local_cache),
            'subscription_products': self.download_subscription_products(local_cache),
            'member_vouchers': self.download_member_vouchers(local_cache),
            'member_subscriptions': self.download_member_subscriptions(local_cache),
        }
        return result
    
    def sync_all_uploads(self, local_cache) -> Dict[str, int]:
        """모든 업로드 동기화 실행"""
        result = {
            'rentals': self.upload_rentals(local_cache),
            'voucher_transactions': self.upload_voucher_transactions(local_cache),
            'devices': self.update_device_status(local_cache),
        }
        return result


# =============================
# 동기화 스케줄러
# =============================

class SyncScheduler:
    """동기화 스케줄러"""
    
    def __init__(self, sheets_sync: SheetsSync, local_cache, 
                 download_interval: int = 300,  # 5분
                 upload_interval: int = 5):     # 5초
        self.sheets_sync = sheets_sync
        self.local_cache = local_cache
        self.download_interval = download_interval
        self.upload_interval = upload_interval
        
        self.running = False
        self.last_download = 0
        self.last_upload = 0
    
    def start(self):
        """스케줄러 시작"""
        self.running = True
        print(f"[SyncScheduler] 시작 (다운로드: {self.download_interval}초, 업로드: {self.upload_interval}초)")
    
    def stop(self):
        """스케줄러 중지"""
        self.running = False
        print("[SyncScheduler] 중지")
    
    def tick(self):
        """스케줄러 틱 (메인 루프에서 호출)"""
        if not self.running:
            return
        
        now = time.time()
        
        # 다운로드 주기 확인
        if now - self.last_download >= self.download_interval:
            print("[SyncScheduler] 다운로드 동기화 시작...")
            result = self.sheets_sync.sync_all_downloads(self.local_cache)
            print(f"[SyncScheduler] 다운로드 완료: {result}")
            self.last_download = now
        
        # 업로드 주기 확인
        if now - self.last_upload >= self.upload_interval:
            result = self.sheets_sync.sync_all_uploads(self.local_cache)
            if any(result.values()):
                print(f"[SyncScheduler] 업로드 완료: {result}")
            self.last_upload = now


if __name__ == '__main__':
    from local_cache import LocalCache
    
    cache = LocalCache()
    sync = SheetsSync(
        credentials_path='config/credentials.json',
        spreadsheet_name='F-BOX-DB-TEST'
    )
    
    if sync.connect():
        sync.download_members(cache)
        sync.download_products(cache)
        sync.upload_rentals(cache)
        sync.update_device_status(cache)
