#!/bin/bash
#
# 모든 시나리오 일괄 캡쳐 스크립트
#
# 사용법:
#   ./run_all_scenarios.sh              # 화면만 캡쳐 (대여 실행 안함)
#   ./run_all_scenarios.sh --execute    # 실제 대여까지 수행
#

set -e

# 프로젝트 루트로 이동
cd "$(dirname "$0")/../.."

# 실행 옵션
EXECUTE_FLAG=""
if [ "$1" == "--execute" ] || [ "$1" == "--execute-rental" ]; then
    EXECUTE_FLAG="--execute-rental"
    echo "⚠️  실제 대여를 수행합니다 (금액권 차감됨)"
    echo "   계속하려면 5초 안에 Ctrl+C로 중단하세요..."
    sleep 5
else
    echo "ℹ️  화면만 캡쳐합니다 (실제 대여 안함)"
fi

echo ""
echo "========================================"
echo "🚀 모든 시나리오 캡쳐 시작"
echo "========================================"
echo ""

# 시나리오 정의
declare -A SCENARIOS=(
    ["A"]="01011111111"
    ["B"]="01022222222"
    ["C"]="01033333333"
    ["D1"]="01044444444"
    ["D2"]="01055555555"
    ["D3"]="01066666666"
)

# 순서대로 실행
for SCENARIO in A B C D1 D2 D3; do
    PHONE="${SCENARIOS[$SCENARIO]}"
    
    echo ""
    echo "----------------------------------------"
    echo "📸 시나리오 $SCENARIO 실행 중..."
    echo "   전화번호: $PHONE"
    echo "----------------------------------------"
    
    python3 scripts/testing/capture_screens.py \
        --scenario "$SCENARIO" \
        --phone "$PHONE" \
        $EXECUTE_FLAG
    
    echo "✅ 시나리오 $SCENARIO 완료"
    
    # 다음 시나리오 전 대기 (화면 초기화)
    if [ "$SCENARIO" != "D3" ]; then
        echo "   ⏳ 다음 시나리오 준비 중 (5초)..."
        sleep 5
    fi
done

echo ""
echo "========================================"
echo "✅ 모든 시나리오 캡쳐 완료!"
echo "========================================"
echo ""
echo "📁 스크린샷 위치: ~/screenshots/"
echo ""
echo "확인:"
echo "  ls -la ~/screenshots/"
echo ""

