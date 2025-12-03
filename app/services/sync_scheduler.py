"""
동기화 스케줄러

백그라운드에서 주기적으로 Google Sheets 동기화 실행
- event_logs 업로드: 5분마다
- rental_logs 업로드: 5분마다
- device_status 업데이트: 1분마다
- members 다운로드: 5분마다
"""

import threading
import time
from datetime import datetime
from typing import Optional
from pathlib import Path


class SyncScheduler:
    """동기화 스케줄러"""
    
    def __init__(self, sheets_sync, local_cache, 
                 event_interval: int = 300,
                 device_interval: int = 60,
                 member_interval: int = 300):
        """
        초기화
        
        Args:
            sheets_sync: SheetsSync 인스턴스
            local_cache: LocalCache 인스턴스
            event_interval: 이벤트/대여 동기화 간격 (초, 기본 5분)
            device_interval: 기기 상태 동기화 간격 (초, 기본 1분)
            member_interval: 회원 정보 동기화 간격 (초, 기본 5분)
        """
        self.sheets_sync = sheets_sync
        self.local_cache = local_cache
        
        self.event_interval = event_interval
        self.device_interval = device_interval
        self.member_interval = member_interval
        
        self._running = False
        self._threads = []
        
        print(f"[SyncScheduler] 초기화 완료")
        print(f"  - 이벤트/대여: {event_interval}초")
        print(f"  - 기기 상태: {device_interval}초")
        print(f"  - 회원 정보: {member_interval}초")
    
    def start(self):
        """스케줄러 시작"""
        if self._running:
            print("[SyncScheduler] 이미 실행 중")
            return
        
        self._running = True
        
        # 이벤트/대여 동기화 스레드
        t1 = threading.Thread(target=self._event_sync_loop, daemon=True)
        t1.start()
        self._threads.append(t1)
        
        # 기기 상태 동기화 스레드
        t2 = threading.Thread(target=self._device_sync_loop, daemon=True)
        t2.start()
        self._threads.append(t2)
        
        # 회원 정보 동기화 스레드
        t3 = threading.Thread(target=self._member_sync_loop, daemon=True)
        t3.start()
        self._threads.append(t3)
        
        print("[SyncScheduler] ✓ 시작됨")
    
    def stop(self):
        """스케줄러 중지"""
        self._running = False
        print("[SyncScheduler] 중지됨")
    
    def _event_sync_loop(self):
        """이벤트/대여 동기화 루프"""
        while self._running:
            try:
                self._sync_events()
            except Exception as e:
                print(f"[SyncScheduler] 이벤트 동기화 오류: {e}")
            
            time.sleep(self.event_interval)
    
    def _device_sync_loop(self):
        """기기 상태 동기화 루프"""
        while self._running:
            try:
                self._sync_device_status()
            except Exception as e:
                print(f"[SyncScheduler] 기기 상태 동기화 오류: {e}")
            
            time.sleep(self.device_interval)
    
    def _member_sync_loop(self):
        """회원 정보 동기화 루프"""
        while self._running:
            try:
                self._sync_members()
            except Exception as e:
                print(f"[SyncScheduler] 회원 동기화 오류: {e}")
            
            time.sleep(self.member_interval)
    
    def _sync_events(self):
        """이벤트 + 대여 로그 업로드"""
        if not self.sheets_sync:
            return
        
        # 이벤트 로그 업로드
        event_count = self.sheets_sync.upload_event_logs(self.local_cache)
        
        # 대여 로그 업로드
        rental_count = self.sheets_sync.upload_rentals(self.local_cache)
        
        if event_count > 0 or rental_count > 0:
            print(f"[SyncScheduler] 업로드: 이벤트 {event_count}건, 대여 {rental_count}건")
    
    def _sync_device_status(self):
        """기기 상태 업데이트"""
        if not self.sheets_sync:
            return
        
        # 기기 상태 업데이트
        self.sheets_sync.update_device_status(self.local_cache)
        # 상품 동기화는 boot_complete 이벤트 시 즉시 처리됨
    
    def _sync_members(self):
        """회원 정보 다운로드"""
        if not self.sheets_sync:
            return
        
        count = self.sheets_sync.download_members(self.local_cache)
        if count > 0:
            self.local_cache.reload_members()
            print(f"[SyncScheduler] 회원 정보 동기화: {count}명")
    
    def sync_now(self):
        """즉시 전체 동기화 실행"""
        print("[SyncScheduler] 즉시 동기화 시작...")
        
        try:
            self._sync_events()
            self._sync_device_status()
            self._sync_members()
            print("[SyncScheduler] 즉시 동기화 완료")
        except Exception as e:
            print(f"[SyncScheduler] 즉시 동기화 오류: {e}")


# 전역 스케줄러 인스턴스 (앱에서 사용)
_scheduler: Optional[SyncScheduler] = None


def get_scheduler() -> Optional[SyncScheduler]:
    """전역 스케줄러 인스턴스 반환"""
    return _scheduler


def init_scheduler(sheets_sync, local_cache, auto_start: bool = True) -> SyncScheduler:
    """
    스케줄러 초기화 및 시작
    
    Args:
        sheets_sync: SheetsSync 인스턴스
        local_cache: LocalCache 인스턴스
        auto_start: 자동 시작 여부
    
    Returns:
        SyncScheduler 인스턴스
    """
    global _scheduler
    
    _scheduler = SyncScheduler(sheets_sync, local_cache)
    
    if auto_start:
        _scheduler.start()
    
    return _scheduler

