#!/usr/bin/env python3
"""
NFC 리더 시뮬레이터

ESP32 없이 NFC 리더를 시뮬레이션합니다.
가상 시리얼 포트로 NFC UID를 전송합니다.
"""

import sys
import os
import time

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.nfc_reader import NFCReaderService
from app.services.locker_api_client import LockerAPIClient


def simulate_nfc_tag(nfc_uid: str):
    """
    NFC 태그 시뮬레이션
    
    실제로는 ESP32에서 보내는 데이터를:
    {"nfc_uid":"5A41B914524189"}
    
    직접 NFCReaderService의 콜백을 호출하여 시뮬레이션합니다.
    """
    print(f"\n{'='*60}")
    print(f"NFC 태그 시뮬레이션")
    print(f"{'='*60}\n")
    
    print(f"[시뮬레이션] NFC 카드 태그")
    print(f"  NFC UID: {nfc_uid}")
    print(f"  ESP32 → 라즈베리파이 (시리얼)")
    print(f"  데이터: {{\"nfc_uid\":\"{nfc_uid}\"}}")
    
    # 락카키 대여기 API 클라이언트
    locker_api = LockerAPIClient(base_url="http://192.168.0.23:5000")
    
    # NFC 리더 서비스의 콜백 함수 시뮬레이션
    def on_nfc_detected(uid: str):
        print(f"\n[NFCReaderService] 콜백 실행")
        print(f"  UID: {uid}")
        
        # 락카키 대여기 API 호출
        print(f"\n[LockerAPIClient] API 호출")
        member = locker_api.get_member_by_nfc(uid)
        
        if member:
            print(f"\n  ✓ 회원 조회 성공:")
            print(f"    - 회원 ID: {member['member_id']}")
            print(f"    - 이름: {member['name']}")
            print(f"    - 락카: {member['locker_number']}")
            
            print(f"\n[SocketIO] 이벤트 발생 (시뮬레이션)")
            print(f"  → 웹 브라우저로 전송:")
            print(f"     nfc_detected({{")
            print(f"       member_id: '{member['member_id']}',")
            print(f"       name: '{member['name']}',")
            print(f"       locker_number: '{member['locker_number']}'")
            print(f"     }})")
            
            print(f"\n[웹 브라우저] 자동 로그인")
            print(f"  → POST /api/auth/member_id")
            print(f"  → 성공 시 /rental 페이지로 이동")
            
        else:
            print(f"\n  ✗ 회원 정보 없음")
            print(f"\n[SocketIO] 에러 이벤트 발생")
            print(f"  → nfc_error({{message: '락카가 배정되어 있지 않습니다'}})")
    
    # 콜백 실행
    on_nfc_detected(nfc_uid)
    
    print(f"\n{'='*60}")
    print(f"시뮬레이션 완료")
    print(f"{'='*60}\n")
    
    print(f"💡 실제 동작:")
    print(f"   1. ESP32에 NFC 카드 태그")
    print(f"   2. ESP32가 UID를 시리얼로 전송")
    print(f"   3. NFCReaderService가 수신 및 콜백 실행")
    print(f"   4. 락카키 대여기 API 호출")
    print(f"   5. SocketIO로 웹 브라우저에 전송")
    print(f"   6. 웹 브라우저가 자동으로 로그인 API 호출")
    print(f"   7. 로그인 성공 시 /rental로 이동")
    print()


def continuous_simulation():
    """연속 시뮬레이션 (인터랙티브 모드)"""
    print(f"\n{'='*60}")
    print(f"NFC 리더 시뮬레이터 (인터랙티브 모드)")
    print(f"{'='*60}\n")
    print(f"샘플 NFC UID:")
    print(f"  1. 5A41B914524189 (M01 대여중)")
    print(f"  2. 5AE17DD3514189 (S01 비어있음)")
    print(f"  3. 직접 입력")
    print(f"  0. 종료")
    print()
    
    sample_uids = {
        '1': '5A41B914524189',
        '2': '5AE17DD3514189',
    }
    
    while True:
        choice = input("선택 (0-3): ").strip()
        
        if choice == '0':
            print("종료합니다.")
            break
        elif choice == '3':
            nfc_uid = input("NFC UID 입력: ").strip().upper()
            if nfc_uid:
                simulate_nfc_tag(nfc_uid)
        elif choice in sample_uids:
            simulate_nfc_tag(sample_uids[choice])
        else:
            print("잘못된 선택입니다.")
        
        print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 명령줄 인자로 UID 전달
        nfc_uid = sys.argv[1]
        simulate_nfc_tag(nfc_uid)
    else:
        # 인터랙티브 모드
        continuous_simulation()

