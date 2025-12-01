#!/bin/bash
# 키오스크 모드 시작 스크립트

echo "🏃 키오스크 모드 시작"

# 화면 보호기 및 절전 모드 비활성화
export DISPLAY=:0
xset s off          # 화면 보호기 끄기
xset -dpms          # 절전 모드 끄기
xset s noblank      # 화면 꺼짐 방지

# 마우스 커서 숨기기 (1초 후)
unclutter -idle 1 -root &

# Flask 서버 시작
cd /home/pi/gym-rental-system
python3 run.py &

# 서버가 시작될 때까지 대기
sleep 5

# Chromium 키오스크 모드로 시작 (키링 비밀번호 묻지 않음)
chromium-browser \
    --kiosk \
    --password-store=basic \
    --window-size=600,1024 \
    --window-position=0,0 \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --check-for-update-interval=31536000 \
    --no-first-run \
    http://localhost:5000

