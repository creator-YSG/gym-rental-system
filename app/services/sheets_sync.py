"""
Google Sheets 동기화 서비스 (횟수 기반)

Google Sheets ↔ SQLite 간 데이터 동기화
- 다운로드: 회원 정보, 상품 목록
- 업로드: 대여 이력, 횟수 변동, 기기 상태
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import List, Dict, Optional
import time


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
        """
        Google Sheets API 연결
        
        Returns:
            성공 여부
        """
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
        """API 호출 제한 관리 (분당 60회 제한)"""
        now = time.time()
        elapsed = now - self.last_api_call
        
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        self.last_api_call = time.time()
    
    # =============================
    # 다운로드 (Sheets → SQLite)
    # =============================
    
    def download_members(self, local_cache) -> int:
        """
        회원 정보 다운로드
        
        Args:
            local_cache: LocalCache 인스턴스
        
        Returns:
            동기화된 회원 수
        """
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('members')
            records = sheet.get_all_records()
            
            count = 0
            conn = local_cache.conn
            cursor = conn.cursor()
            
            for record in records:
                cursor.execute('''
                    INSERT OR REPLACE INTO members 
                    (member_id, name, remaining_count, total_charged, total_used, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    record.get('member_id'),
                    record.get('name'),
                    record.get('remaining_count', 0),
                    record.get('total_charged', 0),
                    record.get('total_used', 0),
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            local_cache.reload_members()  # 메모리 캐시 재로드
            
            print(f"[Sheets] 회원 정보 다운로드 완료: {count}명")
            return count
            
        except Exception as e:
            print(f"[Sheets] 회원 다운로드 오류: {e}")
            return 0
    
    def download_products(self, local_cache) -> int:
        """
        상품 정보 다운로드 (Google Sheets → SQLite)
        주의: ESP32에서 자동 생성된 상품과 충돌하지 않도록 device_uuid가 있는 행만 업데이트
        
        Args:
            local_cache: LocalCache 인스턴스
        
        Returns:
            동기화된 상품 수
        """
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
                    # device_uuid가 없으면 ESP32 연결 안된 상품 - 스킵
                    continue
                    
                cursor.execute('''
                    INSERT OR REPLACE INTO products 
                    (product_id, gym_id, category, size, name, device_uuid, 
                     stock, enabled, display_order, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.get('product_id'),
                    record.get('gym_id', 'GYM001'),
                    record.get('category'),
                    record.get('size', ''),
                    record.get('name'),
                    device_uuid,
                    record.get('stock', 0),
                    1 if record.get('enabled') == 'TRUE' else 0,
                    record.get('display_order', 0),
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            local_cache.reload_products()  # 메모리 캐시 재로드
            
            print(f"[Sheets] 상품 정보 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            print(f"[Sheets] 상품 다운로드 오류: {e}")
            return 0
    
    # =============================
    # 업로드 (SQLite → Sheets)
    # =============================
    
    def upload_rentals(self, local_cache) -> int:
        """
        대여 이력 업로드
        
        Args:
            local_cache: LocalCache 인스턴스
        
        Returns:
            업로드된 대여 수
        """
        try:
            # 동기화되지 않은 대여 로그 조회
            rentals = local_cache.get_unsynced_rentals()
            
            if not rentals:
                return 0
            
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('rental_history')
            
            # 한 번에 추가 (배치)
            rows = []
            rental_ids = []
            
            for rental in rentals:
                rows.append([
                    rental['id'],
                    rental['member_id'],
                    rental.get('locker_number', ''),
                    rental['product_id'],
                    '',  # product_name (조회 필요 시)
                    rental.get('device_uuid', ''),  # device_uuid로 변경
                    rental['quantity'],       # 대여 수량 = 차감 횟수
                    rental['count_before'],   # 대여 전 잔여 횟수
                    rental['count_after'],    # 대여 후 잔여 횟수
                    rental['created_at']
                ])
                rental_ids.append(rental['id'])
            
            # 시트에 추가
            sheet.append_rows(rows)
            
            # 동기화 완료 표시
            local_cache.mark_rentals_synced(rental_ids)
            
            print(f"[Sheets] 대여 이력 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            print(f"[Sheets] 대여 업로드 오류: {e}")
            return 0
    
    def upload_usage_logs(self, local_cache, limit: int = 100) -> int:
        """
        횟수 변동 이력 업로드
        
        Args:
            local_cache: LocalCache 인스턴스
            limit: 최대 업로드 건수
        
        Returns:
            업로드된 로그 수
        """
        try:
            conn = local_cache.conn
            cursor = conn.cursor()
            
            # 아직 업로드되지 않은 로그 조회
            # (간단히 최근 limit 건만 업로드, 실제로는 synced 플래그 추가 필요)
            cursor.execute(f'''
                SELECT * FROM usage_logs 
                ORDER BY created_at DESC 
                LIMIT {limit}
            ''')
            
            logs = [dict(row) for row in cursor.fetchall()]
            
            if not logs:
                return 0
            
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('usage_history')
            
            rows = []
            for log in logs:
                rows.append([
                    log['id'],
                    log['member_id'],
                    log['amount'],
                    log['count_before'],
                    log['count_after'],
                    log['transaction_type'],
                    log.get('description', ''),
                    log['created_at']
                ])
            
            sheet.append_rows(rows)
            
            print(f"[Sheets] 횟수 변동 이력 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            print(f"[Sheets] 횟수 이력 업로드 오류: {e}")
            return 0
    
    def update_device_status(self, local_cache) -> int:
        """
        기기 상태 업데이트 (device_uuid 기반)
        
        Args:
            local_cache: LocalCache 인스턴스
        
        Returns:
            업데이트된 기기 수
        """
        try:
            # device_registry와 device_cache 조인
            devices = local_cache.get_all_devices()
            registry = {d['device_uuid']: d for d in local_cache.get_all_registered_devices()}
            
            if not devices and not registry:
                return 0
            
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('device_status')
            
            # 기존 데이터 전체 삭제 후 재작성
            sheet.clear()
            
            # 새 헤더 (category 추가)
            headers = ['device_uuid', 'mac_address', 'device_name', 'category',
                      'size', 'stock', 'status', 'wifi_rssi',
                      'last_heartbeat', 'ip_address', 'firmware_version',
                      'first_seen_at', 'updated_at']
            rows = [headers]
            
            # device_cache + device_registry 병합
            all_uuids = set(d.get('device_uuid') for d in devices) | set(registry.keys())
            
            for device_uuid in all_uuids:
                cache = next((d for d in devices if d.get('device_uuid') == device_uuid), {})
                reg = registry.get(device_uuid, {})
                
                # 상태 판단
                last_heartbeat = cache.get('last_heartbeat')
                if last_heartbeat:
                    try:
                        heartbeat_time = datetime.fromisoformat(last_heartbeat)
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
            
            # 헤더 서식 적용
            sheet.format('A1:M1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"[Sheets] 기기 상태 업데이트 완료: {len(rows) - 1}개")
            return len(rows) - 1
            
        except Exception as e:
            print(f"[Sheets] 기기 상태 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def upload_event_logs(self, local_cache, limit: int = 100) -> int:
        """
        비즈니스 이벤트 로그 업로드
        
        Args:
            local_cache: LocalCache 인스턴스
            limit: 최대 업로드 건수
        
        Returns:
            업로드된 이벤트 수
        """
        try:
            conn = local_cache.conn
            cursor = conn.cursor()
            
            # 동기화되지 않은 이벤트 조회
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
            
            # 시트 가져오기 (없으면 생성)
            try:
                sheet = self.spreadsheet.worksheet('event_logs')
            except:
                # 시트 생성
                sheet = self.spreadsheet.add_worksheet(title='event_logs', rows=1000, cols=10)
                # 헤더 추가
                headers = ['log_id', 'timestamp', 'event_type', 'severity', 
                          'device_uuid', 'member_id', 'product_id', 'details']
                sheet.append_row(headers)
                # 헤더 서식
                sheet.format('A1:H1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
            
            # 데이터 변환
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
            
            # 시트에 추가
            sheet.append_rows(rows)
            
            # 동기화 완료 표시
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
            import traceback
            traceback.print_exc()
            return 0
    
    def upload_products(self, local_cache) -> int:
        """
        상품 정보 업로드 (SQLite → Google Sheets)
        ESP32에서 자동 생성된 상품을 Google Sheets로 동기화
        
        Args:
            local_cache: LocalCache 인스턴스
        
        Returns:
            업로드된 상품 수
        """
        try:
            # SQLite에서 상품 조회
            conn = local_cache.conn
            cursor = conn.cursor()
            cursor.execute('''
                SELECT product_id, gym_id, category, size, name, 
                       device_uuid, stock, enabled, display_order, updated_at
                FROM products
                ORDER BY display_order, product_id
            ''')
            products = cursor.fetchall()
            
            if not products:
                return 0
            
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('products')
            
            # 기존 데이터 전체 삭제 후 재작성
            sheet.clear()
            
            # 헤더
            headers = ['product_id', 'gym_id', 'category', 'size', 'name', 
                      'device_uuid', 'stock', 'enabled', 'display_order', 'updated_at']
            rows = [headers]
            
            for p in products:
                rows.append([
                    p[0],  # product_id
                    p[1],  # gym_id
                    p[2],  # category
                    p[3],  # size
                    p[4],  # name
                    p[5] or '',  # device_uuid
                    p[6],  # stock
                    'TRUE' if p[7] else 'FALSE',  # enabled
                    p[8],  # display_order
                    p[9] or ''   # updated_at
                ])
            
            sheet.update('A1', rows)
            
            # 헤더 서식 적용
            sheet.format('A1:J1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"[Sheets] 상품 정보 업로드 완료: {len(products)}개")
            return len(products)
            
        except Exception as e:
            print(f"[Sheets] 상품 업로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def update_member_count(self, member_id: str, remaining_count: int) -> bool:
        """
        특정 회원의 잔여 횟수 업데이트 (실시간)
        
        Args:
            member_id: 회원 ID
            remaining_count: 새 잔여 횟수
        
        Returns:
            성공 여부
        """
        try:
            self._rate_limit()
            sheet = self.spreadsheet.worksheet('members')
            
            # 회원 찾기
            cell = sheet.find(member_id)
            if cell:
                # remaining_count 컬럼 업데이트 (4번째 컬럼)
                sheet.update_cell(cell.row, 4, remaining_count)
                return True
            else:
                print(f"[Sheets] 회원을 찾을 수 없음: {member_id}")
                return False
                
        except Exception as e:
            print(f"[Sheets] 횟수 업데이트 오류: {e}")
            return False
    
    # =============================
    # 배치 동기화
    # =============================
    
    def sync_all_downloads(self, local_cache) -> Dict[str, int]:
        """
        모든 다운로드 동기화 실행
        
        Returns:
            {'members': count, 'products': count}
        """
        result = {
            'members': self.download_members(local_cache),
            'products': self.download_products(local_cache)
        }
        return result
    
    def sync_all_uploads(self, local_cache) -> Dict[str, int]:
        """
        모든 업로드 동기화 실행
        
        Returns:
            {'rentals': count, 'usage_logs': count, 'devices': count}
        """
        result = {
            'rentals': self.upload_rentals(local_cache),
            'usage_logs': self.upload_usage_logs(local_cache),
            'devices': self.update_device_status(local_cache)
        }
        return result


# =============================
# 동기화 스케줄러 (백그라운드 작업)
# =============================

class SyncScheduler:
    """동기화 스케줄러"""
    
    def __init__(self, sheets_sync: SheetsSync, local_cache, 
                 download_interval: int = 300,  # 5분
                 upload_interval: int = 5):     # 5초
        """
        초기화
        
        Args:
            sheets_sync: SheetsSync 인스턴스
            local_cache: LocalCache 인스턴스
            download_interval: 다운로드 주기 (초)
            upload_interval: 업로드 주기 (초)
        """
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
        """
        스케줄러 틱 (메인 루프에서 호출)
        주기적으로 호출하여 동기화 작업 실행
        """
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
            if any(result.values()):  # 업로드할 데이터가 있었으면 로그
                print(f"[SyncScheduler] 업로드 완료: {result}")
            self.last_upload = now


# =============================
# 사용 예시
# =============================

if __name__ == '__main__':
    from local_cache import LocalCache
    
    # LocalCache 초기화
    cache = LocalCache()
    
    # SheetsSync 초기화 (credentials.json 필요)
    sync = SheetsSync(
        credentials_path='config/credentials.json',
        spreadsheet_name='F-BOX 관리 시스템'
    )
    
    if sync.connect():
        # 다운로드
        sync.download_members(cache)
        sync.download_products(cache)
        
        # 업로드
        sync.upload_rentals(cache)
        sync.update_device_status(cache)

