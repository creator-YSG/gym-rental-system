"""
기기 제어 API
관리자용 F-BOX 기기 제어 엔드포인트
"""

from flask import Blueprint, jsonify, request

api_device_bp = Blueprint('api_device', __name__, url_prefix='/api/devices')


def get_mqtt_service():
    """MQTT 서비스 가져오기"""
    from app import get_mqtt_service as _get_mqtt
    return _get_mqtt()


def get_local_cache():
    """LocalCache 가져오기"""
    from app import get_local_cache as _get_cache
    return _get_cache()


# =============================
# 기기 상태 조회
# =============================

@api_device_bp.route('', methods=['GET'])
def list_devices():
    """
    모든 기기 목록 조회
    
    Response:
        200 OK
        {
          "status": "ok",
          "devices": [
            {
              "device_id": "FBOX-UPPER-105",
              "size": "105",
              "stock": 15,
              "door_state": "closed",
              "locked": false,
              "last_heartbeat": "2024-12-02T10:00:00"
            },
            ...
          ]
        }
    """
    cache = get_local_cache()
    if not cache:
        return jsonify({'status': 'error', 'message': 'LocalCache not available'}), 503
    
    devices = cache.get_all_devices()
    
    return jsonify({
        'status': 'ok',
        'devices': devices
    }), 200


@api_device_bp.route('/<device_id>', methods=['GET'])
def get_device(device_id: str):
    """
    특정 기기 상태 조회
    
    Response:
        200 OK
        {
          "status": "ok",
          "device_id": "FBOX-UPPER-105",
          ...
        }
    """
    cache = get_local_cache()
    if not cache:
        return jsonify({'status': 'error', 'message': 'LocalCache not available'}), 503
    
    device = cache.get_device(device_id)
    if device:
        return jsonify({'status': 'ok', **device}), 200
    else:
        return jsonify({'status': 'error', 'message': f'기기를 찾을 수 없습니다: {device_id}'}), 404


@api_device_bp.route('/<device_id>/events', methods=['GET'])
def get_device_events(device_id: str):
    """
    기기 이벤트 이력 조회
    
    Query Parameters:
        limit: 조회 개수 (기본 50)
    
    Response:
        200 OK
        {
          "status": "ok",
          "events": [...]
        }
    """
    cache = get_local_cache()
    if not cache:
        return jsonify({'status': 'error', 'message': 'LocalCache not available'}), 503
    
    limit = request.args.get('limit', 50, type=int)
    events = cache.get_recent_events(device_id, limit)
    
    return jsonify({
        'status': 'ok',
        'events': events
    }), 200


# =============================
# 기기 명령 전송
# =============================

@api_device_bp.route('/<device_id>/command', methods=['POST'])
def send_command(device_id: str):
    """
    기기에 명령 전송
    
    Request Body:
        {
          "command": "DISPENSE" | "STATUS" | "SET_STOCK" | "STOP" | "LOCK" | "UNLOCK" | "HOME" | "REBOOT" | "CLEAR_ERROR",
          "stock": 20  // SET_STOCK일 때만 필요
        }
    
    Response:
        200 OK
        {
          "status": "ok",
          "message": "명령 전송 완료"
        }
    """
    mqtt = get_mqtt_service()
    if not mqtt:
        return jsonify({'status': 'error', 'message': 'MQTT service not available'}), 503
    
    if not mqtt.is_connected():
        return jsonify({'status': 'error', 'message': 'MQTT broker not connected'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Request body required'}), 400
    
    command = data.get('command')
    if not command:
        return jsonify({'status': 'error', 'message': 'command field required'}), 400
    
    # 명령 실행
    success = False
    message = ''
    
    if command == 'DISPENSE':
        success = mqtt.dispense(device_id)
        message = '토출 명령 전송'
        
    elif command == 'STATUS':
        success = mqtt.get_status(device_id)
        message = '상태 조회 명령 전송'
        
    elif command == 'SET_STOCK':
        stock = data.get('stock')
        if stock is None:
            return jsonify({'status': 'error', 'message': 'stock field required for SET_STOCK'}), 400
        success = mqtt.set_stock(device_id, int(stock))
        message = f'재고 설정 명령 전송: {stock}개'
        
    elif command == 'STOP':
        success = mqtt.stop(device_id)
        message = '긴급 정지 명령 전송'
        
    elif command == 'LOCK':
        success = mqtt.lock(device_id)
        message = '잠금 명령 전송'
        
    elif command == 'UNLOCK':
        success = mqtt.unlock(device_id)
        message = '잠금 해제 명령 전송'
        
    elif command == 'HOME':
        success = mqtt.home(device_id)
        message = '홈 복귀 명령 전송'
        
    elif command == 'REBOOT':
        success = mqtt.reboot(device_id)
        message = '재부팅 명령 전송'
        
    elif command == 'CLEAR_ERROR':
        success = mqtt.clear_error(device_id)
        message = '에러 초기화 명령 전송'
        
    else:
        return jsonify({'status': 'error', 'message': f'Unknown command: {command}'}), 400
    
    if success:
        return jsonify({'status': 'ok', 'message': message}), 200
    else:
        return jsonify({'status': 'error', 'message': '명령 전송 실패'}), 500


# =============================
# 편의 API (빠른 접근용)
# =============================

@api_device_bp.route('/<device_id>/dispense', methods=['POST'])
def dispense(device_id: str):
    """토출 명령 (바로가기)"""
    mqtt = get_mqtt_service()
    if not mqtt or not mqtt.is_connected():
        return jsonify({'status': 'error', 'message': 'MQTT not available'}), 503
    
    if mqtt.dispense(device_id):
        return jsonify({'status': 'ok', 'message': '토출 명령 전송'}), 200
    else:
        return jsonify({'status': 'error', 'message': '명령 전송 실패'}), 500


@api_device_bp.route('/<device_id>/lock', methods=['POST'])
def lock_device(device_id: str):
    """기기 잠금 (바로가기)"""
    mqtt = get_mqtt_service()
    if not mqtt or not mqtt.is_connected():
        return jsonify({'status': 'error', 'message': 'MQTT not available'}), 503
    
    if mqtt.lock(device_id):
        return jsonify({'status': 'ok', 'message': '잠금 완료'}), 200
    else:
        return jsonify({'status': 'error', 'message': '명령 전송 실패'}), 500


@api_device_bp.route('/<device_id>/unlock', methods=['POST'])
def unlock_device(device_id: str):
    """기기 잠금 해제 (바로가기)"""
    mqtt = get_mqtt_service()
    if not mqtt or not mqtt.is_connected():
        return jsonify({'status': 'error', 'message': 'MQTT not available'}), 503
    
    if mqtt.unlock(device_id):
        return jsonify({'status': 'ok', 'message': '잠금 해제 완료'}), 200
    else:
        return jsonify({'status': 'error', 'message': '명령 전송 실패'}), 500


@api_device_bp.route('/<device_id>/stock', methods=['PUT'])
def set_stock(device_id: str):
    """
    재고 설정 (바로가기)
    
    Request Body:
        {"stock": 20}
    """
    mqtt = get_mqtt_service()
    if not mqtt or not mqtt.is_connected():
        return jsonify({'status': 'error', 'message': 'MQTT not available'}), 503
    
    data = request.get_json()
    stock = data.get('stock') if data else None
    
    if stock is None:
        return jsonify({'status': 'error', 'message': 'stock field required'}), 400
    
    if mqtt.set_stock(device_id, int(stock)):
        return jsonify({'status': 'ok', 'message': f'재고 설정: {stock}개'}), 200
    else:
        return jsonify({'status': 'error', 'message': '명령 전송 실패'}), 500


# =============================
# MQTT 상태 확인
# =============================

@api_device_bp.route('/mqtt/status', methods=['GET'])
def mqtt_status():
    """
    MQTT 연결 상태 확인
    
    Response:
        200 OK
        {
          "status": "ok",
          "connected": true,
          "broker": "localhost:1883"
        }
    """
    mqtt = get_mqtt_service()
    
    if mqtt:
        return jsonify({
            'status': 'ok',
            'connected': mqtt.is_connected(),
            'broker': f'{mqtt.broker_host}:{mqtt.broker_port}'
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'connected': False,
            'message': 'MQTT service not initialized'
        }), 503


@api_device_bp.route('/mqtt/reconnect', methods=['POST'])
def mqtt_reconnect():
    """MQTT 재연결 시도"""
    mqtt = get_mqtt_service()
    
    if not mqtt:
        return jsonify({'status': 'error', 'message': 'MQTT service not initialized'}), 503
    
    if mqtt.connect():
        return jsonify({'status': 'ok', 'message': 'MQTT 재연결 성공'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'MQTT 재연결 실패'}), 500

