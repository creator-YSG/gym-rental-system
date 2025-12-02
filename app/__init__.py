"""
운동복/수건 대여 시스템 - Flask 애플리케이션
"""
import os
from flask import Flask, jsonify
from flask_socketio import SocketIO

# SocketIO 인스턴스 (전역)
socketio = SocketIO()

# 전역 서비스 인스턴스
mqtt_service = None
local_cache = None


def create_app(config_name='default'):
    """Flask 애플리케이션 팩토리"""
    global mqtt_service, local_cache
    
    app = Flask(__name__)
    
    # 기본 설정
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DATABASE_PATH=os.path.join(app.instance_path, 'rental_system.db'),
        PORTRAIT_MODE=True,  # 터치스크린 세로 모드
        # MQTT 설정
        MQTT_BROKER_HOST=os.getenv('MQTT_BROKER_HOST', 'localhost'),
        MQTT_BROKER_PORT=int(os.getenv('MQTT_BROKER_PORT', 1883)),
    )
    
    # instance 폴더 생성
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # SocketIO 초기화
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # LocalCache 초기화
    try:
        from app.services.local_cache import LocalCache
        local_cache = LocalCache()
        app.local_cache = local_cache
        print("[App] LocalCache 초기화 완료")
    except Exception as e:
        print(f"[App] LocalCache 초기화 실패: {e}")
    
    # MQTT 서비스 초기화 (백그라운드)
    try:
        from app.services.mqtt_service import MQTTService, register_default_handlers
        mqtt_service = MQTTService(
            broker_host=app.config['MQTT_BROKER_HOST'],
            broker_port=app.config['MQTT_BROKER_PORT']
        )
        
        # LocalCache 연결
        if local_cache:
            mqtt_service.set_local_cache(local_cache)
        
        # 기본 핸들러 등록
        register_default_handlers(mqtt_service, local_cache)
        
        # MQTT 연결 (실패해도 앱은 계속 실행)
        if mqtt_service.connect():
            print("[App] MQTT 연결 성공")
        else:
            print("[App] MQTT 연결 실패 - 나중에 재시도")
        
        app.mqtt_service = mqtt_service
        
    except Exception as e:
        print(f"[App] MQTT 초기화 실패: {e}")
    
    # 블루프린트 등록
    from app.routes import main_bp, api_locker_bp, api_device_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_locker_bp)
    app.register_blueprint(api_device_bp)
    
    # 에러 핸들러 (JSON 응답)
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app


def get_mqtt_service():
    """MQTT 서비스 인스턴스 반환"""
    return mqtt_service


def get_local_cache():
    """LocalCache 인스턴스 반환"""
    return local_cache

