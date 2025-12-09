"""
락카키 대여기 API 클라이언트
NFC UID로 회원 정보 조회
"""

import requests
from typing import Optional, Dict


class LockerAPIClient:
    """락카키 대여기 API 클라이언트"""
    
    def __init__(self, base_url: str = "http://192.168.0.23:5000", timeout: float = 2.0):
        """
        초기화
        
        Args:
            base_url: 락카키 대여기 API 주소
            timeout: 타임아웃 (초)
        """
        self.base_url = base_url
        self.timeout = timeout
    
    def get_member_by_nfc(self, nfc_uid: str) -> Optional[Dict]:
        """
        NFC UID로 회원 정보 조회
        
        Args:
            nfc_uid: NFC 태그 UID (예: "5A41B914524189")
        
        Returns:
            dict: 회원 정보 또는 None
            {
                'member_id': '20240861',
                'name': '쩐부테쑤안',
                'locker_number': 'M01',
                'assigned_at': '2025-12-09 10:33:52'
            }
        """
        try:
            url = f"{self.base_url}/api/member/by-nfc/{nfc_uid}"
            print(f"[Locker API] 요청: {url}")
            
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'ok':
                    print(f"[Locker API] ✓ 회원 조회 성공: {data.get('name')} ({data.get('member_id')})")
                    return {
                        'member_id': data['member_id'],
                        'name': data['name'],
                        'locker_number': data.get('locker_number', ''),
                        'assigned_at': data.get('assigned_at', '')
                    }
                else:
                    print(f"[Locker API] ✗ 응답 오류: {data.get('message')}")
                    return None
                    
            elif response.status_code == 404:
                print(f"[Locker API] ✗ 락카 미배정: NFC {nfc_uid}")
                return None
            else:
                print(f"[Locker API] ✗ HTTP 오류: {response.status_code}")
                return None
                
        except requests.Timeout:
            print(f"[Locker API] ✗ 타임아웃: 락카키 대여기 응답 없음")
            return None
        except requests.ConnectionError:
            print(f"[Locker API] ✗ 연결 실패: 락카키 대여기 서버 다운")
            return None
        except Exception as e:
            print(f"[Locker API] ✗ 예외 발생: {e}")
            return None
    
    def health_check(self) -> bool:
        """락카키 대여기 API 서버 상태 확인"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=1.0)
            return response.status_code == 200
        except:
            return False


# 사용 예시
if __name__ == '__main__':
    client = LockerAPIClient()
    
    # 헬스 체크
    if client.health_check():
        print("✓ 락카키 대여기 서버 정상")
    else:
        print("✗ 락카키 대여기 서버 다운")
    
    # 회원 조회
    member = client.get_member_by_nfc("5A41B914524189")
    if member:
        print(f"회원 정보: {member}")
    else:
        print("회원 정보 없음")

