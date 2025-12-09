"""
NFC 리더 서비스
ESP32로부터 NFC UID를 시리얼로 수신
"""

import serial
import json
import threading
import time
from typing import Callable, Optional


class NFCReaderService:
    """ESP32 NFC 리더와 시리얼 통신"""
    
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200):
        """
        초기화
        
        Args:
            port: 시리얼 포트 (예: /dev/ttyUSB0, /dev/ttyACM0)
            baudrate: 통신 속도 (ESP32와 동일해야 함)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # NFC UID 수신 콜백
        self.on_nfc_detected: Optional[Callable[[str], None]] = None
        
    def connect(self) -> bool:
        """시리얼 포트 연결"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            print(f"[NFC Reader] ✓ 연결 성공: {self.port}")
            return True
        except serial.SerialException as e:
            print(f"[NFC Reader] ✗ 연결 실패: {e}")
            print(f"[NFC Reader] 포트 확인: ls -l /dev/ttyUSB* /dev/ttyACM*")
            return False
        except Exception as e:
            print(f"[NFC Reader] ✗ 예외 발생: {e}")
            return False
    
    def start(self):
        """백그라운드 스레드에서 NFC UID 수신 시작"""
        if self.running:
            print("[NFC Reader] 이미 실행 중")
            return
        
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.connect():
                print("[NFC Reader] 시리얼 연결 실패, 건너뜀")
                return
        
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        print("[NFC Reader] 시리얼 리스닝 시작")
    
    def stop(self):
        """NFC 리더 중지"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print("[NFC Reader] 중지")
    
    def _read_loop(self):
        """시리얼 데이터 읽기 루프"""
        while self.running:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    
                    if line:
                        self._process_line(line)
                        
            except serial.SerialException as e:
                print(f"[NFC Reader] 시리얼 오류: {e}")
                time.sleep(1.0)
            except Exception as e:
                print(f"[NFC Reader] 읽기 오류: {e}")
                time.sleep(1.0)
    
    def _process_line(self, line: str):
        """
        ESP32로부터 수신한 라인 처리
        
        예상 형식: {"nfc_uid":"5A41B914524189"}
        """
        try:
            data = json.loads(line)
            nfc_uid = data.get('nfc_uid')
            
            if nfc_uid:
                print(f"[NFC Reader] ← NFC 태그 감지: {nfc_uid}")
                
                # 콜백 실행
                if self.on_nfc_detected:
                    try:
                        self.on_nfc_detected(nfc_uid)
                    except Exception as e:
                        print(f"[NFC Reader] 콜백 실행 오류: {e}")
            else:
                print(f"[NFC Reader] nfc_uid 없음: {line}")
                
        except json.JSONDecodeError:
            # JSON이 아닌 일반 텍스트 (디버그 메시지 등)
            if line.startswith('{'):
                print(f"[NFC Reader] JSON 파싱 실패: {line}")
            else:
                # 디버그 메시지는 무시
                pass
        except Exception as e:
            print(f"[NFC Reader] 처리 오류: {e}")
    
    def set_callback(self, callback: Callable[[str], None]):
        """
        NFC UID 수신 시 실행할 콜백 등록
        
        Args:
            callback: NFC UID를 인자로 받는 함수
        """
        self.on_nfc_detected = callback
        print("[NFC Reader] 콜백 등록 완료")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.serial_conn is not None and self.serial_conn.is_open


# 사용 예시
if __name__ == '__main__':
    def handle_nfc(nfc_uid: str):
        print(f"콜백 실행: NFC UID = {nfc_uid}")
        # 여기서 락카키 대여기 API 호출
    
    reader = NFCReaderService(port='/dev/ttyUSB0')
    reader.set_callback(handle_nfc)
    reader.start()
    
    try:
        print("NFC 리더 실행 중... (Ctrl+C로 종료)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n종료 중...")
        reader.stop()

