#!/bin/bash
# 간단한 수동 캡쳐 스크립트

export DISPLAY=:0

# 홈 화면 캡쳐
echo "📸 01. 홈 화면 캡쳐..."
scrot ~/screenshots/manual_01_home.png
sleep 1

# JavaScript 실행으로 전화번호 입력 + 로그인
echo "⌨️  전화번호 입력 및 로그인 (JavaScript)..."
xdotool key F12  # 개발자 도구 열기
sleep 1

# 콘솔에 JavaScript 입력
xdotool type --delay 50 "phoneNumbers = '01055555555'; updatePhoneDisplay();"
xdotool key Return
sleep 0.5

xdotool type --delay 50 "document.querySelector('#loginBtn').click();"
xdotool key Return
sleep 3

# F12로 개발자 도구 닫기
xdotool key F12
sleep 0.5

# 상품 선택 화면 캡쳐
echo "📸 02. 상품 선택 화면 캡쳐..."
scrot ~/screenshots/manual_02_rental.png

echo "✅ 완료!"

