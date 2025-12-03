"""
대여 서비스 - 비즈니스 로직 (금액권/구독권 기반)

대여 처리:
1. 회원/상품/기기 검증
2. 결제 수단 선택 (구독권 또는 금액권)
3. 구독권: 일일 제한 확인
4. 금액권: 잔액 확인, 쪼개기 지원
5. DISPENSE 명령 전송 + 응답 대기
6. 성공 시에만 차감/사용량 기록
7. 대여 로그 기록
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading

# 옵셔널 임포트
try:
    from app.services.local_cache import LocalCache, get_kst_now
except Exception as e:
    print(f"[RentalService] LocalCache 임포트 실패: {e}")
    LocalCache = None
    def get_kst_now():
        return datetime.now()

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
    """대여 관련 비즈니스 로직을 처리하는 서비스 (금액권/구독권 기반)"""
    
    # DISPENSE 응답 대기용
    _pending_dispense: Dict[str, DispenseResult] = {}
    _pending_lock = threading.Lock()
    
    def __init__(self, local_cache=None, mqtt_service=None):
        """초기화"""
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
        """MQTT 서비스"""
        if self._mqtt_service is None:
            print("[RentalService] ⚠️ MQTT 서비스가 설정되지 않음")
            return None
        
        if not self._handlers_registered:
            self._register_dispense_handlers()
        
        return self._mqtt_service
    
    def _register_dispense_handlers(self):
        """DISPENSE 응답 핸들러 등록"""
        if not self._mqtt_service:
            return
        
        def on_dispense_complete(device_uuid: str, payload: dict):
            stock = payload.get('stock', 0)
            
            if self.local_cache:
                product = self.local_cache.get_product_by_device_uuid(device_uuid)
                if product:
                    self.local_cache.update_product_stock(product['product_id'], stock)
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
    
    def _dispense_and_wait(self, device_uuid: str, timeout: float = 10.0) -> DispenseResult:
        """DISPENSE 명령 전송 후 응답 대기"""
        result = DispenseResult()
        
        if not self.mqtt_service:
            result.set_failed("mqtt_not_connected")
            return result
        
        with self._pending_lock:
            self._pending_dispense[device_uuid] = result
        
        try:
            sent = self._mqtt_service.dispense(device_uuid)
            if not sent:
                result.set_failed("mqtt_send_failed")
                return result
            
            if not result.wait(timeout):
                result.set_failed("timeout")
                print(f"[RentalService] ⏰ DISPENSE 타임아웃: {device_uuid}")
        finally:
            with self._pending_lock:
                self._pending_dispense.pop(device_uuid, None)
        
        return result
    
    # =============================
    # 대여 처리 (금액권/구독권 기반)
    # =============================
    
    def process_rental_with_subscription(self, member_id: str, items: List[Dict], 
                                         subscription_id: int) -> Dict:
        """
        구독권으로 대여 처리
        
        Args:
            member_id: 회원 ID
            items: [{"product_id": "...", "quantity": 1, "device_uuid": "..."}, ...]
            subscription_id: 사용할 구독권 ID
        
        Returns:
            대여 결과
        """
        # 1. 회원 검증
        member = self.local_cache.get_member(member_id)
        if not member:
            raise ValueError(f"회원을 찾을 수 없습니다: {member_id}")
        if member.get('status') != 'active':
            raise ValueError("비활성화된 회원입니다.")
        
        # 2. 구독권 검증
        subscriptions = self.local_cache.get_active_subscriptions(member_id)
        subscription = next((s for s in subscriptions if s['subscription_id'] == subscription_id), None)
        if not subscription:
            raise ValueError("유효한 구독권이 아닙니다.")
        
        # 3. 각 상품별 일일 제한 확인
        validated_items = []
        for item in items:
            validated = self._validate_item(item)
            category = validated['category']
            quantity = validated['quantity']
            
            remaining = self.local_cache.get_subscription_remaining(subscription_id, category)
            if remaining < quantity:
                raise ValueError(f"{self._get_category_name(category)} 일일 제한 초과 (남은 횟수: {remaining})")
            
            validated_items.append(validated)
        
        # 4. DISPENSE 실행
        success_items = []
        failed_items = []
        dispense_results = []
        
        for item in validated_items:
            device_uuid = item['device_uuid']
            quantity = item['quantity']
            
            dispensed = 0
            fail_reason = None
            
            for _ in range(quantity):
                result = self._dispense_and_wait(device_uuid)
                if result.success:
                    dispensed += 1
                else:
                    fail_reason = result.reason
                    break
            
            if dispensed > 0:
                success_items.append({**item, 'dispensed_count': dispensed})
            if fail_reason:
                failed_items.append({**item, 'dispensed_count': dispensed, 'reason': fail_reason})
            
            dispense_results.append({
                'product_id': item['product_id'],
                'product_name': item['product_name'],
                'requested': quantity,
                'dispensed': dispensed,
                'success': fail_reason is None,
                'reason': fail_reason,
            })
        
        # 5. 성공한 것만 기록
        for item in success_items:
            # 구독권 사용량 증가
            self.local_cache.use_subscription(subscription_id, item['category'], item['dispensed_count'])
            
            # 대여 로그
            self.local_cache.add_rental_log(
                member_id=member_id,
                product_id=item['product_id'],
                device_uuid=item['device_uuid'],
                quantity=item['dispensed_count'],
                payment_type='subscription',
                subscription_id=subscription_id,
                amount=0,
                product_name=item['product_name']
            )
        
        total_dispensed = sum(i['dispensed_count'] for i in success_items)
        
        if not failed_items:
            return {
                'success': True,
                'message': f'대여 완료 ({total_dispensed}개)',
                'payment_type': 'subscription',
                'dispense_results': dispense_results,
            }
        elif total_dispensed > 0:
            return {
                'success': True,
                'message': f'일부 대여 완료 ({total_dispensed}개 성공)',
                'payment_type': 'subscription',
                'dispense_results': dispense_results,
            }
        else:
            return {
                'success': False,
                'message': f'대여 실패: {self._get_fail_reason_text(failed_items[0]["reason"])}',
                'payment_type': 'subscription',
                'dispense_results': dispense_results,
            }
    
    def process_rental_with_vouchers(self, member_id: str, items: List[Dict],
                                     voucher_selections: List[Dict]) -> Dict:
        """
        금액권으로 대여 처리 (쪼개기 지원)
        
        Args:
            member_id: 회원 ID
            items: [{"product_id": "...", "quantity": 1, "device_uuid": "..."}, ...]
            voucher_selections: [{"voucher_id": 1, "amount": 500}, {"voucher_id": 2, "amount": 500}]
                               하나의 상품에 여러 금액권 사용 가능
        
        Returns:
            대여 결과
        """
        # 1. 회원 검증
        member = self.local_cache.get_member(member_id)
        if not member:
            raise ValueError(f"회원을 찾을 수 없습니다: {member_id}")
        if member.get('status') != 'active':
            raise ValueError("비활성화된 회원입니다.")
        
        # 2. 상품 검증 및 총 금액 계산
        validated_items = []
        total_amount = 0
        for item in items:
            validated = self._validate_item(item)
            product = self.local_cache.get_product(validated['product_id'])
            price = product.get('price', 1000)
            item_amount = price * validated['quantity']
            validated['price'] = price
            validated['total_amount'] = item_amount
            validated_items.append(validated)
            total_amount += item_amount
        
        # 3. 금액권 잔액 검증
        total_voucher_amount = sum(v['amount'] for v in voucher_selections)
        if total_voucher_amount < total_amount:
            raise ValueError(f"금액권 잔액 부족 (필요: {total_amount}원, 선택: {total_voucher_amount}원)")
        
        # 4. 각 금액권 잔액 확인
        active_vouchers = {v['voucher_id']: v for v in self.local_cache.get_active_vouchers(member_id)}
        for selection in voucher_selections:
            voucher_id = selection['voucher_id']
            amount = selection['amount']
            
            if voucher_id not in active_vouchers:
                raise ValueError(f"유효하지 않은 금액권: #{voucher_id}")
            
            voucher = active_vouchers[voucher_id]
            if voucher['remaining_amount'] < amount:
                raise ValueError(f"금액권 #{voucher_id} 잔액 부족 (잔액: {voucher['remaining_amount']}원)")
        
        # 5. DISPENSE 실행
        success_items = []
        failed_items = []
        dispense_results = []
        
        for item in validated_items:
            device_uuid = item['device_uuid']
            quantity = item['quantity']
            
            dispensed = 0
            fail_reason = None
            
            for _ in range(quantity):
                result = self._dispense_and_wait(device_uuid)
                if result.success:
                    dispensed += 1
                else:
                    fail_reason = result.reason
                    break
            
            if dispensed > 0:
                success_items.append({**item, 'dispensed_count': dispensed})
            if fail_reason:
                failed_items.append({**item, 'dispensed_count': dispensed, 'reason': fail_reason})
            
            dispense_results.append({
                'product_id': item['product_id'],
                'product_name': item['product_name'],
                'requested': quantity,
                'dispensed': dispensed,
                'success': fail_reason is None,
                'reason': fail_reason,
            })
        
        # 6. 성공한 것만 금액권 차감 및 기록
        total_dispensed = sum(i['dispensed_count'] for i in success_items)
        
        if total_dispensed > 0:
            # 실제 차감할 금액 계산
            actual_amount = sum(i['price'] * i['dispensed_count'] for i in success_items)
            
            # 금액권 차감 (선택된 순서대로)
            remaining_to_deduct = actual_amount
            deducted_vouchers = []
            
            for selection in voucher_selections:
                if remaining_to_deduct <= 0:
                    break
                
                voucher_id = selection['voucher_id']
                max_amount = selection['amount']
                deduct_amount = min(max_amount, remaining_to_deduct)
                
                # 대여 로그 먼저 생성 (rental_log_id 필요)
                # 첫 번째 성공 아이템에 대한 로그
                if success_items:
                    first_item = success_items[0]
                    rental_log_id = self.local_cache.add_rental_log(
                        member_id=member_id,
                        product_id=first_item['product_id'],
                        device_uuid=first_item['device_uuid'],
                        quantity=first_item['dispensed_count'],
                        payment_type='voucher',
                        amount=deduct_amount,
                        product_name=first_item['product_name']
                    )
                else:
                    rental_log_id = None
                
                # 금액권 차감
                self.local_cache.deduct_voucher(voucher_id, deduct_amount, rental_log_id)
                
                deducted_vouchers.append({
                    'voucher_id': voucher_id,
                    'amount': deduct_amount
                })
                remaining_to_deduct -= deduct_amount
            
            # 나머지 성공 아이템들 로그 (금액 0으로)
            for item in success_items[1:]:
                self.local_cache.add_rental_log(
                    member_id=member_id,
                    product_id=item['product_id'],
                    device_uuid=item['device_uuid'],
                    quantity=item['dispensed_count'],
                    payment_type='voucher',
                    amount=0,  # 첫 번째 로그에 전체 금액 기록됨
                    product_name=item['product_name']
                )
        
        if not failed_items:
            return {
                'success': True,
                'message': f'대여 완료 ({total_dispensed}개, {actual_amount}원 차감)',
                'payment_type': 'voucher',
                'total_amount': actual_amount if total_dispensed > 0 else 0,
                'dispense_results': dispense_results,
            }
        elif total_dispensed > 0:
            return {
                'success': True,
                'message': f'일부 대여 완료 ({total_dispensed}개)',
                'payment_type': 'voucher',
                'total_amount': actual_amount,
                'dispense_results': dispense_results,
            }
        else:
            return {
                'success': False,
                'message': f'대여 실패: {self._get_fail_reason_text(failed_items[0]["reason"])}',
                'payment_type': 'voucher',
                'total_amount': 0,
                'dispense_results': dispense_results,
            }
    
    def calculate_rental_cost(self, items: List[Dict]) -> int:
        """
        대여 비용 계산
        
        Args:
            items: [{"product_id": "...", "quantity": 1}, ...]
        
        Returns:
            총 비용 (원)
        """
        total = 0
        for item in items:
            product = self.local_cache.get_product(item['product_id'])
            if product:
                price = product.get('price', 1000)
                quantity = item.get('quantity', 1)
                total += price * quantity
        return total
    
    def get_available_payment_methods(self, member_id: str, category: str = None) -> Dict:
        """
        사용 가능한 결제 수단 조회
        
        Args:
            member_id: 회원 ID
            category: 카테고리 (구독권 잔여 횟수 확인용)
        
        Returns:
            {
                "subscriptions": [...],  # 활성 구독권 목록 (잔여 횟수 포함)
                "vouchers": [...],       # 활성 금액권 목록
                "total_balance": 1000,   # 총 금액권 잔액
            }
        """
        # 활성 구독권
        subscriptions = self.local_cache.get_active_subscriptions(member_id)
        for sub in subscriptions:
            if category:
                sub['remaining_today'] = self.local_cache.get_subscription_remaining(
                    sub['subscription_id'], category
                )
            else:
                # 모든 카테고리 잔여 횟수
                sub['remaining_by_category'] = {}
                for cat in ['top', 'pants', 'towel', 'sweat_towel', 'other']:
                    sub['remaining_by_category'][cat] = self.local_cache.get_subscription_remaining(
                        sub['subscription_id'], cat
                    )
        
        # 활성 금액권
        vouchers = self.local_cache.get_active_vouchers(member_id)
        total_balance = sum(v['remaining_amount'] for v in vouchers)
        
        return {
            'subscriptions': subscriptions,
            'vouchers': vouchers,
            'total_balance': total_balance,
        }
    
    def get_member_cards(self, member_id: str) -> Dict:
        """
        회원의 모든 카드 조회 (마이페이지용)
        
        Args:
            member_id: 회원 ID
        
        Returns:
            {
                "subscriptions": [...],  # 모든 구독권 (만료 포함)
                "vouchers": [...],       # 모든 금액권 (만료/소진 포함)
            }
        """
        return {
            'subscriptions': self.local_cache.get_member_subscriptions(member_id, include_all=True),
            'vouchers': self.local_cache.get_member_vouchers(member_id, include_all=True),
        }
    
    # =============================
    # 유틸리티
    # =============================
    
    def _validate_item(self, item: Dict) -> Dict:
        """개별 아이템 검증"""
        product_id = item.get('product_id')
        quantity = item.get('quantity', 1)
        device_uuid = item.get('device_uuid')
        
        product = self.local_cache.get_product(product_id)
        if not product:
            raise ValueError(f"상품을 찾을 수 없습니다: {product_id}")
        
        if not device_uuid:
            device_uuid = product.get('device_uuid')
        
        if not device_uuid:
            raise ValueError(f"상품 '{product['name']}'에 연결된 기기가 없습니다.")
        
        # 기기 온라인 확인
        device = self.local_cache.get_device(device_uuid)
        if device:
            last_heartbeat = device.get('last_heartbeat')
            if last_heartbeat:
                try:
                    hb_time = datetime.fromisoformat(last_heartbeat)
                    # timezone 처리
                    now = get_kst_now()
                    if hb_time.tzinfo is None:
                        from app.services.local_cache import KST
                        hb_time = KST.localize(hb_time)
                    if (now - hb_time) > timedelta(minutes=2):
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
    
    def get_inventory_status(self) -> Dict:
        """재고 현황 조회"""
        products = self.local_cache.get_products()
        
        inventory = {
            'categories': {},
            'total': {'total': 0, 'available': 0}
        }
        
        for product in products:
            category = product.get('category', 'other')
            device_uuid = product.get('device_uuid')
            
            stock = product.get('stock', 0)
            if device_uuid:
                device = self.local_cache.get_device(device_uuid)
                if device and device.get('stock') is not None:
                    stock = device['stock']
            
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
                'price': product.get('price', 1000),
                'stock': stock,
            })
            cat_data['available'] += stock
            cat_data['total'] += 1
            
            inventory['total']['available'] += stock
            inventory['total']['total'] += 1
        
        return inventory
