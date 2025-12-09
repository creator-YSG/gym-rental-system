#!/bin/bash
# NFC 로그인 전체 플로우 테스트

cd "$(dirname "$0")/../.."

echo "=================================="
echo "NFC 로그인 전체 플로우 테스트"
echo "=================================="
echo ""

NFC_UID="${1:-5A41B914524189}"

echo "[1단계] 락카키 대여기 API 테스트"
echo "  GET http://192.168.0.23:5000/api/member/by-nfc/$NFC_UID"
echo ""

curl -s "http://192.168.0.23:5000/api/member/by-nfc/$NFC_UID" | python3 -m json.tool

echo ""
echo ""
echo "[2단계] 운동복 대여기 로그인 API 테스트"
echo "  먼저 member_id 추출..."
echo ""

MEMBER_ID=$(curl -s "http://192.168.0.23:5000/api/member/by-nfc/$NFC_UID" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('member_id', ''))" 2>/dev/null)

if [ -n "$MEMBER_ID" ]; then
    echo "  member_id: $MEMBER_ID"
    echo ""
    echo "  POST http://localhost:5000/api/auth/member_id"
    echo ""
    
    curl -s -X POST http://localhost:5000/api/auth/member_id \
        -H "Content-Type: application/json" \
        -d "{\"member_id\": \"$MEMBER_ID\"}" | python3 -m json.tool
    
    echo ""
    echo ""
    echo "✅ 테스트 완료!"
    echo ""
    echo "💡 다음 단계:"
    echo "   1. 웹 브라우저에서 http://localhost:5000 열기"
    echo "   2. NFC 카드 태그 (시뮬레이션)"
    echo "   3. 자동으로 로그인되어 /rental로 이동"
    echo ""
else
    echo "  ❌ 회원 정보를 찾을 수 없습니다"
    echo ""
    echo "  가능한 원인:"
    echo "   - 락카키 대여기 서버가 실행되지 않음 (http://192.168.0.23:5000)"
    echo "   - NFC UID가 등록되지 않음 ($NFC_UID)"
    echo "   - 락카가 비어있음"
    echo ""
fi

echo "=================================="

