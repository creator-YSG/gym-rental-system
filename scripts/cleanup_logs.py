#!/usr/bin/env python3
"""
오래된 로그 삭제 스크립트

- mqtt_events: 7일 초과 삭제
- 매일 cron으로 실행 권장

사용법:
    python3 scripts/cleanup_logs.py

crontab 설정 (매일 새벽 3시):
    0 3 * * * cd /home/pi/gym-rental-system && python3 scripts/cleanup_logs.py >> /tmp/cleanup.log 2>&1
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'instance' / 'fbox_local.db'

# 보관 기간 설정 (일)
MQTT_EVENTS_RETENTION_DAYS = 7


def cleanup_mqtt_events(conn, days: int = MQTT_EVENTS_RETENTION_DAYS) -> int:
    """
    오래된 mqtt_events 삭제
    
    Args:
        conn: SQLite 연결
        days: 보관 기간 (일)
    
    Returns:
        삭제된 행 수
    """
    cursor = conn.cursor()
    
    # 삭제 기준 날짜
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    # 삭제 전 카운트
    cursor.execute('SELECT COUNT(*) FROM mqtt_events WHERE created_at < ?', (cutoff_date,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        cursor.execute('DELETE FROM mqtt_events WHERE created_at < ?', (cutoff_date,))
        conn.commit()
        print(f"[Cleanup] mqtt_events: {count}건 삭제 (기준: {days}일 초과)")
    else:
        print(f"[Cleanup] mqtt_events: 삭제할 항목 없음")
    
    return count


def get_db_stats(conn) -> dict:
    """DB 통계 조회"""
    cursor = conn.cursor()
    
    stats = {}
    
    # mqtt_events 통계
    cursor.execute('SELECT COUNT(*) FROM mqtt_events')
    stats['mqtt_events_total'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT MIN(created_at), MAX(created_at) FROM mqtt_events')
    row = cursor.fetchone()
    stats['mqtt_events_oldest'] = row[0]
    stats['mqtt_events_newest'] = row[1]
    
    # event_logs 통계
    try:
        cursor.execute('SELECT COUNT(*) FROM event_logs')
        stats['event_logs_total'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM event_logs WHERE synced_to_sheets = 0')
        stats['event_logs_unsynced'] = cursor.fetchone()[0]
    except:
        stats['event_logs_total'] = 0
        stats['event_logs_unsynced'] = 0
    
    return stats


def vacuum_db(conn):
    """DB 최적화 (VACUUM)"""
    print("[Cleanup] VACUUM 실행 중...")
    conn.execute('VACUUM')
    print("[Cleanup] VACUUM 완료")


def main():
    print("=" * 50)
    print(f"[Cleanup] 로그 정리 시작: {datetime.now().isoformat()}")
    print("=" * 50)
    
    if not DB_PATH.exists():
        print(f"[Cleanup] 오류: DB 파일 없음 ({DB_PATH})")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH))
    
    try:
        # 삭제 전 통계
        print("\n[Before]")
        stats_before = get_db_stats(conn)
        print(f"  mqtt_events: {stats_before['mqtt_events_total']}건")
        print(f"  event_logs: {stats_before['event_logs_total']}건 (미동기화: {stats_before['event_logs_unsynced']}건)")
        
        # mqtt_events 정리
        print()
        deleted = cleanup_mqtt_events(conn, MQTT_EVENTS_RETENTION_DAYS)
        
        # 삭제 후 통계
        print("\n[After]")
        stats_after = get_db_stats(conn)
        print(f"  mqtt_events: {stats_after['mqtt_events_total']}건")
        
        # VACUUM (삭제된 항목이 많으면 실행)
        if deleted > 100:
            print()
            vacuum_db(conn)
        
        print()
        print("=" * 50)
        print(f"[Cleanup] 완료: {datetime.now().isoformat()}")
        print("=" * 50)
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()

