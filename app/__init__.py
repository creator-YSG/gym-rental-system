"""
운동복/수건 대여 시스템 - Flask 애플리케이션
"""
import os
from flask import Flask
from flask_socketio import SocketIO

# SocketIO 인스턴스 (전역)
socketio = SocketIO()

def create_app(config_name='default'):
    """Flask 애플리케이션 팩토리"""
    
    app = Flask(__name__)
    
    # 기본 설정
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DATABASE_PATH=os.path.join(app.instance_path, 'rental_system.db'),
        PORTRAIT_MODE=True,  # 터치스크린 세로 모드
    )
    
    # instance 폴더 생성
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # SocketIO 초기화
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # 블루프린트 등록
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    # 에러 핸들러
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    return app

