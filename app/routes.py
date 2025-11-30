"""
메인 라우트
"""
from flask import Blueprint, render_template, jsonify, request
from app.services.rental_service import RentalService
from app.services.barcode_service import BarcodeService

main_bp = Blueprint('main', __name__)

# 서비스 인스턴스
rental_service = RentalService()
barcode_service = BarcodeService()

@main_bp.route('/')
def index():
    """홈 페이지"""
    return render_template('pages/home.html')

@main_bp.route('/rental')
def rental():
    """대여 페이지"""
    return render_template('pages/rental.html')

@main_bp.route('/return')
def return_page():
    """반납 페이지"""
    return render_template('pages/return.html')

@main_bp.route('/status')
def status():
    """재고 현황 페이지"""
    return render_template('pages/status.html')

# API 엔드포인트
@main_bp.route('/api/scan', methods=['POST'])
def api_scan_barcode():
    """바코드 스캔 처리"""
    data = request.json
    barcode = data.get('barcode')
    
    if not barcode:
        return jsonify({'success': False, 'message': '바코드가 없습니다'}), 400
    
    # 바코드 처리
    result = barcode_service.process_barcode(barcode)
    return jsonify(result)

@main_bp.route('/api/rental', methods=['POST'])
def api_create_rental():
    """대여 생성"""
    data = request.json
    member_id = data.get('member_id')
    item_type = data.get('item_type')  # 'uniform' or 'towel'
    item_size = data.get('item_size')  # 'S', 'M', 'L', 'XL' or None
    
    result = rental_service.create_rental(member_id, item_type, item_size)
    return jsonify(result)

@main_bp.route('/api/return', methods=['POST'])
def api_return_item():
    """반납 처리"""
    data = request.json
    rental_id = data.get('rental_id')
    
    result = rental_service.return_item(rental_id)
    return jsonify(result)

@main_bp.route('/api/inventory', methods=['GET'])
def api_get_inventory():
    """재고 현황 조회"""
    inventory = rental_service.get_inventory_status()
    return jsonify(inventory)

