#!/bin/bash

# NFC 로그인 전체 플로우 테스트 스크립트

echo "=================================================="
echo "NFC 로그인 전체 플로우 테스트"
echo "=================================================="
echo

# 1. 기존 프로세스 종료
echo "[1/5] 기존 프로세스 종료..."
pkill -f "chromium-browser" 2>/dev/null
pkill -f "python3.*run.py" 2>/dev/null
sleep 3
echo "✓ 완료"
echo

# 2. Flask 앱 시작
echo "[2/5] Flask 앱 시작..."
cd ~/gym-rental-system
nohup python3 run.py > /tmp/flask_app.log 2>&1 &
FLASK_PID=$!
echo "✓ Flask PID: $FLASK_PID"
sleep 5
echo

# 3. Flask 앱 상태 확인
echo "[3/5] Flask 앱 상태 확인..."
if ps -p $FLASK_PID > /dev/null; then
    echo "✓ Flask 앱 실행 중"
    
    # IntegrationSync 로그 확인
    echo
    echo "IntegrationSync 로그:"
    echo "----------------------------------------"
    grep "IntegrationSync\|락카키 대여기 IP" /tmp/flask_app.log | tail -5
    echo "----------------------------------------"
else
    echo "✗ Flask 앱이 실행되지 않았습니다"
    cat /tmp/flask_app.log
    exit 1
fi
echo

# 4. 키오스크 모드 시작
echo "[4/5] 키오스크 모드 시작..."
export DISPLAY=:0
nohup chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI \
    http://localhost:5000 > /tmp/kiosk.log 2>&1 &
KIOSK_PID=$!
echo "✓ 키오스크 PID: $KIOSK_PID"
sleep 5
echo

# 5. NFC UID 주입 테스트
echo "[5/5] NFC UID 주입 테스트..."
echo
echo "NFC UID: 5A41B914524189"
echo "회원: 쩐부테쑤안 (20240861)"
echo
echo "주입 중..."

curl -X POST http://localhost:5000/api/test/nfc-inject \
    -H 'Content-Type: application/json' \
    -d '{"nfc_uid":"5A41B914524189"}' \
    2>/dev/null | python3 -m json.tool

echo
echo "=================================================="
echo "테스트 완료!"
echo "=================================================="
echo
echo "화면이 전환되었는지 확인하세요."
echo "실시간 로그: tail -f /tmp/flask_app.log"
echo "키오스크 로그: tail -f /tmp/kiosk.log"

