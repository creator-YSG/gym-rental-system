"""
락카키 대여기 API

락카키 대여기 라즈베리파이에서 실행되는 API 서버
- 운동복 대여기가 NFC 태그 시 회원 정보 조회
- 락카 배정/해제 내부 처리
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

# Blueprint 생성
api_locker_bp = Blueprint('api_locker', __name__, url_prefix='/api')

# LocalCache는 앱 초기화 시 주입받음
_local_cache = None


def init_api_locker(local_cache):
    """
    API 초기화
    
    Args:
        local_cache: LocalCache 인스턴스
    """
    global _local_cache
    _local_cache = local_cache


# =============================
# 운동복 대여기가 호출하는 API (Pull 방식)
# =============================

@api_locker_bp.route('/member/by-locker/<int:locker_number>', methods=['GET'])
def get_member_by_locker(locker_number):
    """
    락카 번호로 회원 정보 조회 API
    
    *** 운동복 대여기에서 NFC 태그 시 호출 ***
    
    Request:
        GET /api/member/by-locker/105
    
    Response:
        200 OK (회원 찾음)
        {
          "status": "ok",
          "locker_number": 105,
          "member_id": "A001",
          "name": "홍길동",
          "remaining_count": 10,
          "total_charged": 15,
          "total_used": 5,
          "assigned_at": "2024-12-01T10:00:00"
        }
        
        404 Not Found (락카 미배정)
        {
          "status": "error",
          "message": "해당 락카가 배정되어 있지 않습니다"
        }
    """
    try:
        # 락카 번호로 회원 ID 조회
        member_id = _local_cache.get_member_by_locker(locker_number)
        
        if not member_id:
            return jsonify({
                'status': 'error',
                'locker_number': locker_number,
                'message': '해당 락카가 배정되어 있지 않습니다'
            }), 404
        
        # 회원 정보 조회
        member = _local_cache.get_member(member_id)
        
        if not member:
            return jsonify({
                'status': 'error',
                'locker_number': locker_number,
                'member_id': member_id,
                'message': '회원 정보를 찾을 수 없습니다'
            }), 404
        
        # 락카 배정 정보 조회
        locker_info = _local_cache.get_locker_info(locker_number)
        
        return jsonify({
            'status': 'ok',
            'locker_number': locker_number,
            'member_id': member_id,
            'name': member.get('name', ''),
            'remaining_count': member.get('remaining_count', 0),
            'total_charged': member.get('total_charged', 0),
            'total_used': member.get('total_used', 0),
            'assigned_at': locker_info.get('assigned_at', '') if locker_info else ''
        }), 200
        
    except Exception as e:
        print(f"[API] 회원 조회 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': '서버 오류'
        }), 500


# =============================
# 락카키 대여기 내부용 API
# =============================

@api_locker_bp.route('/locker/assign', methods=['POST'])
def assign_locker():
    """
    락카 배정 API (락카키 대여기 내부용)
    
    락카키 대여 시 호출하여 락카-회원 매핑 저장
    
    Request:
        POST /api/locker/assign
        {
          "locker": 105,
          "member": "A001"
        }
    
    Response:
        200 OK
        {
          "status": "ok",
          "locker": 105,
          "member_id": "A001",
          "name": "홍길동"
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'locker' not in data or 'member' not in data:
            return jsonify({
                'status': 'error',
                'message': '필수 파라미터 누락 (locker, member)'
            }), 400
        
        locker_number = int(data['locker'])
        member_id = str(data['member'])
        
        # 회원 존재 확인
        member = _local_cache.get_member(member_id)
        if not member:
            return jsonify({
                'status': 'error',
                'message': f'회원을 찾을 수 없습니다: {member_id}'
            }), 404
        
        # 락카 배정
        _local_cache.assign_locker(locker_number, member_id)
        
        return jsonify({
            'status': 'ok',
            'locker': locker_number,
            'member_id': member_id,
            'name': member.get('name', ''),
            'assigned_at': datetime.now().isoformat()
        }), 200
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        print(f"[API] 락카 배정 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': '서버 오류'
        }), 500


@api_locker_bp.route('/locker/release', methods=['POST'])
def release_locker():
    """
    락카 해제 API (락카키 대여기 내부용)
    
    락카키 반납 시 호출
    
    Request:
        POST /api/locker/release
        {
          "locker": 105
        }
    
    Response:
        200 OK
        {
          "status": "ok",
          "locker": 105
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'locker' not in data:
            return jsonify({
                'status': 'error',
                'message': '필수 파라미터 누락 (locker)'
            }), 400
        
        locker_number = int(data['locker'])
        
        # 락카 해제
        success = _local_cache.release_locker(locker_number)
        
        if success:
            return jsonify({
                'status': 'ok',
                'locker': locker_number
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'락카 {locker_number}번이 배정되어 있지 않습니다'
            }), 404
            
    except Exception as e:
        print(f"[API] 락카 해제 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': '서버 오류'
        }), 500


@api_locker_bp.route('/locker/list', methods=['GET'])
def list_lockers():
    """
    현재 배정된 락카 목록 조회 API
    
    Request:
        GET /api/locker/list
    
    Response:
        200 OK
        {
          "status": "ok",
          "count": 3,
          "lockers": [
            {"locker": 105, "member_id": "A001", "name": "홍길동"},
            {"locker": 106, "member_id": "A002", "name": "김철수"},
            ...
          ]
        }
    """
    try:
        lockers = _local_cache.get_all_lockers()
        
        result = []
        for locker_number, member_id in lockers.items():
            member = _local_cache.get_member(member_id)
            result.append({
                'locker': locker_number,
                'member_id': member_id,
                'name': member.get('name', '') if member else ''
            })
        
        return jsonify({
            'status': 'ok',
            'count': len(result),
            'lockers': sorted(result, key=lambda x: x['locker'])
        }), 200
        
    except Exception as e:
        print(f"[API] 락카 목록 조회 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': '서버 오류'
        }), 500


@api_locker_bp.route('/member/<member_id>', methods=['GET'])
def get_member_info(member_id):
    """
    회원 정보 조회 API
    
    Request:
        GET /api/member/A001
    
    Response:
        200 OK
        {
          "status": "ok",
          "member_id": "A001",
          "name": "홍길동",
          "remaining_count": 10,
          ...
        }
    """
    try:
        member = _local_cache.get_member(member_id)
        
        if member:
            return jsonify({
                'status': 'ok',
                **member
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'회원을 찾을 수 없습니다: {member_id}'
            }), 404
            
    except Exception as e:
        print(f"[API] 회원 조회 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': '서버 오류'
        }), 500


@api_locker_bp.route('/health', methods=['GET'])
def health_check():
    """
    헬스 체크 API
    
    Request:
        GET /api/health
    
    Response:
        200 OK
        {
          "status": "healthy",
          "service": "locker-api",
          "timestamp": "2024-12-01T10:00:00"
        }
    """
    return jsonify({
        'status': 'healthy',
        'service': 'locker-api',
        'timestamp': datetime.now().isoformat()
    }), 200
