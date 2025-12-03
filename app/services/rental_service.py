"""
대여 서비스 - 비즈니스 로직

횟수 기반 대여 처리:
1. 회원/상품/기기 검증
2. DISPENSE 명령 전송 + 응답 대기
3. 성공 시에만 횟수 차감 (1개 = 1회)
4. 대여 로그 기록
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import time

# 옵셔널 임포트 (LocalCache, MQTTService, EventLogger)
try:
    from app.services.local_cache import LocalCache
except Exception as e:
    print(f"[RentalService] LocalCache 임포트 실패: {e}")
    LocalCache = None

try:
    from app.services.mqtt_service import MQTTService
except Exception as e:
    print(f"[RentalService] MQTTService 임포트 실패: {e}")
    MQTTService = None

try:
    from app.services.event_logger import EventLogger
except Exception as e:
    print(f"[RentalService] EventLogger 임포트 실패: {e}")
    EventLogger = None


class DispenseResult:
    """DISPENSE 응답 대기를 위한 클래스"""
    
    def __init__(self):
        self.event = threading.Event()
        self.success = None
        self.reason = None
        self.stock = None
    
    def set_success(self, stock: int):
        self.success = True
        self.stock = stock
        self.event.set()
    
    def set_failed(self, reason: str):
        self.success = False
        self.reason = reason
        self.event.set()
    
    def wait(self, timeout: float = 5.0) -> bool:
        """응답 대기. timeout 초과 시 False 반환"""
        return self.event.wait(timeout)


class RentalService:
    """대여 관련 비즈니스 로직을 처리하는 서비스"""
    
    # DISPENSE 응답 대기용 (device_uuid → DispenseResult)
    _pending_dispense: Dict[str, DispenseResult] = {}
    _pending_lock = threading.Lock()
    
    def __init__(self, local_cache=None, mqtt_service=None):
        """
        초기화
        
        Args:
            local_cache: LocalCache 인스턴스
            mqtt_service: MQTTService 인스턴스 (None이면 lazy 생성)
        """
        if local_cache:
            self.local_cache = local_cache
        elif LocalCache:
            try:
                self.local_cache = LocalCache()
            except Exception as e:
                print(f"[RentalService] LocalCache 초기화 실패: {e}")
                self.local_cache = None
        else:
            self.local_cache = None
        
        self._mqtt_service = mqtt_service
        self._handlers_registered = False
        
        # EventLogger 초기화
        self._event_logger = None
        if self.local_cache and EventLogger:
            try:
                self._event_logger = EventLogger(self.local_cache)
            except Exception as e:
                print(f"[RentalService] EventLogger 초기화 실패: {e}")
    
    def set_mqtt_service(self, mqtt_service):
        """외부에서 MQTT 서비스 주입"""
        self._mqtt_service = mqtt_service
        if mqtt_service and not self._handlers_registered:
            self._register_dispense_handlers()
    
    @property
    def mqtt_service(self) -> Optional[MQTTService]:
        """MQTT 서비스 (외부 주입 필수)"""
        if self._mqtt_service is None:
            print("[RentalService] ⚠️ MQTT 서비스가 설정되지 않음. set_mqtt_service() 호출 필요")
            return None
        
        # DISPENSE 응답 핸들러 등록
        if not self._handlers_registered:
            self._register_dispense_handlers()
        
        return self._mqtt_service
    
    def _register_dispense_handlers(self):
        """DISPENSE 응답 핸들러 등록"""
        if not self._mqtt_service:
            return
        
        def on_dispense_complete(device_uuid: str, payload: dict):
            stock = payload.get('stock', 0)
            
            # 로컬 DB 재고 즉시 업데이트
            if self.local_cache:
                product = self.local_cache.get_product_by_device_uuid(device_uuid)
                if product:
                    self.local_cache.update_product_stock(product['product_id'], stock)
                    print(f"[RentalService] 📦 재고 업데이트: {product['product_id']} → {stock}개")
                self.local_cache.update_device_status(device_uuid, stock=stock)
            
            with self._pending_lock:
                if device_uuid in self._pending_dispense:
                    self._pending_dispense[device_uuid].set_success(stock)
                    print(f"[RentalService] ✅ DISPENSE 성공: {device_uuid}, 재고: {stock}")
        
        def on_dispense_failed(device_uuid: str, payload: dict):
            reason = payload.get('reason', 'unknown')
            with self._pending_lock:
                if device_uuid in self._pending_dispense:
                    self._pending_dispense[device_uuid].set_failed(reason)
                    print(f"[RentalService] ❌ DISPENSE 실패: {device_uuid}, 이유: {reason}")
        
        self._mqtt_service.register_event_handler('dispense_complete', on_dispense_complete)
        self._mqtt_service.register_event_handler('dispense_failed', on_dispense_failed)
        self._handlers_registered = True
        print("[RentalService] DISPENSE 응답 핸들러 등록 완료")
    
    def _dispense_and_wait(self, device_uuid: str, timeout: float = 5.0) -> DispenseResult:
        """
        DISPENSE 명령 전송 후 응답 대기
        
        Args:
            device_uuid: 기기 UUID
            timeout: 응답 대기 타임아웃 (초)
        
        Returns:
            DispenseResult (success, reason, stock)
        """
        result = DispenseResult()
        
        if not self.mqtt_service:
            result.set_failed("mqtt_not_connected")
            return result
        
        # 대기 목록에 등록
        with self._pending_lock:
            self._pending_dispense[device_uuid] = result
        
        try:
            # DISPENSE 명령 전송
            sent = self._mqtt_service.dispense(device_uuid)
            if not sent:
                result.set_failed("mqtt_send_failed")
                return result
            
            # 응답 대기
            if not result.wait(timeout):
                result.set_failed("timeout")
                print(f"[RentalService] ⏰ DISPENSE 타임아웃: {device_uuid}")
        finally:
            # 대기 목록에서 제거
            with self._pending_lock:
                self._pending_dispense.pop(device_uuid, None)
        
        return result
    
    def process_rental(self, member_id: str, items: List[Dict]) -> Dict:
        """
        대여 처리 (DISPENSE 성공 시에만 차감)
        
        Args:
            member_id: 회원 ID
            items: 대여 아이템 목록
                   [{"product_id": "...", "quantity": 1, "device_uuid": "..."}, ...]
        
        Returns:
            {
                "success": True/False,
                "message": "...",
                "remaining_count": 잔여횟수 (성공 시)
            }
        
        Raises:
            ValueError: 검증 실패 시
        """
        # 1. 회원 정보 확인
        member = self.local_cache.get_member(member_id)
        if not member:
            raise ValueError(f"회원을 찾을 수 없습니다: {member_id}")
        
        if member.get('status') != 'active':
            raise ValueError("비활성화된 회원입니다.")
        
        # 2. 총 차감 횟수 계산
        total_count = sum(item['quantity'] for item in items)
        
        if total_count <= 0:
            raise ValueError("선택된 상품이 없습니다.")
        
        # 3. 잔여 횟수 검증
        remaining = member.get('remaining_count', 0)
        if remaining < total_count:
            raise ValueError(f"잔여 횟수가 부족합니다. (필요: {total_count}회, 잔여: {remaining}회)")
        
        # 4. 각 상품별 검증
        validated_items = []
        for item in items:
            validated = self._validate_item(item)
            validated_items.append(validated)
        
        # 5. 각 상품별 DISPENSE 명령 전송 및 응답 대기
        dispense_results = []
        success_items = []
        failed_items = []
        
        for item in validated_items:
            device_uuid = item['device_uuid']
            quantity = item['quantity']
            
            # 수량만큼 DISPENSE 실행
            item_success_count = 0
            item_failed = False
            fail_reason = None
            
            for i in range(quantity):
                result = self._dispense_and_wait(device_uuid, timeout=10.0)
                
                if result.success:
                    item_success_count += 1
                else:
                    item_failed = True
                    fail_reason = result.reason
                    break  # 실패하면 해당 상품 중단
            
            if item_success_count > 0:
                success_items.append({
                    **item,
                    'dispensed_count': item_success_count,
                })
            
            if item_failed:
                failed_items.append({
                    **item,
                    'dispensed_count': item_success_count,
                    'reason': fail_reason,
                })
            
            dispense_results.append({
                'product_id': item['product_id'],
                'product_name': item['product_name'],
                'requested': quantity,
                'dispensed': item_success_count,
                'success': not item_failed,
                'reason': fail_reason,
            })
        
        # 6. 성공한 수량만큼 횟수 차감
        total_dispensed = sum(item['dispensed_count'] for item in success_items)
        
        if total_dispensed > 0:
            count_before, count_after = self.local_cache.update_member_count(
                member_id=member_id,
                amount=-total_dispensed,
                type='rental',
                description=f"대여 {len(success_items)}건, 총 {total_dispensed}개"
            )
            
            # 대여 로그 기록 (성공한 것만)
            for item in success_items:
                try:
                    self.local_cache.add_rental_log(
                        member_id=member_id,
                        locker_number=0,
                        product_id=item['product_id'],
                        product_name=item['product_name'],
                        device_id=item['device_uuid'],
                        quantity=item['dispensed_count'],
                        count_before=count_before,
                        count_after=count_after
                    )
                    
                    # 이벤트 로깅: 대여 성공
                    if self._event_logger:
                        self._event_logger.log_rental_success(
                            member_id=member_id,
                            product_id=item['product_id'],
                            device_uuid=item['device_uuid'],
                            quantity=item['dispensed_count'],
                            count_before=count_before,
                            count_after=count_after
                        )
                except Exception as e:
                    print(f"[RentalService] 대여 로그 기록 실패: {e}")
        else:
            count_after = remaining
        
        # 이벤트 로깅: 대여 실패
        if self._event_logger:
            for item in failed_items:
                self._event_logger.log_rental_failed(
                    member_id=member_id,
                    product_id=item['product_id'],
                    device_uuid=item['device_uuid'],
                    reason=item['reason']
                )
        
        # 7. 결과 반환
        if len(failed_items) == 0:
            # 모두 성공
            return {
                'success': True,
                'message': f'대여가 완료되었습니다. ({total_dispensed}개)',
                'remaining_count': count_after,
                'dispense_results': dispense_results,
            }
        elif total_dispensed > 0:
            # 일부 성공
            fail_reasons = [f"{i['product_name']}: {i['reason']}" for i in failed_items]
            return {
                'success': True,
                'message': f'일부 대여 완료 ({total_dispensed}개 성공, {len(failed_items)}건 실패: {", ".join(fail_reasons)})',
                'remaining_count': count_after,
                'dispense_results': dispense_results,
            }
        else:
            # 모두 실패
            fail_reasons = [f"{i['product_name']}: {self._get_fail_reason_text(i['reason'])}" for i in failed_items]
            return {
                'success': False,
                'message': f'대여 실패: {", ".join(fail_reasons)}',
                'remaining_count': remaining,
                'dispense_results': dispense_results,
            }
    
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
    
    def _validate_item(self, item: Dict) -> Dict:
        """
        개별 아이템 검증
        
        Args:
            item: {"product_id": "...", "quantity": 1, "device_uuid": "..."}
        
        Returns:
            검증된 아이템 정보 (product 정보 포함)
        
        Raises:
            ValueError: 검증 실패 시
        """
        product_id = item.get('product_id')
        quantity = item.get('quantity', 1)
        device_uuid = item.get('device_uuid')
        
        # 상품 조회
        product = self.local_cache.get_product(product_id)
        if not product:
            raise ValueError(f"상품을 찾을 수 없습니다: {product_id}")
        
        # device_uuid 확인
        if not device_uuid:
            device_uuid = product.get('device_uuid')
        
        if not device_uuid:
            raise ValueError(f"상품 '{product['name']}'에 연결된 기기가 없습니다.")
        
        # 기기 상태 확인
        device = self.local_cache.get_device(device_uuid)
        if not device:
            print(f"[RentalService] 경고: 기기 상태 정보 없음 ({device_uuid})")
        else:
            # 온라인 상태 확인
            last_heartbeat = device.get('last_heartbeat')
            if last_heartbeat:
                try:
                    hb_time = datetime.fromisoformat(last_heartbeat)
                    if (datetime.now() - hb_time) > timedelta(minutes=2):
                        raise ValueError(f"상품 '{product['name']}' 기기가 오프라인 상태입니다.")
                except ValueError as e:
                    if "오프라인" in str(e):
                        raise
        
        return {
            'product_id': product_id,
            'product_name': product['name'],
            'quantity': quantity,
            'device_uuid': device_uuid,
            'category': product.get('category'),
            'size': product.get('size'),
        }
    
    def get_inventory_status(self) -> Dict:
        """
        재고 현황 조회
        
        Returns:
            카테고리별 재고 현황
        """
        products = self.local_cache.get_products()
        
        inventory = {
            'categories': {},
            'total': {
                'total': 0,
                'available': 0,
            }
        }
        
        for product in products:
            category = product.get('category', 'other')
            device_uuid = product.get('device_uuid')
            
            # 실시간 재고 조회
            stock = product.get('stock', 0)
            if device_uuid:
                device = self.local_cache.get_device(device_uuid)
                if device and device.get('stock') is not None:
                    stock = device['stock']
            
            # 카테고리별 집계
            if category not in inventory['categories']:
                inventory['categories'][category] = {
                    'name': self._get_category_name(category),
                    'items': [],
                    'total': 0,
                    'available': 0,
                }
            
            cat_data = inventory['categories'][category]
            cat_data['items'].append({
                'product_id': product['product_id'],
                'name': product['name'],
                'size': product.get('size', ''),
                'stock': stock,
            })
            cat_data['available'] += stock
            cat_data['total'] += 1
            
            inventory['total']['available'] += stock
            inventory['total']['total'] += 1
        
        return inventory
    
    def _get_category_name(self, category: str) -> str:
        """카테고리 코드를 한글명으로 변환"""
        names = {
            'top': '상의',
            'pants': '하의',
            'towel': '수건',
            'sweat_towel': '땀수건',
            'other': '기타',
        }
        return names.get(category, category)
    
    def return_item(self, rental_id: str) -> Dict:
        """
        반납 처리 (현재 미구현 - 별도 반납함 사용)
        """
        return {
            'success': False,
            'message': '반납은 반납함을 이용해주세요.'
        }
