#!/bin/bash
# 키오스크 모드 시작 스크립트
# 키링 팝업 없이 바로 실행

echo "🏃 키오스크 모드 시작"

# 기존 프로세스 정리
pkill -f chromium 2>/dev/null
sleep 1

# 화면 보호기 및 절전 모드 비활성화
export DISPLAY=:0
xset s off          # 화면 보호기 끄기
xset -dpms          # 절전 모드 끄기
xset s noblank      # 화면 꺼짐 방지

# 마우스 커서 숨기기 (1초 후)
unclutter -idle 1 -root &

# Flask 서버 시작 (이미 실행 중이면 스킵)
if ! pgrep -f "python3 run.py" > /dev/null; then
    cd /home/pi/gym-rental-system
    nohup python3 run.py > /tmp/flask.log 2>&1 &
    sleep 3
fi

# Chromium 키오스크 모드로 시작 (키링 비밀번호 묻지 않음)
chromium-browser \
    --kiosk \
    --password-store=basic \
    --disable-features=LockProfileCookieDatabase \
    --window-size=600,1024 \
    --window-position=0,0 \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --check-for-update-interval=31536000 \
    --no-first-run \
    --disable-translate \
    --disable-sync \
    --autoplay-policy=no-user-gesture-required \
    http://localhost:5000 &

echo "✅ 키오스크 모드 실행 완료"


