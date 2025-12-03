"""
메인 라우트 및 API 엔드포인트
"""
from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta

# 옵셔널 임포트
try:
    from app.services.rental_service import RentalService
except Exception as e:
    print(f"[Routes] RentalService 임포트 실패: {e}")
    RentalService = None

try:
    from app.services.local_cache import LocalCache
except Exception as e:
    print(f"[Routes] LocalCache 임포트 실패: {e}")
    LocalCache = None

main_bp = Blueprint('main', __name__)

# 서비스 인스턴스 (lazy 초기화)
_rental_service = None
_local_cache = None


def get_local_cache():
    """LocalCache 인스턴스 가져오기 (lazy 초기화)"""
    global _local_cache
    if _local_cache is None and LocalCache:
        try:
            _local_cache = LocalCache()
        except Exception as e:
            print(f"[Routes] LocalCache 초기화 실패: {e}")
    return _local_cache


def get_rental_service():
    """RentalService 인스턴스 가져오기 (lazy 초기화)"""
    global _rental_service
    if _rental_service is None and RentalService:
        try:
            from flask import current_app
            _rental_service = RentalService(get_local_cache())
            # 앱의 MQTT 서비스 주입 (중복 연결 방지)
            if hasattr(current_app, 'mqtt_service') and current_app.mqtt_service:
                _rental_service.set_mqtt_service(current_app.mqtt_service)
                print("[Routes] RentalService에 앱 MQTT 서비스 주입 완료")
        except Exception as e:
            print(f"[Routes] RentalService 초기화 실패: {e}")
    return _rental_service


# ========================================
# 페이지 라우트
# ========================================

@main_bp.route('/')
def index():
    """로그인 페이지 (홈)"""
    return render_template('pages/home.html')


@main_bp.route('/rental')
def rental():
    """상품 선택 + 장바구니 페이지"""
    return render_template('pages/rental.html')


@main_bp.route('/complete')
def complete():
    """대여 완료 페이지"""
    return render_template('pages/complete.html')


# ========================================
# 인증 API
# ========================================

@main_bp.route('/api/auth/phone', methods=['POST'])
def api_auth_phone():
    """
    전화번호로 회원 로그인
    
    Request:
        {"phone": "01012345678"}
    
    Response:
        {"success": true, "member": {...}} 또는
        {"success": false, "message": "..."}
    """
    data = request.json
    phone = data.get('phone', '').replace('-', '').strip()
    
    if not phone:
        return jsonify({'success': False, 'message': '전화번호를 입력해주세요.'}), 400
    
    if len(phone) < 10:
        return jsonify({'success': False, 'message': '올바른 전화번호를 입력해주세요.'}), 400
    
    local_cache = get_local_cache()
    
    if not local_cache:
        return jsonify({'success': False, 'message': '시스템 초기화 중입니다. 잠시 후 다시 시도해주세요.'}), 503
    
    # 전화번호로 회원 조회
    member = find_member_by_phone(local_cache, phone)
    
    if not member:
        return jsonify({
            'success': False, 
            'message': '등록되지 않은 전화번호입니다.'
        }), 404
    
    if member.get('status') != 'active':
        return jsonify({
            'success': False,
            'message': '비활성화된 회원입니다. 관리자에게 문의해주세요.'
        }), 403
    
    return jsonify({
        'success': True,
        'member': {
            'member_id': member['member_id'],
            'name': member['name'],
            'phone': member.get('phone', ''),
            'remaining_count': member['remaining_count'],
            'status': member['status'],
        }
    })


def find_member_by_phone(local_cache, phone):
    """전화번호로 회원 검색"""
    # 전화번호 정규화 (하이픈 제거)
    normalized_phone = phone.replace('-', '').strip()
    
    # 모든 회원 순회하며 전화번호 매칭
    for member_id, member in local_cache._members_cache.items():
        member_phone = member.get('phone', '').replace('-', '').strip()
        if member_phone == normalized_phone:
            return member
    
    return None


# ========================================
# 상품 API
# ========================================

@main_bp.route('/api/products', methods=['GET'])
def api_get_products():
    """
    상품 목록 조회 (기기 상태 포함)
    
    Response:
        {
            "products": [
                {
                    "product_id": "P-TOP-105",
                    "name": "운동복 상의 105",
                    "category": "top",
                    "size": "105",
                    "stock": 30,
                    "device_uuid": "FBOX-...",
                    "connected": true,
                    "online": true
                },
                ...
            ]
        }
    """
    local_cache = get_local_cache()
    
    if not local_cache:
        return jsonify({'products': []})
    
    products = local_cache.get_products()
    result = []
    
    for product in products:
        device_uuid = product.get('device_uuid')
        
        # 기기 연결 상태 확인
        connected = device_uuid is not None
        online = False
        stock = product.get('stock', 0)
        
        if device_uuid:
            # device_cache에서 실시간 상태 조회
            device = local_cache.get_device(device_uuid)
            if device:
                # heartbeat가 2분 이내면 online
                last_heartbeat = device.get('last_heartbeat')
                if last_heartbeat:
                    try:
                        hb_time = datetime.fromisoformat(last_heartbeat)
                        online = (datetime.now() - hb_time) < timedelta(minutes=2)
                    except:
                        pass
                
                # 실시간 재고로 업데이트
                if device.get('stock') is not None:
                    stock = device['stock']
        
        result.append({
            'product_id': product['product_id'],
            'name': product['name'],
            'category': product['category'],
            'size': product.get('size', ''),
            'stock': stock,
            'device_uuid': device_uuid or '',
            'connected': connected,
            'online': online,
            'display_order': product.get('display_order', 0),
        })
    
    # display_order로 정렬
    result.sort(key=lambda x: x['display_order'])
    
    return jsonify({'products': result})


# ========================================
# 대여 API
# ========================================

@main_bp.route('/api/rental/process', methods=['POST'])
def api_process_rental():
    """
    대여 처리
    
    Request:
        {
            "member_id": "A001",
            "items": [
                {"product_id": "P-TOP-105", "quantity": 1, "device_uuid": "FBOX-..."},
                ...
            ]
        }
    
    Response:
        {
            "success": true,
            "remaining_count": 7,
            "message": "대여가 완료되었습니다."
        }
    """
    data = request.json
    member_id = data.get('member_id')
    items = data.get('items', [])
    
    if not member_id:
        return jsonify({'success': False, 'message': '회원 정보가 없습니다.'}), 400
    
    if not items:
        return jsonify({'success': False, 'message': '선택된 상품이 없습니다.'}), 400
    
    rental_service = get_rental_service()
    
    if not rental_service:
        return jsonify({'success': False, 'message': '시스템 초기화 중입니다. 잠시 후 다시 시도해주세요.'}), 503
    
    try:
        result = rental_service.process_rental(member_id, items)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        print(f"[API] 대여 처리 오류: {e}")
        return jsonify({'success': False, 'message': '대여 처리 중 오류가 발생했습니다.'}), 500


# ========================================
# 재고 API (기존)
# ========================================

@main_bp.route('/api/inventory', methods=['GET'])
def api_get_inventory():
    """재고 현황 조회 (기존 API 유지)"""
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'categories': {}, 'total': {'total': 0, 'available': 0}})
    inventory = rental_service.get_inventory_status()
    return jsonify(inventory)
