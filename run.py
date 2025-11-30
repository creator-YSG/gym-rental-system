#!/usr/bin/env python3
"""
운동복/수건 대여 시스템 - 메인 실행 파일
"""
import os
import sys
from app import create_app

def main():
    """Flask 애플리케이션 시작"""
    
    # 애플리케이션 생성
    app = create_app()
    
    # 개발 서버 설정
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print("=" * 60)
    print("🏃 운동복/수건 대여 시스템 시작")
    print("=" * 60)
    print(f"📍 주소: http://{host}:{port}")
    print(f"🔧 디버그 모드: {debug}")
    print("=" * 60)
    print()
    
    # Flask 서버 실행
    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=debug
        )
    except KeyboardInterrupt:
        print("\n\n🛑 서버를 종료합니다...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

