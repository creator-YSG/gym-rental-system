#!/bin/bash

# Flask 앱 재시작 및 IntegrationSync 동작 확인 스크립트

echo "=================================================="
echo "Flask 앱 재시작 및 IntegrationSync 확인"
echo "=================================================="
echo

# 1. 기존 Flask 프로세스 종료
echo "[1/4] 기존 Flask 프로세스 종료..."
pkill -f "python3.*run.py" 2>/dev/null
sleep 2
echo "✓ 완료"
echo

# 2. Flask 앱 시작
echo "[2/4] Flask 앱 시작..."
cd ~/gym-rental-system
nohup python3 run.py > /tmp/flask_app.log 2>&1 &
FLASK_PID=$!
echo "✓ Flask PID: $FLASK_PID"
sleep 5
echo

# 3. 로그 확인 (IntegrationSync 부분만)
echo "[3/4] IntegrationSync 로그 확인..."
echo "----------------------------------------"
grep -A5 "IntegrationSync\|락카키 대여기 IP" /tmp/flask_app.log | tail -20
echo "----------------------------------------"
echo

# 4. 프로세스 상태 확인
echo "[4/4] Flask 프로세스 상태 확인..."
if ps -p $FLASK_PID > /dev/null; then
    echo "✓ Flask 앱이 정상적으로 실행 중입니다 (PID: $FLASK_PID)"
else
    echo "✗ Flask 앱이 실행되지 않았습니다"
    echo
    echo "전체 로그:"
    cat /tmp/flask_app.log
    exit 1
fi
echo

echo "=================================================="
echo "완료! 전체 로그는 /tmp/flask_app.log 에서 확인하세요."
echo "=================================================="
echo
echo "실시간 로그 보기: tail -f /tmp/flask_app.log"

