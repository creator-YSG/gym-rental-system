"""
메인 라우트 및 API 엔드포인트 (금액권/구독권 기반)
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
    """LocalCache 인스턴스 가져오기"""
    global _local_cache
    if _local_cache is None and LocalCache:
        try:
            _local_cache = LocalCache()
        except Exception as e:
            print(f"[Routes] LocalCache 초기화 실패: {e}")
    return _local_cache


def get_rental_service():
    """RentalService 인스턴스 가져오기"""
    global _rental_service
    if _rental_service is None and RentalService:
        try:
            from flask import current_app
            _rental_service = RentalService(get_local_cache())
            if hasattr(current_app, 'mqtt_service') and current_app.mqtt_service:
                _rental_service.set_mqtt_service(current_app.mqtt_service)
                print(f"[Routes] RentalService MQTT 연결됨")
            else:
                print(f"[Routes] RentalService MQTT 없음!")
        except Exception as e:
            import traceback
            print(f"[Routes] RentalService 초기화 실패: {e}")
            traceback.print_exc()
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

def _get_member_login_data(member_id):
    """
    회원 로그인 시 필요한 정보 조회 (공통 함수)
    
    Args:
        member_id: 회원 ID
    
    Returns:
        dict: 회원 정보 또는 None
    """
    local_cache = get_local_cache()
    
    if not local_cache:
        return None
    
    member = local_cache.get_member(member_id)
    
    if not member:
        return None
    
    if member.get('status') != 'active':
        return None
    
    # 금액권/구독권 요약 정보
    total_balance = local_cache.get_total_balance(member_id)
    active_vouchers = local_cache.get_active_vouchers(member_id)
    active_subscriptions = local_cache.get_active_subscriptions(member_id)
    
    # 구독권 상세 정보 (카테고리별 잔여 횟수, D-day)
    subscription_info = None
    if active_subscriptions:
        sub = active_subscriptions[0]  # 첫 번째 활성 구독권
        remaining_by_cat = {}
        for cat in ['top', 'pants', 'towel']:
            remaining_by_cat[cat] = local_cache.get_subscription_remaining(sub['subscription_id'], cat)
        
        # D-day 계산
        valid_until = sub.get('valid_until', '')
        days_left = 0
        if valid_until:
            try:
                end_date = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                now = datetime.now(end_date.tzinfo) if end_date.tzinfo else datetime.now()
                days_left = (end_date - now).days
            except:
                pass
        
        subscription_info = {
            'subscription_id': sub['subscription_id'],
            'product_name': sub.get('product_name', sub.get('subscription_product_id', '')),
            'remaining_by_category': remaining_by_cat,
            'days_left': days_left,
            'valid_until': valid_until,
        }
    
    return {
        'member_id': member_id,
        'name': member['name'],
        'phone': member.get('phone', ''),
        'status': member['status'],
        'total_balance': total_balance,
        'active_vouchers_count': len(active_vouchers),
        'active_subscriptions_count': len(active_subscriptions),
        'subscription_info': subscription_info,
    }


@main_bp.route('/api/auth/phone', methods=['POST'])
def api_auth_phone():
    """
    전화번호로 회원 로그인
    
    Request:
        {"phone": "01012345678"}
    
    Response:
        {
            "success": true,
            "member": {
                "member_id": "A001",
                "name": "홍길동",
                "phone": "01012345678",
                "status": "active",
                "total_balance": 50000,           // 총 금액권 잔액
                "active_vouchers_count": 2,       // 활성 금액권 수
                "active_subscriptions_count": 1   // 활성 구독권 수
            }
        }
    """
    data = request.json
    phone = data.get('phone', '').replace('-', '').strip()
    
    if not phone:
        return jsonify({'success': False, 'message': '전화번호를 입력해주세요.'}), 400
    
    if len(phone) < 10:
        return jsonify({'success': False, 'message': '올바른 전화번호를 입력해주세요.'}), 400
    
    local_cache = get_local_cache()
    
    if not local_cache:
        return jsonify({'success': False, 'message': '시스템 초기화 중입니다.'}), 503
    
    member = local_cache.get_member_by_phone(phone)
    
    if not member:
        return jsonify({'success': False, 'message': '등록되지 않은 전화번호입니다.'}), 404
    
    if member.get('status') != 'active':
        return jsonify({'success': False, 'message': '비활성화된 회원입니다.'}), 403
    
    member_id = member['member_id']
    member_data = _get_member_login_data(member_id)
    
    if not member_data:
        return jsonify({'success': False, 'message': '회원 정보 조회 실패'}), 500
    
    return jsonify({
        'success': True,
        'member': member_data
    })


@main_bp.route('/api/auth/member_id', methods=['POST'])
def api_auth_member_id():
    """
    member_id로 회원 로그인 (NFC 로그인용)
    
    Request:
        {"member_id": "A001"}
    
    Response:
        {
            "success": true,
            "member": {
                "member_id": "A001",
                "name": "홍길동",
                "phone": "01012345678",
                "status": "active",
                "total_balance": 50000,
                "active_vouchers_count": 2,
                "active_subscriptions_count": 1
            }
        }
    """
    data = request.json
    member_id = data.get('member_id', '').strip()
    
    if not member_id:
        return jsonify({'success': False, 'message': '회원 ID가 없습니다.'}), 400
    
    member_data = _get_member_login_data(member_id)
    
    if not member_data:
        return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없거나 비활성화된 회원입니다.'}), 404
    
    return jsonify({
        'success': True,
        'member': member_data
    })


# ========================================
# 상품 API
# ========================================

@main_bp.route('/api/products', methods=['GET'])
def api_get_products():
    """
    상품 목록 조회 (기기 상태 + 가격 포함)
    
    Response:
        {
            "products": [
                {
                    "product_id": "P-TOP-105",
                    "name": "운동복 상의 105",
                    "category": "top",
                    "size": "105",
                    "price": 1000,
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
        connected = device_uuid is not None
        online = False
        stock = product.get('stock', 0)
        
        if device_uuid:
            device = local_cache.get_device(device_uuid)
            if device:
                last_heartbeat = device.get('last_heartbeat')
                if last_heartbeat:
                    try:
                        hb_time = datetime.fromisoformat(last_heartbeat)
                        if hb_time.tzinfo:
                            hb_time = hb_time.replace(tzinfo=None)
                        online = (datetime.now() - hb_time) < timedelta(minutes=2)
                    except:
                        pass
                
                if device.get('stock') is not None:
                    stock = device['stock']
        
        result.append({
            'product_id': product['product_id'],
            'name': product['name'],
            'category': product['category'],
            'size': product.get('size', ''),
            'price': product.get('price', 1000),
            'stock': stock,
            'device_uuid': device_uuid or '',
            'connected': connected,
            'online': online,
            'display_order': product.get('display_order', 0),
        })
    
    result.sort(key=lambda x: x['display_order'])
    
    return jsonify({'products': result})


# ========================================
# 결제 수단 API
# ========================================

@main_bp.route('/api/payment-methods/<member_id>', methods=['GET'])
def api_get_payment_methods(member_id):
    """
    사용 가능한 결제 수단 조회
    
    Query params:
        category: 카테고리 (구독권 잔여 횟수 확인용)
    
    Response:
        {
            "subscriptions": [
                {
                    "subscription_id": 1,
                    "product_name": "3개월 기본 이용권",
                    "valid_until": "2025-03-01",
                    "remaining_today": 1,           // category 지정 시
                    "remaining_by_category": {...}  // category 미지정 시
                },
                ...
            ],
            "vouchers": [
                {
                    "voucher_id": 1,
                    "product_name": "10만원 금액권",
                    "remaining_amount": 45000,
                    "valid_until": "2025-12-01"
                },
                ...
            ],
            "total_balance": 45000
        }
    """
    category = request.args.get('category')
    
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'subscriptions': [], 'vouchers': [], 'total_balance': 0})
    
    result = rental_service.get_available_payment_methods(member_id, category)
    return jsonify(result)


@main_bp.route('/api/member/<member_id>/cards', methods=['GET'])
def api_get_member_cards(member_id):
    """
    회원의 모든 카드 조회 (마이페이지용)
    
    Response:
        {
            "subscriptions": [...],  // 모든 구독권 (만료 포함)
            "vouchers": [...]        // 모든 금액권 (만료/소진 포함)
        }
    """
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'subscriptions': [], 'vouchers': []})
    
    result = rental_service.get_member_cards(member_id)
    return jsonify(result)


# ========================================
# 대여 API
# ========================================

@main_bp.route('/api/rental/calculate', methods=['POST'])
def api_calculate_rental():
    """
    대여 비용 계산
    
    Request:
        {
            "items": [{"product_id": "P-TOP-105", "quantity": 1}, ...]
        }
    
    Response:
        {"total_amount": 2000}
    """
    data = request.json
    items = data.get('items', [])
    
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'total_amount': 0})
    
    total = rental_service.calculate_rental_cost(items)
    return jsonify({'total_amount': total})


@main_bp.route('/api/rental/subscription', methods=['POST'])
def api_rental_with_subscription():
    """
    구독권으로 대여 처리
    
    Request:
        {
            "member_id": "A001",
            "subscription_id": 1,
            "payment_password": "123456",
            "items": [
                {"product_id": "P-TOP-105", "quantity": 1, "device_uuid": "FBOX-..."},
                ...
            ]
        }
    
    Response:
        {
            "success": true,
            "message": "대여 완료",
            "payment_type": "subscription",
            "dispense_results": [...]
        }
    """
    data = request.json
    member_id = data.get('member_id')
    subscription_id = data.get('subscription_id')
    payment_password = data.get('payment_password')
    items = data.get('items', [])
    
    if not member_id:
        return jsonify({'success': False, 'message': '회원 정보가 없습니다.'}), 400
    if not subscription_id:
        return jsonify({'success': False, 'message': '구독권을 선택해주세요.'}), 400
    if not items:
        return jsonify({'success': False, 'message': '선택된 상품이 없습니다.'}), 400
    if not payment_password:
        return jsonify({'success': False, 'message': '결제 비밀번호를 입력해주세요.'}), 400
    
    # 결제 비밀번호 검증
    local_cache = get_local_cache()
    if local_cache:
        is_valid, msg = local_cache.verify_payment_password(member_id, payment_password)
        if not is_valid:
            return jsonify({'success': False, 'message': msg}), 401
    
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'success': False, 'message': '시스템 초기화 중입니다.'}), 503
    
    try:
        print(f"[API] 구독권 대여 요청: member={member_id}, subscription_id={subscription_id}, items={items}")
        result = rental_service.process_rental_with_subscription(member_id, items, subscription_id)
        print(f"[API] 구독권 대여 결과: {result}")
        return jsonify(result)
    except ValueError as e:
        print(f"[API] 구독권 대여 ValueError: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        import traceback
        print(f"[API] 구독권 대여 오류: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '대여 처리 중 오류가 발생했습니다.'}), 500


@main_bp.route('/api/rental/voucher', methods=['POST'])
def api_rental_with_voucher():
    """
    금액권으로 대여 처리 (쪼개기 지원)
    
    Request:
        {
            "member_id": "A001",
            "payment_password": "123456",
            "items": [
                {"product_id": "P-TOP-105", "quantity": 1, "device_uuid": "FBOX-..."},
                ...
            ],
            "voucher_selections": [
                {"voucher_id": 1, "amount": 500},
                {"voucher_id": 2, "amount": 500}
            ]
        }
    
    Response:
        {
            "success": true,
            "message": "대여 완료 (1000원 차감)",
            "payment_type": "voucher",
            "total_amount": 1000,
            "dispense_results": [...]
        }
    """
    data = request.json
    member_id = data.get('member_id')
    payment_password = data.get('payment_password')
    items = data.get('items', [])
    voucher_selections = data.get('voucher_selections', [])
    
    if not member_id:
        return jsonify({'success': False, 'message': '회원 정보가 없습니다.'}), 400
    if not items:
        return jsonify({'success': False, 'message': '선택된 상품이 없습니다.'}), 400
    if not voucher_selections:
        return jsonify({'success': False, 'message': '금액권을 선택해주세요.'}), 400
    if not payment_password:
        return jsonify({'success': False, 'message': '결제 비밀번호를 입력해주세요.'}), 400
    
    # 결제 비밀번호 검증
    local_cache = get_local_cache()
    if local_cache:
        is_valid, msg = local_cache.verify_payment_password(member_id, payment_password)
        if not is_valid:
            return jsonify({'success': False, 'message': msg}), 401
    
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'success': False, 'message': '시스템 초기화 중입니다.'}), 503
    
    try:
        print(f"[API] 금액권 대여 요청: member={member_id}, items={items}, vouchers={voucher_selections}")
        result = rental_service.process_rental_with_vouchers(member_id, items, voucher_selections)
        print(f"[API] 금액권 대여 결과: {result}")
        return jsonify(result)
    except ValueError as e:
        print(f"[API] 금액권 대여 ValueError: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        import traceback
        print(f"[API] 금액권 대여 오류: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '대여 처리 중 오류가 발생했습니다.'}), 500


# ========================================
# 재고 API
# ========================================

@main_bp.route('/api/inventory', methods=['GET'])
def api_get_inventory():
    """재고 현황 조회"""
    rental_service = get_rental_service()
    if not rental_service:
        return jsonify({'categories': {}, 'total': {'total': 0, 'available': 0}})
    inventory = rental_service.get_inventory_status()
    return jsonify(inventory)


@main_bp.route('/api/nfc/poll', methods=['GET'])
def api_nfc_poll():
    """NFC 이벤트 폴링 (큐에서 가져오기)
    
    Response:
        성공: {"has_event": true, "member_id": "...", "name": "...", ...}
        없음: {"has_event": false}
    """
    from flask import current_app
    import queue
    
    try:
        nfc_queue = getattr(current_app, 'nfc_queue', None)
        
        if nfc_queue:
            try:
                # 큐에서 데이터 가져오기 (non-blocking)
                nfc_data = nfc_queue.get_nowait()
                
                if nfc_data.get('success'):
                    return jsonify({
                        'has_event': True,
                        'success': True,
                        'member_id': nfc_data.get('member_id'),
                        'name': nfc_data.get('name'),
                        'locker_number': nfc_data.get('locker_number'),
                        'nfc_uid': nfc_data.get('nfc_uid')
                    })
                else:
                    return jsonify({
                        'has_event': True,
                        'success': False,
                        'message': nfc_data.get('message', '알 수 없는 오류'),
                        'nfc_uid': nfc_data.get('nfc_uid')
                    })
            except queue.Empty:
                # 큐가 비어있음
                return jsonify({'has_event': False})
        else:
            return jsonify({'has_event': False})
            
    except Exception as e:
        print(f'[API] NFC 폴링 오류: {e}')
        return jsonify({'has_event': False, 'error': str(e)})


@main_bp.route('/api/test/nfc-inject', methods=['POST'])
def api_test_nfc_inject():
    """테스트용: NFC 이벤트 큐에 직접 주입
    
    Request:
        {"nfc_uid": "5A41B914524189"}
    
    Response:
        {"success": true, "member": {...}}
    """
    from flask import current_app
    import queue
    
    data = request.json
    nfc_uid = data.get('nfc_uid', '').strip()
    
    if not nfc_uid:
        return jsonify({'success': False, 'message': 'NFC UID가 필요합니다.'}), 400
    
    # Locker API Client를 통해 회원 정보 조회
    if not hasattr(current_app, 'locker_api_client') or not current_app.locker_api_client:
        return jsonify({'success': False, 'message': 'Locker API 클라이언트가 없습니다.'}), 500
    
    member_info = current_app.locker_api_client.get_member_by_nfc(nfc_uid)
    
    nfc_queue = getattr(current_app, 'nfc_queue', None)
    
    if not nfc_queue:
        return jsonify({'success': False, 'message': 'NFC 큐가 초기화되지 않았습니다.'}), 500
    
    if not member_info:
        # 오류 이벤트 큐에 추가
        try:
            nfc_queue.put_nowait({
                'nfc_uid': nfc_uid,
                'success': False,
                'message': '등록되지 않은 NFC 카드입니다.'
            })
            print(f"[API] 🧪 테스트: NFC 오류 이벤트 큐에 주입 - {nfc_uid}")
            return jsonify({
                'success': False,
                'message': '등록되지 않은 NFC 카드입니다 (큐에 저장됨)'
            }), 404
        except queue.Full:
            try:
                nfc_queue.get_nowait()
                nfc_queue.put_nowait({
                    'nfc_uid': nfc_uid,
                    'success': False,
                    'message': '등록되지 않은 NFC 카드입니다.'
                })
                return jsonify({
                    'success': False,
                    'message': '등록되지 않은 NFC 카드입니다 (큐에 저장됨, 기존 데이터 덮어씀)'
                }), 404
            except:
                return jsonify({'success': False, 'message': 'NFC 큐 추가 실패'}), 500
    
    # 성공 이벤트 큐에 추가
    try:
        nfc_queue.put_nowait({
            'nfc_uid': nfc_uid,
            'member_id': member_info['member_id'],
            'name': member_info['name'],
            'locker_number': member_info['locker_number'],
            'success': True
        })
        print(f"[API] 🧪 테스트: NFC 이벤트 큐에 주입 - {member_info['member_id']} ({member_info['name']})")
        return jsonify({
            'success': True,
            'message': 'NFC 이벤트가 큐에 추가되었습니다',
            'member': member_info
        })
    except queue.Full:
        try:
            nfc_queue.get_nowait()
            nfc_queue.put_nowait({
                'nfc_uid': nfc_uid,
                'member_id': member_info['member_id'],
                'name': member_info['name'],
                'locker_number': member_info['locker_number'],
                'success': True
            })
            print(f"[API] 🧪 테스트: NFC 이벤트 큐에 주입 (기존 데이터 덮어씀) - {member_info['member_id']}")
            return jsonify({
                'success': True,
                'message': 'NFC 이벤트가 큐에 추가되었습니다 (기존 데이터 덮어씀)',
                'member': member_info
            })
        except:
            return jsonify({'success': False, 'message': 'NFC 큐 추가 실패'}), 500
