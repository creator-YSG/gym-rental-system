#!/bin/bash
# 키오스크 모드 종료 스크립트

echo "🛑 키오스크 모드 종료"

pkill -f chromium 2>/dev/null
pkill -f "python3 run.py" 2>/dev/null

echo "✅ 종료 완료"

