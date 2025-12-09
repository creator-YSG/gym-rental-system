#!/usr/bin/env python3
"""
NFC 로그인 테스트 스크립트

ESP32 없이 NFC 로그인을 테스트합니다.
"""

import sys
import os

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.locker_api_client import LockerAPIClient
from app import socketio


def test_nfc_login(nfc_uid: str):
    """
    NFC 로그인 테스트
    
    Args:
        nfc_uid: 테스트할 NFC UID
    """
    print(f"\n{'='*60}")
    print(f"NFC 로그인 테스트")
    print(f"{'='*60}\n")
    
    # 1. 락카키 대여기 API 호출 테스트
    print(f"[1단계] 락카키 대여기 API 호출")
    print(f"  NFC UID: {nfc_uid}")
    
    client = LockerAPIClient(base_url="http://192.168.0.23:5000")
    
    # 헬스 체크
    print(f"\n  락카키 대여기 서버 상태 확인...")
    if client.health_check():
        print(f"  ✓ 서버 정상")
    else:
        print(f"  ✗ 서버 다운 (테스트 계속 진행)")
    
    # 회원 정보 조회
    print(f"\n  회원 정보 조회 중...")
    member = client.get_member_by_nfc(nfc_uid)
    
    if member:
        print(f"  ✓ 회원 조회 성공:")
        print(f"    - 회원 ID: {member['member_id']}")
        print(f"    - 이름: {member['name']}")
        print(f"    - 락카 번호: {member['locker_number']}")
        print(f"    - 배정 시각: {member['assigned_at']}")
        
        member_id = member['member_id']
        
        # 2. SocketIO 이벤트 발생
        print(f"\n[2단계] SocketIO 이벤트 발생")
        print(f"  이벤트: nfc_detected")
        print(f"  데이터: {{member_id: '{member_id}', name: '{member['name']}', ...}}")
        
        try:
            socketio.emit('nfc_detected', {
                'nfc_uid': nfc_uid,
                'member_id': member_id,
                'name': member['name'],
                'locker_number': member['locker_number']
            })
            print(f"  ✓ SocketIO 이벤트 발생 성공")
            print(f"\n  💡 웹 브라우저에서 홈 화면(/)을 열어두면")
            print(f"     자동으로 로그인되어 /rental로 이동합니다!")
        except Exception as e:
            print(f"  ✗ SocketIO 이벤트 발생 실패: {e}")
        
        # 3. 로그인 API 테스트
        print(f"\n[3단계] 로그인 API 테스트 (직접 호출)")
        print(f"  POST /api/auth/member_id")
        print(f"  Body: {{member_id: '{member_id}'}}")
        
        import requests
        try:
            response = requests.post(
                'http://localhost:5000/api/auth/member_id',
                json={'member_id': member_id},
                timeout=2.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"  ✓ 로그인 성공:")
                    member_data = data['member']
                    print(f"    - 회원 ID: {member_data['member_id']}")
                    print(f"    - 이름: {member_data['name']}")
                    print(f"    - 금액권 잔액: {member_data.get('total_balance', 0):,}원")
                    print(f"    - 활성 금액권: {member_data.get('active_vouchers_count', 0)}개")
                    print(f"    - 활성 구독권: {member_data.get('active_subscriptions_count', 0)}개")
                else:
                    print(f"  ✗ 로그인 실패: {data.get('message')}")
            else:
                print(f"  ✗ HTTP {response.status_code}: {response.text}")
        except requests.ConnectionError:
            print(f"  ✗ Flask 앱이 실행되지 않았습니다")
            print(f"     먼저 'python run.py'를 실행해주세요")
        except Exception as e:
            print(f"  ✗ 오류: {e}")
        
    else:
        print(f"  ✗ 회원 정보 없음")
        print(f"    - 락카가 배정되어 있지 않거나")
        print(f"    - NFC UID가 등록되지 않았습니다")
        
        # SocketIO 에러 이벤트
        print(f"\n[2단계] SocketIO 에러 이벤트 발생")
        try:
            socketio.emit('nfc_error', {
                'nfc_uid': nfc_uid,
                'message': '락카가 배정되어 있지 않습니다'
            })
            print(f"  ✓ 에러 이벤트 발생 성공")
        except Exception as e:
            print(f"  ✗ 에러 이벤트 발생 실패: {e}")
    
    print(f"\n{'='*60}")
    print(f"테스트 완료")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    # 테스트 NFC UID
    nfc_uid = "5A41B914524189"  # 락카키 대여기에 등록된 샘플 UID
    
    if len(sys.argv) > 1:
        nfc_uid = sys.argv[1]
    
    test_nfc_login(nfc_uid)

