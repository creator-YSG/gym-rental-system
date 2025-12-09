"""
IntegrationSync 테스트 스크립트
락카키 대여기 IP를 System_Integration 시트에서 다운로드 테스트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.integration_sync import IntegrationSync


def main():
    print("="*60)
    print("IntegrationSync 테스트")
    print("="*60)
    print()
    
    # 1. IntegrationSync 초기화
    print("[1/3] IntegrationSync 초기화...")
    sync = IntegrationSync()
    print(f"  - Credentials: {sync.credentials_path}")
    print(f"  - Cache File: {sync.cache_file}")
    print()
    
    # 2. 구글 시트 연결
    print("[2/3] 구글 시트 연결...")
    if sync.connect():
        print(f"  ✓ 연결 성공: {sync.spreadsheet.title}")
        print(f"  - Sheet ID: {sync.INTEGRATION_SHEET_ID}")
    else:
        print("  ✗ 연결 실패")
        print("  → 캐시에서 로드 시도...")
    print()
    
    # 3. 락카키 대여기 IP 다운로드
    print("[3/3] 락카키 대여기 IP 다운로드...")
    locker_api_info = sync.download_locker_api_info()
    
    print()
    print("="*60)
    print("다운로드 결과")
    print("="*60)
    print(f"  Host: {locker_api_info.get('host', 'N/A')}")
    print(f"  Port: {locker_api_info.get('port', 'N/A')}")
    print(f"  URL: {locker_api_info.get('url', 'N/A')}")
    print(f"  Last Updated: {locker_api_info.get('last_updated', 'N/A')}")
    print(f"  Status: {locker_api_info.get('status', 'N/A')}")
    
    if 'cached_at' in locker_api_info:
        print(f"  [캐시] Cached At: {locker_api_info['cached_at']}")
    
    print()
    print("="*60)
    print("테스트 완료!")
    print("="*60)
    
    # 4. 헬스 체크 (선택)
    try:
        import requests
        print()
        print("[추가] 락카키 대여기 API 헬스 체크...")
        url = locker_api_info['url']
        response = requests.get(f"{url}/api/health", timeout=2)
        
        if response.status_code == 200:
            print(f"  ✓ 헬스 체크 성공: {url}")
            print(f"  응답: {response.json()}")
        else:
            print(f"  ✗ 헬스 체크 실패: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ✗ 헬스 체크 오류: {e}")


if __name__ == '__main__':
    main()

