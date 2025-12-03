"""
이벤트 로거 서비스

MQTT Raw 이벤트를 비즈니스 이벤트로 분류하여 event_logs 테이블에 저장
- rental_success / rental_failed: 대여 성공/실패
- stock_low / stock_empty: 재고 부족/없음
- device_online / device_offline: 기기 상태
- door_opened / door_closed: 문 열림/닫힘
- error: 기기 에러
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any


class EventLogger:
    """비즈니스 이벤트 로거"""
    
    # 이벤트 타입별 심각도 매핑
    SEVERITY_MAP = {
        # 정상 이벤트 (info)
        'rental_success': 'info',
        'device_online': 'info',
        'door_closed': 'info',
        'stock_updated': 'info',
        
        # 경고 이벤트 (warning)
        'stock_low': 'warning',
        'door_opened': 'warning',
        'device_offline': 'warning',
        
        # 에러 이벤트 (error)
        'rental_failed': 'error',
        'stock_empty': 'error',
        'dispense_failed': 'error',
        'motor_error': 'error',
        'home_failed': 'error',
        'error': 'error',
    }
    
    def __init__(self, local_cache):
        """
        초기화
        
        Args:
            local_cache: LocalCache 인스턴스 (DB 접근용)
        """
        self.local_cache = local_cache
        print("[EventLogger] 초기화 완료")
    
    def log_event(self, event_type: str, 
                  device_uuid: str = None,
                  member_id: str = None,
                  product_id: str = None,
                  details: Dict[str, Any] = None,
                  severity: str = None) -> int:
        """
        비즈니스 이벤트 로깅
        
        Args:
            event_type: 이벤트 타입
            device_uuid: 관련 기기 UUID
            member_id: 관련 회원 ID
            product_id: 관련 상품 ID
            details: 상세 정보 (dict → JSON 저장)
            severity: 심각도 (None이면 자동 결정)
        
        Returns:
            생성된 event_log ID
        """
        # 심각도 자동 결정
        if severity is None:
            severity = self.SEVERITY_MAP.get(event_type, 'info')
        
        # details를 JSON 문자열로 변환
        details_json = json.dumps(details, ensure_ascii=False) if details else None
        
        try:
            conn = self.local_cache.conn
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO event_logs 
                (event_type, severity, device_uuid, member_id, product_id, details, created_at, synced_to_sheets)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ''', (event_type, severity, device_uuid, member_id, product_id, 
                  details_json, datetime.now().isoformat()))
            
            event_id = cursor.lastrowid
            conn.commit()
            
            print(f"[EventLogger] {severity.upper()}: {event_type} (ID: {event_id})")
            
            return event_id
            
        except Exception as e:
            print(f"[EventLogger] 로깅 실패: {e}")
            return -1
    
    # =============================
    # 대여 관련 이벤트
    # =============================
    
    def log_rental_success(self, member_id: str, product_id: str, 
                           device_uuid: str, quantity: int,
                           payment_type: str = 'voucher', amount: int = 0):
        """대여 성공 이벤트 (금액권/구독권 기반)"""
        return self.log_event(
            event_type='rental_success',
            device_uuid=device_uuid,
            member_id=member_id,
            product_id=product_id,
            details={
                'quantity': quantity,
                'payment_type': payment_type,
                'amount': amount,
            }
        )
    
    def log_rental_failed(self, member_id: str, product_id: str,
                          device_uuid: str, reason: str):
        """대여 실패 이벤트"""
        return self.log_event(
            event_type='rental_failed',
            device_uuid=device_uuid,
            member_id=member_id,
            product_id=product_id,
            details={
                'reason': reason,
                'reason_text': self._get_fail_reason_text(reason),
            }
        )
    
    def _get_fail_reason_text(self, reason: str) -> str:
        """실패 이유를 한글로 변환"""
        reasons = {
            'device_locked': '기기 잠금 상태',
            'no_stock': '재고 없음',
            'door_open': '문 열림',
            'emergency_stop': '긴급 정지',
            'timeout': '응답 없음',
            'mqtt_not_connected': 'MQTT 미연결',
            'mqtt_send_failed': '명령 전송 실패',
        }
        return reasons.get(reason, reason)
    
    # =============================
    # 재고 관련 이벤트
    # =============================
    
    def log_stock_low(self, device_uuid: str, product_id: str, stock: int):
        """재고 부족 이벤트 (5개 이하)"""
        return self.log_event(
            event_type='stock_low',
            device_uuid=device_uuid,
            product_id=product_id,
            details={'stock': stock}
        )
    
    def log_stock_empty(self, device_uuid: str, product_id: str):
        """재고 없음 이벤트"""
        return self.log_event(
            event_type='stock_empty',
            device_uuid=device_uuid,
            product_id=product_id,
            details={'stock': 0}
        )
    
    def log_stock_updated(self, device_uuid: str, product_id: str, 
                          stock: int, source: str):
        """재고 업데이트 이벤트"""
        return self.log_event(
            event_type='stock_updated',
            device_uuid=device_uuid,
            product_id=product_id,
            details={'stock': stock, 'source': source}
        )
    
    # =============================
    # 기기 상태 이벤트
    # =============================
    
    def log_device_online(self, device_uuid: str, ip_address: str = None,
                          firmware_version: str = None):
        """기기 온라인 이벤트 (부팅/재연결)"""
        return self.log_event(
            event_type='device_online',
            device_uuid=device_uuid,
            details={
                'ip_address': ip_address,
                'firmware_version': firmware_version,
            }
        )
    
    def log_device_offline(self, device_uuid: str, last_heartbeat: str = None):
        """기기 오프라인 이벤트"""
        return self.log_event(
            event_type='device_offline',
            device_uuid=device_uuid,
            details={'last_heartbeat': last_heartbeat}
        )
    
    def log_door_opened(self, device_uuid: str):
        """문 열림 이벤트"""
        return self.log_event(
            event_type='door_opened',
            device_uuid=device_uuid,
            details={}
        )
    
    def log_door_closed(self, device_uuid: str, stock: int = None):
        """문 닫힘 이벤트"""
        return self.log_event(
            event_type='door_closed',
            device_uuid=device_uuid,
            details={'stock': stock}
        )
    
    # =============================
    # 에러 이벤트
    # =============================
    
    def log_error(self, device_uuid: str, error_code: str, 
                  error_message: str):
        """일반 에러 이벤트"""
        return self.log_event(
            event_type='error',
            device_uuid=device_uuid,
            details={
                'error_code': error_code,
                'error_message': error_message,
            }
        )
    
    def log_dispense_failed(self, device_uuid: str, reason: str,
                            member_id: str = None, product_id: str = None):
        """토출 실패 이벤트 (MQTT에서 직접 호출)"""
        return self.log_event(
            event_type='dispense_failed',
            device_uuid=device_uuid,
            member_id=member_id,
            product_id=product_id,
            details={
                'reason': reason,
                'reason_text': self._get_fail_reason_text(reason),
            }
        )
    
    # =============================
    # 조회
    # =============================
    
    def get_unsynced_events(self, limit: int = 100) -> list:
        """Sheets에 동기화되지 않은 이벤트 조회"""
        try:
            conn = self.local_cache.conn
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM event_logs 
                WHERE synced_to_sheets = 0 
                ORDER BY created_at
                LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"[EventLogger] 조회 실패: {e}")
            return []
    
    def mark_events_synced(self, event_ids: list):
        """이벤트를 동기화 완료로 표시"""
        if not event_ids:
            return
        
        try:
            conn = self.local_cache.conn
            cursor = conn.cursor()
            
            placeholders = ', '.join(['?' for _ in event_ids])
            cursor.execute(f'''
                UPDATE event_logs 
                SET synced_to_sheets = 1 
                WHERE id IN ({placeholders})
            ''', event_ids)
            
            conn.commit()
            print(f"[EventLogger] {len(event_ids)}건 동기화 완료 표시")
            
        except Exception as e:
            print(f"[EventLogger] 동기화 표시 실패: {e}")
    
    def get_recent_events(self, limit: int = 50, 
                          event_type: str = None,
                          severity: str = None) -> list:
        """최근 이벤트 조회"""
        try:
            conn = self.local_cache.conn
            cursor = conn.cursor()
            
            query = 'SELECT * FROM event_logs WHERE 1=1'
            params = []
            
            if event_type:
                query += ' AND event_type = ?'
                params.append(event_type)
            
            if severity:
                query += ' AND severity = ?'
                params.append(severity)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"[EventLogger] 조회 실패: {e}")
            return []

