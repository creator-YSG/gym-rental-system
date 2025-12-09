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
sheets_sync = None
sync_scheduler = None
event_logger = None


def create_app(config_name='default'):
    """Flask 애플리케이션 팩토리"""
    global mqtt_service, local_cache, sheets_sync, sync_scheduler, event_logger
    
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
    
    # SocketIO 초기화 (threading 모드 - paho-mqtt와 호환)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    
    # LocalCache 초기화
    try:
        from app.services.local_cache import LocalCache
        local_cache = LocalCache()
        app.local_cache = local_cache
        print("[App] LocalCache 초기화 완료")
    except Exception as e:
        print(f"[App] LocalCache 초기화 실패: {e}")
    
    # EventLogger 초기화
    try:
        from app.services.event_logger import EventLogger
        if local_cache:
            event_logger = EventLogger(local_cache)
            app.event_logger = event_logger
            print("[App] EventLogger 초기화 완료")
    except Exception as e:
        print(f"[App] EventLogger 초기화 실패: {e}")
    
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
        
        # 핸들러는 Sheets 초기화 후 한 번만 등록 (아래에서 처리)
        
        # MQTT 연결 (실패해도 앱은 계속 실행)
        if mqtt_service.connect():
            print("[App] MQTT 연결 성공")
        else:
            print("[App] MQTT 연결 실패 - 나중에 재시도")
        
        app.mqtt_service = mqtt_service
        
    except Exception as e:
        print(f"[App] MQTT 초기화 실패: {e}")
    
    # Google Sheets 동기화 초기화
    try:
        from app.services.sheets_sync import SheetsSync
        from app.services.sync_scheduler import SyncScheduler
        
        # credentials 경로 (라즈베리파이 또는 로컬)
        creds_path = os.path.join(os.path.dirname(app.root_path), 'config', 'credentials.json')
        
        if os.path.exists(creds_path) and local_cache:
            sheets_sync = SheetsSync(credentials_path=creds_path)
            
            if sheets_sync.connect():
                print("[App] Google Sheets 연결 성공")
                
                # config 다운로드
                config = sheets_sync.download_config()
                app.sheets_config = config
                
                # 시작 시 members 다운로드
                sheets_sync.download_members(local_cache)
                
                # 동기화 스케줄러 시작 (config에서 주기 읽기)
                sync_scheduler = SyncScheduler(
                    sheets_sync, 
                    local_cache,
                    event_interval=config.get('sync_interval_upload', 300),
                    device_interval=config.get('sync_interval_device', 60),
                    member_interval=config.get('sync_interval_members', 300)
                )
                sync_scheduler.start()
                
                app.sheets_sync = sheets_sync
                app.sync_scheduler = sync_scheduler
                
                # MQTT 핸들러 등록 (sheets_sync + event_logger 포함)
                if mqtt_service:
                    from app.services.mqtt_service import register_default_handlers
                    register_default_handlers(mqtt_service, local_cache, sheets_sync, event_logger)
                    print("[App] MQTT 핸들러 등록 완료 (Sheets + EventLogger 연동)")
            else:
                print("[App] Google Sheets 연결 실패")
                # Sheets 없이 핸들러만 등록
                if mqtt_service and local_cache:
                    from app.services.mqtt_service import register_default_handlers
                    register_default_handlers(mqtt_service, local_cache, None, event_logger)
                    print("[App] MQTT 핸들러 등록 완료 (Sheets 없음, EventLogger 있음)")
        else:
            print(f"[App] Google Sheets 건너뜀 (credentials 없음: {creds_path})")
            # Sheets 없이 핸들러만 등록
            if mqtt_service and local_cache:
                from app.services.mqtt_service import register_default_handlers
                register_default_handlers(mqtt_service, local_cache, None, event_logger)
                print("[App] MQTT 핸들러 등록 완료 (Sheets 없음, EventLogger 있음)")
            
    except Exception as e:
        print(f"[App] Google Sheets 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
    
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


def get_sheets_sync():
    """SheetsSync 인스턴스 반환"""
    return sheets_sync


def get_sync_scheduler():
    """SyncScheduler 인스턴스 반환"""
    return sync_scheduler


def get_event_logger():
    """EventLogger 인스턴스 반환"""
    return event_logger


