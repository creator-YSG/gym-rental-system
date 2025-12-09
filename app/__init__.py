"""
운동복/수건 대여 시스템 - Flask 애플리케이션
"""
import os
import queue
from flask import Flask, jsonify
from flask_socketio import SocketIO

# SocketIO 인스턴스 (전역)
socketio = SocketIO()

# NFC 이벤트 큐 (전역)
nfc_queue = queue.Queue(maxsize=10)

# 전역 서비스 인스턴스
mqtt_service = None
local_cache = None
sheets_sync = None
sync_scheduler = None
event_logger = None
nfc_reader = None
locker_api_client = None


def create_app(config_name='default'):
    """Flask 애플리케이션 팩토리"""
    global mqtt_service, local_cache, sheets_sync, sync_scheduler, event_logger, nfc_reader, locker_api_client
    
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
    
    # NFC 큐를 app에 등록
    app.nfc_queue = nfc_queue
    
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
    
    # NFC 리더 및 락카키 대여기 API 클라이언트 초기화
    try:
        from app.services.nfc_reader import NFCReaderService
        from app.services.locker_api_client import LockerAPIClient
        from app.services.integration_sync import IntegrationSync
        
        # 락카키 대여기 API 주소 가져오기 (IntegrationSync 사용)
        try:
            print("[App] 락카키 대여기 IP 다운로드 시도 (System_Integration 시트)...")
            integration_sync = IntegrationSync()
            locker_api_info = integration_sync.download_locker_api_info()
            locker_api_url = locker_api_info['url']
            print(f"[App] ✓ 락카키 대여기 IP 다운로드 성공: {locker_api_url}")
            print(f"     - 마지막 업데이트: {locker_api_info.get('last_updated', 'N/A')}")
            print(f"     - 상태: {locker_api_info.get('status', 'unknown')}")
        except Exception as e:
            # 실패 시 환경변수 또는 기본값 사용
            locker_api_url = os.getenv('LOCKER_API_URL', 'http://192.168.0.23:5000')
            print(f"[App] ⚠️ 락카키 대여기 IP 다운로드 실패: {e}")
            print(f"[App] 기본값 사용: {locker_api_url}")
            import traceback
            traceback.print_exc()
        
        # 락카키 대여기 API 클라이언트
        locker_api_client = LockerAPIClient(base_url=locker_api_url)
        app.locker_api_client = locker_api_client
        
        # 헬스 체크
        if locker_api_client.health_check():
            print(f"[App] 락카키 대여기 API 연결 성공: {locker_api_url}")
        else:
            print(f"[App] 락카키 대여기 API 연결 실패: {locker_api_url}")
        
        # NFC 리더 초기화
        nfc_port = os.getenv('NFC_PORT', '/dev/ttyUSB0')
        nfc_reader = NFCReaderService(port=nfc_port)
        app.nfc_reader = nfc_reader
        
        # NFC 태그 감지 시 처리 함수
        def handle_nfc_tag(nfc_uid: str):
            """NFC 태그 감지 시 실행 - 락카키 대여기 API 호출 후 큐에 저장"""
            print(f"[App] NFC 태그 감지: {nfc_uid}")
            
            # 락카키 대여기 API 호출하여 member_id 가져오기
            member = locker_api_client.get_member_by_nfc(nfc_uid)
            
            if member and member.get('member_id'):
                member_id = member['member_id']
                name = member.get('name', '')
                locker_number = member.get('locker_number', '')
                
                print(f"[App] ✓ 회원 조회 성공: {name} ({member_id}), 락카: {locker_number}")
                
                # NFC 이벤트를 큐에 저장 (폴링 방식)
                try:
                    nfc_queue.put_nowait({
                        'nfc_uid': nfc_uid,
                        'member_id': member_id,
                        'name': name,
                        'locker_number': locker_number,
                        'success': True
                    })
                    print(f"[App] NFC 이벤트 큐에 추가: {member_id}")
                except queue.Full:
                    # 큐가 꽉 찼으면 기존 데이터 제거 후 재시도
                    try:
                        nfc_queue.get_nowait()
                        nfc_queue.put_nowait({
                            'nfc_uid': nfc_uid,
                            'member_id': member_id,
                            'name': name,
                            'locker_number': locker_number,
                            'success': True
                        })
                        print(f"[App] NFC 이벤트 큐에 추가 (기존 데이터 덮어씀): {member_id}")
                    except:
                        print(f"[App] ✗ NFC 이벤트 큐 추가 실패")
            else:
                # 오류 이벤트를 큐에 저장
                try:
                    nfc_queue.put_nowait({
                        'nfc_uid': nfc_uid,
                        'success': False,
                        'message': '락카가 배정되어 있지 않습니다'
                    })
                    print(f"[App] NFC 오류 이벤트 큐에 추가: {nfc_uid}")
                except queue.Full:
                    try:
                        nfc_queue.get_nowait()
                        nfc_queue.put_nowait({
                            'nfc_uid': nfc_uid,
                            'success': False,
                            'message': '락카가 배정되어 있지 않습니다'
                        })
                    except:
                        print(f"[App] ✗ NFC 오류 이벤트 큐 추가 실패")
                print(f"[App] ✗ 회원 정보 없음: NFC {nfc_uid}")
        
        # 콜백 등록
        nfc_reader.set_callback(handle_nfc_tag)
        
        # NFC 리더 시작
        nfc_reader.start()
        
        print("[App] NFC 리더 서비스 시작")
        
    except ImportError as e:
        print(f"[App] NFC 리더 모듈 임포트 실패: {e}")
        print("[App] pyserial 설치 필요: pip install pyserial")
    except Exception as e:
        print(f"[App] NFC 리더 초기화 실패: {e}")
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


def get_nfc_reader():
    """NFC 리더 인스턴스 반환"""
    return nfc_reader


def get_locker_api_client():
    """락카키 대여기 API 클라이언트 반환"""
    return locker_api_client


