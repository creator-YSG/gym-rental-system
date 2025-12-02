#!/bin/bash
# Mosquitto MQTT 브로커 설치 스크립트
# 라즈베리파이용

echo "=========================================="
echo "Mosquitto MQTT 브로커 설치"
echo "=========================================="

# 패키지 업데이트
echo "[1/5] 패키지 목록 업데이트..."
sudo apt update

# Mosquitto 설치
echo "[2/5] Mosquitto 설치..."
sudo apt install -y mosquitto mosquitto-clients

# 설정 파일 생성
echo "[3/5] 설정 파일 생성..."
sudo tee /etc/mosquitto/conf.d/fbox.conf > /dev/null << 'EOF'
# F-BOX MQTT 브로커 설정

# 리스너 설정
listener 1883
protocol mqtt

# 인증 없이 접속 허용 (로컬 네트워크용)
allow_anonymous true

# 로그 설정
log_dest file /var/log/mosquitto/mosquitto.log
log_type all

# 연결 유지 설정
max_keepalive 120

# 메시지 설정
max_inflight_messages 20
max_queued_messages 100

# 영속성 설정 (재시작 시 메시지 유지)
persistence true
persistence_location /var/lib/mosquitto/
EOF

# 서비스 활성화 및 시작
echo "[4/5] Mosquitto 서비스 시작..."
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# 상태 확인
echo "[5/5] 설치 확인..."
sleep 2

if systemctl is-active --quiet mosquitto; then
    echo ""
    echo "=========================================="
    echo "✅ Mosquitto 설치 완료!"
    echo "=========================================="
    echo "브로커 주소: localhost:1883"
    echo ""
    echo "테스트 방법:"
    echo "  터미널 1: mosquitto_sub -t 'test'"
    echo "  터미널 2: mosquitto_pub -t 'test' -m 'hello'"
    echo ""
    echo "F-BOX 토픽 구독:"
    echo "  mosquitto_sub -t 'fbox/#' -v"
    echo "=========================================="
else
    echo ""
    echo "❌ Mosquitto 시작 실패"
    echo "로그 확인: sudo journalctl -u mosquitto"
    exit 1
fi

