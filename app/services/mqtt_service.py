"""
MQTT 통신 서비스

ESP32 F-BOX 기기들과 MQTT 프로토콜로 통신
- 명령 전송 (DISPENSE, SET_STOCK, LOCK 등)
- 이벤트 수신 (dispense_complete, heartbeat 등)
"""

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
from typing import Callable, Dict, Optional
from threading import Thread


class MQTTService:
    """MQTT 통신 관리 클래스"""
    
    def __init__(self, broker_host: str = 'localhost', broker_port: int = 1883):
        """
        초기화
        
        Args:
            broker_host: MQTT 브로커 주소
            broker_port: MQTT 브로커 포트
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        self.client = mqtt.Client(client_id='fbox-server', clean_session=True)
        self.connected = False
        
        # 이벤트 핸들러 등록
        self.event_handlers: Dict[str, Callable] = {}
        
        # MQTT 클라이언트 콜백 설정
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        print(f"[MQTT] 초기화: {broker_host}:{broker_port}")
    
    def connect(self) -> bool:
        """
        MQTT 브로커에 연결
        
        Returns:
            성공 여부
        """
        try:
            print(f"[MQTT] 연결 시도: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            
            # 백그라운드 스레드에서 루프 실행
            self.client.loop_start()
            
            # 연결 대기 (최대 5초)
            timeout = 5
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                print("[MQTT] ✓ 연결 성공")
                return True
            else:
                print("[MQTT] ✗ 연결 실패 (타임아웃)")
                return False
                
        except Exception as e:
            print(f"[MQTT] ✗ 연결 실패: {e}")
            return False
    
    def disconnect(self):
        """MQTT 브로커 연결 해제"""
        self.client.loop_stop()
        self.client.disconnect()
        print("[MQTT] 연결 해제")
    
    def _on_connect(self, client, userdata, flags, rc):
        """연결 성공 콜백"""
        if rc == 0:
            self.connected = True
            print("[MQTT] 브로커 연결됨")
            
            # 모든 F-BOX 기기의 상태 토픽 구독
            self.subscribe_all_devices()
        else:
            self.connected = False
            print(f"[MQTT] 연결 실패: RC={rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """연결 해제 콜백"""
        self.connected = False
        if rc != 0:
            print(f"[MQTT] 예기치 않은 연결 해제: RC={rc}")
        else:
            print("[MQTT] 정상 연결 해제")
    
    def _on_message(self, client, userdata, msg):
        """메시지 수신 콜백"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))
            
            # 토픽에서 device_id 추출
            # 예: fbox/FBOX-UPPER-105/status → FBOX-UPPER-105
            parts = topic.split('/')
            if len(parts) >= 3 and parts[0] == 'fbox':
                device_id = parts[1]
                topic_type = parts[2]
                
                if topic_type == 'status':
                    # 이벤트 처리
                    self._handle_event(device_id, payload)
                else:
                    print(f"[MQTT] 알 수 없는 토픽: {topic}")
            
        except json.JSONDecodeError as e:
            print(f"[MQTT] JSON 파싱 실패: {e}")
        except Exception as e:
            print(f"[MQTT] 메시지 처리 오류: {e}")
    
    def _handle_event(self, device_id: str, payload: Dict):
        """
        ESP32로부터 수신한 이벤트 처리
        
        Args:
            device_id: 기기 ID
            payload: 이벤트 페이로드
        """
        event_type = payload.get('event')
        
        if not event_type:
            print(f"[MQTT] 이벤트 타입 없음: {payload}")
            return
        
        print(f"[MQTT] ← {device_id}: {event_type}")
        
        # 등록된 핸들러 실행
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type](device_id, payload)
            except Exception as e:
                print(f"[MQTT] 핸들러 실행 오류 ({event_type}): {e}")
        else:
            print(f"[MQTT] 미등록 이벤트: {event_type}")
    
    # =============================
    # 구독 관리
    # =============================
    
    def subscribe_all_devices(self):
        """모든 F-BOX 기기의 상태 토픽 구독"""
        topic = 'fbox/+/status'
        self.client.subscribe(topic, qos=0)
        print(f"[MQTT] Subscribe: {topic}")
    
    def subscribe_device(self, device_id: str):
        """특정 기기의 상태 토픽 구독"""
        topic = f'fbox/{device_id}/status'
        self.client.subscribe(topic, qos=0)
        print(f"[MQTT] Subscribe: {topic}")
    
    # =============================
    # 명령 전송
    # =============================
    
    def send_command(self, device_id: str, command: str, **params) -> bool:
        """
        ESP32에 명령 전송
        
        Args:
            device_id: 기기 ID
            command: 명령 (DISPENSE, STATUS, SET_STOCK 등)
            **params: 추가 파라미터
        
        Returns:
            성공 여부
        """
        if not self.connected:
            print("[MQTT] 브로커 미연결 상태")
            return False
        
        topic = f'fbox/{device_id}/cmd'
        payload = {
            'cmd': command,
            'timestamp': int(datetime.now().timestamp()),
            **params
        }
        
        try:
            result = self.client.publish(topic, json.dumps(payload), qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] → {device_id}: {command} {params}")
                return True
            else:
                print(f"[MQTT] 전송 실패: RC={result.rc}")
                return False
                
        except Exception as e:
            print(f"[MQTT] 명령 전송 오류: {e}")
            return False
    
    def dispense(self, device_id: str) -> bool:
        """물품 토출 명령"""
        return self.send_command(device_id, 'DISPENSE')
    
    def get_status(self, device_id: str) -> bool:
        """상태 조회 명령"""
        return self.send_command(device_id, 'STATUS')
    
    def set_stock(self, device_id: str, stock: int) -> bool:
        """재고 설정 명령"""
        return self.send_command(device_id, 'SET_STOCK', stock=stock)
    
    def stop(self, device_id: str) -> bool:
        """긴급 정지 명령"""
        return self.send_command(device_id, 'STOP')
    
    def lock(self, device_id: str) -> bool:
        """기기 잠금 명령 (점검 모드)"""
        return self.send_command(device_id, 'LOCK')
    
    def unlock(self, device_id: str) -> bool:
        """기기 잠금 해제 명령"""
        return self.send_command(device_id, 'UNLOCK')
    
    def home(self, device_id: str) -> bool:
        """강제 홈 복귀 명령"""
        return self.send_command(device_id, 'HOME')
    
    def reboot(self, device_id: str) -> bool:
        """재시작 명령"""
        return self.send_command(device_id, 'REBOOT')
    
    def clear_error(self, device_id: str) -> bool:
        """에러 초기화 명령"""
        return self.send_command(device_id, 'CLEAR_ERROR')
    
    # =============================
    # 이벤트 핸들러 등록
    # =============================
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """
        이벤트 핸들러 등록
        
        Args:
            event_type: 이벤트 타입 (예: 'boot_complete', 'dispense_complete')
            handler: 핸들러 함수 (device_id, payload를 인자로 받음)
        """
        self.event_handlers[event_type] = handler
        print(f"[MQTT] 핸들러 등록: {event_type}")
    
    def unregister_event_handler(self, event_type: str):
        """이벤트 핸들러 등록 해제"""
        if event_type in self.event_handlers:
            del self.event_handlers[event_type]
            print(f"[MQTT] 핸들러 해제: {event_type}")
    
    # =============================
    # 유틸리티
    # =============================
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.connected
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# =============================
# 기본 이벤트 핸들러 예시
# =============================

def handle_boot_complete(device_id: str, payload: Dict):
    """부팅 완료 이벤트 핸들러"""
    print(f"[Event] {device_id} 부팅 완료:")
    print(f"  - Size: {payload.get('size')}")
    print(f"  - Stock: {payload.get('stock')}")
    print(f"  - IP: {payload.get('ipAddress')}")
    print(f"  - Firmware: {payload.get('firmwareVersion')}")


def handle_heartbeat(device_id: str, payload: Dict):
    """하트비트 이벤트 핸들러"""
    # 조용히 처리 (로그 최소화)
    pass


def handle_dispense_complete(device_id: str, payload: Dict):
    """토출 완료 이벤트 핸들러"""
    stock = payload.get('stock')
    print(f"[Event] {device_id} 토출 완료: 재고 {stock}개")


def handle_dispense_failed(device_id: str, payload: Dict):
    """토출 실패 이벤트 핸들러"""
    reason = payload.get('reason')
    print(f"[Event] {device_id} 토출 실패: {reason}")


def handle_door_opened(device_id: str, payload: Dict):
    """문 열림 이벤트 핸들러"""
    print(f"[Event] {device_id} 문 열림 (재고 보충 시작?)")


def handle_door_closed(device_id: str, payload: Dict):
    """문 닫힘 이벤트 핸들러"""
    stock = payload.get('stock')
    sensor_available = payload.get('sensorAvailable', False)
    print(f"[Event] {device_id} 문 닫힘: 재고 {stock}개 (센서: {'O' if sensor_available else 'X'})")


def handle_stock_updated(device_id: str, payload: Dict):
    """재고 업데이트 이벤트 핸들러"""
    stock = payload.get('stock')
    source = payload.get('source', 'unknown')
    needs_verification = payload.get('needsVerification', False)
    
    print(f"[Event] {device_id} 재고 업데이트: {stock}개 (출처: {source})")
    if needs_verification:
        print(f"  ⚠️  관리자 확인 필요")


def handle_stock_low(device_id: str, payload: Dict):
    """재고 부족 이벤트 핸들러"""
    stock = payload.get('stock')
    print(f"[Event] {device_id} ⚠️  재고 부족: {stock}개")


def handle_stock_empty(device_id: str, payload: Dict):
    """재고 없음 이벤트 핸들러"""
    print(f"[Event] {device_id} ❌ 재고 없음")


def handle_error(device_id: str, payload: Dict):
    """에러 이벤트 핸들러"""
    error_code = payload.get('errorCode')
    error_message = payload.get('errorMessage')
    print(f"[Event] {device_id} ❌ 에러: [{error_code}] {error_message}")


# =============================
# 기본 핸들러 등록 유틸리티
# =============================

def register_default_handlers(mqtt_service: MQTTService, local_cache=None):
    """
    기본 이벤트 핸들러 등록
    
    Args:
        mqtt_service: MQTT 서비스 인스턴스
        local_cache: LocalCache 인스턴스 (선택, 재고 동기화용)
    """
    # 정상 작동 이벤트
    mqtt_service.register_event_handler('boot_complete', handle_boot_complete)
    mqtt_service.register_event_handler('heartbeat', handle_heartbeat)
    mqtt_service.register_event_handler('dispense_complete', handle_dispense_complete)
    mqtt_service.register_event_handler('door_opened', handle_door_opened)
    mqtt_service.register_event_handler('door_closed', handle_door_closed)
    mqtt_service.register_event_handler('stock_updated', handle_stock_updated)
    
    # 경고 이벤트
    mqtt_service.register_event_handler('stock_low', handle_stock_low)
    mqtt_service.register_event_handler('stock_empty', handle_stock_empty)
    
    # 에러 이벤트
    mqtt_service.register_event_handler('dispense_failed', handle_dispense_failed)
    mqtt_service.register_event_handler('error', handle_error)
    
    # LocalCache와 연동하는 핸들러 (선택)
    if local_cache:
        def handle_heartbeat_with_cache(device_id: str, payload: Dict):
            local_cache.update_heartbeat(device_id)
        
        def handle_dispense_with_cache(device_id: str, payload: Dict):
            stock = payload.get('stock')
            product = local_cache.get_product_by_device(device_id)
            if product:
                local_cache.update_product_stock(product['product_id'], stock)
            local_cache.update_device_status(device_id, stock=stock)
        
        mqtt_service.register_event_handler('heartbeat', handle_heartbeat_with_cache)
        mqtt_service.register_event_handler('dispense_complete', handle_dispense_with_cache)
    
    print("[MQTT] 기본 핸들러 등록 완료")


# =============================
# 사용 예시
# =============================

if __name__ == '__main__':
    # MQTT 서비스 생성 및 연결
    mqtt_service = MQTTService(broker_host='localhost', broker_port=1883)
    
    if mqtt_service.connect():
        # 기본 핸들러 등록
        register_default_handlers(mqtt_service)
        
        # 상태 조회 명령 전송
        mqtt_service.get_status('FBOX-UPPER-105')
        
        # 토출 명령 전송
        mqtt_service.dispense('FBOX-UPPER-105')
        
        # 계속 실행
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            mqtt_service.disconnect()

