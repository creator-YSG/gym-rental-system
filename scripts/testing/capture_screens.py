#!/usr/bin/env python3
"""
라즈베리파이 키오스크 화면 자동 캡쳐 스크립트

xdotool과 scrot을 사용하여 다양한 시나리오의 화면을 자동으로 캡쳐합니다.

사용법:
    python capture_screens.py --scenario A --phone 01011111111
    python capture_screens.py --scenario B --phone 01022222222 --execute-rental
    python capture_screens.py --scenario D2 --phone 01055555555 --execute-rental

시나리오:
    A  : 이용권 없는 회원
    B  : 구독권만 있는 회원
    C  : 금액권만 있는 회원
    D1 : 구독권 + 금액권 (구독권으로 전부 커버)
    D2 : 구독권 + 금액권 (혼합 결제, 핵심!)
    D3 : 구독권 소진 + 금액권
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# 라즈베리파이에서 실행되는지 확인
IS_RASPBERRY_PI = os.uname().machine.startswith('arm') or os.uname().machine.startswith('aarch')

# 스크린샷 저장 경로
SCREENSHOTS_DIR = Path.home() / 'screenshots'

# 브라우저 윈도우 타이틀 (키오스크 모드에서 실행 중인 Chromium)
WINDOW_TITLE = "Chromium"

# 키오스크 앱 URL
KIOSK_URL = "http://localhost:5000"


class ScreenCapture:
    """화면 캡쳐 자동화 클래스"""
    
    def __init__(self, scenario, phone, execute_rental=False):
        self.scenario = scenario.upper()
        self.phone = phone
        self.execute_rental = execute_rental
        self.output_dir = None
        self.screenshot_count = 0
        
        # 시나리오별 설정
        self.scenario_config = {
            'A': {
                'name': 'A_no_payment',
                'description': '이용권 없는 회원',
                'password': '123456',
            },
            'B': {
                'name': 'B_subscription_only',
                'description': '구독권만 있는 회원',
                'password': '123456',
            },
            'C': {
                'name': 'C_voucher_only',
                'description': '금액권만 있는 회원',
                'password': '123456',
            },
            'D1': {
                'name': 'D1_both_sub_covers',
                'description': '구독권 + 금액권 (구독권으로 전부 커버)',
                'password': '123456',
            },
            'D2': {
                'name': 'D2_both_mixed',
                'description': '구독권 + 금액권 (혼합 결제)',
                'password': '123456',
            },
            'D3': {
                'name': 'D3_sub_exhausted',
                'description': '구독권 소진 + 금액권',
                'password': '123456',
            },
        }
        
        if self.scenario not in self.scenario_config:
            print(f"❌ 잘못된 시나리오: {self.scenario}")
            print(f"   사용 가능한 시나리오: {', '.join(self.scenario_config.keys())}")
            sys.exit(1)
    
    def check_dependencies(self):
        """필요한 도구 확인"""
        print("🔍 시스템 확인 중...")
        
        tools = ['xdotool', 'scrot']
        missing = []
        
        for tool in tools:
            if subprocess.run(['which', tool], capture_output=True).returncode != 0:
                missing.append(tool)
        
        if missing:
            print(f"❌ 필요한 도구가 설치되지 않았습니다: {', '.join(missing)}")
            print(f"   설치: sudo apt install {' '.join(missing)}")
            sys.exit(1)
        
        print("✅ 필요한 도구 확인 완료")
    
    def setup_output_dir(self):
        """출력 디렉토리 생성"""
        config = self.scenario_config[self.scenario]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        self.output_dir = SCREENSHOTS_DIR / f"{config['name']}_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 출력 디렉토리: {self.output_dir}")
    
    def capture(self, filename, description=""):
        """스크린샷 캡쳐"""
        self.screenshot_count += 1
        filepath = self.output_dir / f"{self.screenshot_count:02d}_{filename}.png"
        
        print(f"📸 [{self.screenshot_count:02d}] {description or filename}")
        
        # scrot으로 스크린샷 캡쳐
        subprocess.run(['scrot', str(filepath)], check=True)
        
        return filepath
    
    def wait(self, seconds=1.0, message=""):
        """대기"""
        if message:
            print(f"   ⏳ {message} ({seconds}초 대기)")
        time.sleep(seconds)
    
    def focus_window(self):
        """브라우저 윈도우 포커스"""
        subprocess.run(['xdotool', 'search', '--name', WINDOW_TITLE, 'windowactivate'], 
                      capture_output=True)
        self.wait(0.5)
    
    def click(self, x, y):
        """좌표 클릭"""
        subprocess.run(['xdotool', 'mousemove', str(x), str(y), 'click', '1'], 
                      check=True)
        self.wait(0.3)
    
    def type_text(self, text):
        """텍스트 입력"""
        subprocess.run(['xdotool', 'type', '--delay', '100', text], 
                      check=True)
        self.wait(0.5)
    
    def press_key(self, key):
        """키 입력"""
        subprocess.run(['xdotool', 'key', key], check=True)
        self.wait(0.3)
    
    def reload_page(self):
        """페이지 새로고침 (Ctrl+R)"""
        print("🔄 페이지 새로고침")
        subprocess.run(['xdotool', 'key', 'ctrl+r'], check=True)
        self.wait(2.0, "페이지 로드 중")
    
    def input_phone_number(self):
        """전화번호 입력"""
        print(f"\n📱 전화번호 입력: {self.phone}")
        
        # 1. 초기 홈 화면
        self.capture('home_initial', '홈 화면 (초기)')
        self.wait(1.0)
        
        # 2. 화면 클릭하여 포커스 (전화번호 입력 필드)
        self.click(640, 400)
        self.wait(0.5)
        
        # 3. 전화번호 직접 타이핑
        phone_digits = self.phone.replace('-', '')
        for i, digit in enumerate(phone_digits):
            subprocess.run(['xdotool', 'key', digit], check=True)
            self.wait(0.15)
            
            # 중간에 한 번 캡쳐
            if i == 5:
                self.capture('home_input_partial', '홈 화면 (전화번호 입력 중)')
        
        self.wait(0.5)
        
        # 4. 전화번호 입력 완료
        self.capture('home_input_complete', '홈 화면 (전화번호 입력 완료)')
        
        # 5. Tab 키로 로그인 버튼으로 이동 후 Enter
        print("   ⌨️  로그인 (Tab + Enter)")
        subprocess.run(['xdotool', 'key', 'Tab'], check=True)
        self.wait(0.3)
        subprocess.run(['xdotool', 'key', 'Return'], check=True)
        
        # 6. 로딩 화면
        self.wait(0.3)
        self.capture('home_loading', '홈 화면 (로딩 중)')
        
        # 7. 상품 선택 화면으로 이동 대기
        self.wait(2.5, "상품 선택 화면 로드 중")
    
    def capture_rental_screen(self):
        """상품 선택 화면 캡쳐"""
        print("\n🛒 상품 선택 화면")
        
        # 1. 초기 상태
        self.capture('rental_initial', '상품 선택 화면 (초기)')
        self.wait(1.5)
        
        # 2. 마이페이지 열기 (Tab으로 버튼 찾아서 Enter - 또는 직접 클릭)
        print("   ⌨️  마이페이지 열기")
        # 우측 상단 마이페이지 버튼 클릭 (좌표 사용 - 버튼 위치는 고정)
        self.click(1100, 120)
        self.wait(1.5)
        self.capture('mypage_panel', '마이페이지 슬라이드 패널')
        
        # 3. 마이페이지 닫기 (Escape 키)
        self.wait(1.0)
        print("   ⌨️  마이페이지 닫기 (ESC)")
        subprocess.run(['xdotool', 'key', 'Escape'], check=True)
        self.wait(0.5)
        
        # 4. 상품 선택
        if self.scenario not in ['A']:  # 이용권 없는 회원은 선택 안함
            print("   ⌨️  상품 선택 (첫 번째 상품 클릭)")
            # 첫 번째 상품 클릭
            self.click(400, 350)
            self.wait(1.5)
            self.capture('rental_cart_one', '장바구니 (상품 1개)')
            
            # D2 시나리오는 상품 하나 더 추가 (구독권 한도 초과)
            if self.scenario == 'D2':
                print("   ⌨️  상품 추가 (한 개 더)")
                self.click(400, 350)
                self.wait(1.5)
                self.capture('rental_cart_two', '장바구니 (상품 2개)')
    
    def capture_checkout_flow(self):
        """결제 플로우 캡쳐"""
        config = self.scenario_config[self.scenario]
        password = config['password']
        
        if self.scenario == 'A':
            # 이용권 없는 회원은 결제 불가
            print("\n⚠️  이용권 없음 - 결제 불가")
            return
        
        print("\n💳 결제 플로우")
        
        # 1. 대여하기 버튼 (페이지 하단, Tab으로 이동 또는 클릭)
        print("   ⌨️  대여하기 버튼")
        # 화면 하단 대여하기 버튼 클릭
        self.click(640, 720)
        self.wait(2.0)
        
        # 2. 시나리오별 분기
        if self.scenario in ['B', 'C']:
            # 구독권만 OR 금액권만 → 결제 모달 없이 바로 비밀번호
            print("   (결제 모달 생략 - 자동 배정)")
            
        elif self.scenario in ['D1', 'D2', 'D3']:
            # 구독권 + 금액권 → 결제 확인 모달 표시
            self.wait(0.5)
            self.capture('payment_modal', '결제 확인 모달')
            self.wait(1.0)
            
            # D2는 금액권 쪼개기 UI도 캡쳐
            if self.scenario == 'D2':
                # 금액 입력 필드 클릭 (숫자 키패드 열기)
                print("   ⌨️  금액 입력 필드 클릭 (키패드)")
                self.click(640, 480)  # 금액 입력 필드
                self.wait(0.8)
                self.capture('numpad_overlay', '숫자 키패드')
                
                # 키패드 닫기 (Escape)
                subprocess.run(['xdotool', 'key', 'Escape'], check=True)
                self.wait(0.5)
            
            # 대여하기 버튼 클릭 (모달 내)
            print("   ⌨️  모달 대여하기 버튼 (Tab + Enter)")
            # Tab 여러 번 눌러서 대여하기 버튼으로 이동
            for _ in range(5):
                subprocess.run(['xdotool', 'key', 'Tab'], check=True)
                self.wait(0.1)
            subprocess.run(['xdotool', 'key', 'Return'], check=True)
            self.wait(1.5)
        
        # 3. 비밀번호 입력 모달
        self.capture('password_modal', '비밀번호 입력 모달')
        self.wait(0.5)
        
        # 4. 비밀번호 직접 타이핑
        print(f"   ⌨️  비밀번호 입력: {password}")
        for i, digit in enumerate(password):
            subprocess.run(['xdotool', 'key', digit], check=True)
            self.wait(0.15)
            
            # 중간에 한 번 캡쳐
            if i == 2:
                self.capture('password_input_partial', '비밀번호 입력 중 (3자리)')
        
        self.wait(0.5)
        
        # 5. 비밀번호 입력 완료
        self.capture('password_input_complete', '비밀번호 입력 완료')
        
        # 6. 확인 버튼 (Tab + Enter 또는 클릭)
        if self.execute_rental:
            print("   ⌨️  확인 버튼 (Tab + Enter)")
            subprocess.run(['xdotool', 'key', 'Tab'], check=True)
            self.wait(0.3)
            subprocess.run(['xdotool', 'key', 'Return'], check=True)
            self.wait(3.0, "대여 처리 중")
            
            # 7. 대여 완료 화면
            self.capture('complete_screen', '대여 완료 화면')
            print("   ✅ 대여 완료!")
        else:
            print("   ⏸️  대여 실행하지 않음")
            # Escape로 취소
            subprocess.run(['xdotool', 'key', 'Escape'], check=True)
            self.wait(0.5)
    
    def run(self):
        """시나리오 실행"""
        config = self.scenario_config[self.scenario]
        
        print("\n" + "="*60)
        print(f"📸 화면 캡쳐 시작")
        print("="*60)
        print(f"시나리오: {self.scenario} - {config['description']}")
        print(f"전화번호: {self.phone}")
        print(f"실제 대여: {'예' if self.execute_rental else '아니오'}")
        print("="*60 + "\n")
        
        # 1. 사전 확인
        self.check_dependencies()
        
        # 2. 출력 디렉토리 생성
        self.setup_output_dir()
        
        # 3. 브라우저 포커스
        self.focus_window()
        
        # 4. 페이지 새로고침 (초기화)
        self.reload_page()
        
        # 5. 전화번호 입력 & 로그인
        self.input_phone_number()
        
        # 6. 상품 선택 화면
        self.capture_rental_screen()
        
        # 7. 결제 플로우
        self.capture_checkout_flow()
        
        # 완료
        print("\n" + "="*60)
        print(f"✅ 캡쳐 완료! 총 {self.screenshot_count}장")
        print(f"📁 저장 위치: {self.output_dir}")
        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='라즈베리파이 키오스크 화면 자동 캡쳐',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
시나리오:
  A   이용권 없는 회원
  B   구독권만 있는 회원
  C   금액권만 있는 회원
  D1  구독권 + 금액권 (구독권으로 전부 커버)
  D2  구독권 + 금액권 (혼합 결제, 핵심!)
  D3  구독권 소진 + 금액권

예시:
  python capture_screens.py --scenario B --phone 01022222222
  python capture_screens.py --scenario D2 --phone 01055555555 --execute-rental
        """
    )
    
    parser.add_argument('--scenario', required=True, 
                       choices=['A', 'B', 'C', 'D1', 'D2', 'D3'],
                       help='캡쳐할 시나리오')
    parser.add_argument('--phone', required=True,
                       help='로그인할 전화번호')
    parser.add_argument('--execute-rental', action='store_true',
                       help='실제로 대여 실행 (기본: 비밀번호까지만)')
    
    args = parser.parse_args()
    
    # 캡쳐 실행
    capture = ScreenCapture(args.scenario, args.phone, args.execute_rental)
    
    try:
        capture.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

