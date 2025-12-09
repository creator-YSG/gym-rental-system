#!/bin/bash
# 코드 동기화 스크립트 (로컬 → 라즈베리파이)

echo "🔄 코드 동기화 중..."
echo "   로컬 → 192.168.0.27"
echo ""

# 제외할 파일들
EXCLUDE="--exclude instance/*.db --exclude __pycache__ --exclude '*.pyc' --exclude .git --exclude venv"

# rsync로 동기화
rsync -av --progress $EXCLUDE \
  /Users/yunseong-geun/Projects/gym-rental-system/ \
  pi@192.168.0.27:~/gym-rental-system/

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 동기화 완료!"
else
    echo ""
    echo "❌ 동기화 실패"
    exit 1
fi


