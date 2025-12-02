#!/bin/bash
# F-BOX 키오스크 모드 실행 스크립트
# 키링 팝업 없이 바로 실행

# 기존 chromium 종료
pkill -f chromium 2>/dev/null
sleep 1

# Flask 서버 실행 (이미 실행 중이면 스킵)
if ! pgrep -f "python3 run.py" > /dev/null; then
    cd ~/gym-rental-system
    nohup python3 run.py > /tmp/flask.log 2>&1 &
    sleep 3
fi

# 키오스크 모드로 Chromium 실행 (키링 비활성화)
export DISPLAY=:0
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --password-store=basic \
    --disable-features=LockProfileCookieDatabase \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-translate \
    --disable-sync \
    --autoplay-policy=no-user-gesture-required \
    http://localhost:5000 \
    > /dev/null 2>&1 &

echo "✅ 키오스크 모드 실행 완료"

