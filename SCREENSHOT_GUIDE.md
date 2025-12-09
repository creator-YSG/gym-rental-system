# 📸 화면 캡쳐 자동화 가이드

라즈베리파이에서 키오스크 화면을 자동으로 캡쳐하는 완벽 가이드입니다.

---

## 🎯 목표

회원 유형별 6가지 시나리오의 모든 화면을 자동으로 캡쳐하여 문서화 및 테스트에 활용합니다.

### 캡쳐 대상 (총 약 45장)

| 시나리오 | 설명 | 화면 수 |
|---------|------|--------|
| A | 이용권 없는 회원 | 6장 |
| B | 구독권만 있는 회원 | 9장 |
| C | 금액권만 있는 회원 | 9장 |
| D1 | 구독권+금액권 (구독권 커버) | 8장 |
| D2 | 구독권+금액권 (혼합 결제) ⭐ | 12장 |
| D3 | 구독권 소진+금액권 | 7장 |

---

## 🚀 빠른 시작 (라즈베리파이에서)

### 1️⃣ 코드 동기화

```bash
# 로컬에서 실행
./scripts/deployment/sync_code.sh
```

### 2️⃣ 테스트 데이터 생성

```bash
# 라즈베리파이에 SSH 접속 후
cd ~/gym-rental-system
python3 scripts/testing/setup_test_data.py
```

출력 예시:
```
🚀 테스트 데이터 생성 스크립트
====================================
...
✅ 테스트 데이터 생성 완료!
```

### 3️⃣ 키오스크 앱 실행

```bash
# 이미 실행 중이면 재시작
~/gym-rental-system/scripts/deployment/stop_kiosk.sh
~/gym-rental-system/scripts/deployment/start_kiosk.sh
```

### 4️⃣ 필요한 도구 설치 (최초 1회)

```bash
sudo apt update
sudo apt install xdotool scrot -y
```

### 5️⃣ 모든 시나리오 캡쳐 실행

```bash
cd ~/gym-rental-system

# 방법 1: 화면만 캡쳐 (권장, 데이터 변경 없음)
./scripts/testing/run_all_scenarios.sh

# 방법 2: 실제 대여까지 수행 (금액권 차감됨)
./scripts/testing/run_all_scenarios.sh --execute
```

### 6️⃣ 결과 확인

```bash
# 캡쳐된 스크린샷 확인
ls -la ~/screenshots/

# 특정 시나리오 확인
ls -la ~/screenshots/D2_both_mixed_*/
```

### 7️⃣ 로컬로 복사 (선택)

```bash
# 로컬 컴퓨터에서 실행
scp -r pi@192.168.0.27:~/screenshots/ ./pi_screenshots/
```

---

## 📋 시나리오별 상세 정보

### 시나리오 A: 이용권 없는 회원

**회원 정보:**
- 전화번호: `01011111111`
- 이름: 이용권없음
- 이용권: 없음

**캡쳐 화면:**
1. 홈 화면 (초기)
2. 홈 화면 (전화번호 입력 중)
3. 홈 화면 (로딩)
4. 상품 선택 화면 (이용권 없음 표시)
5. 마이페이지 (빈 상태)
6. 대여 불가 상태

**수동 캡쳐:**
```bash
python3 scripts/testing/capture_screens.py --scenario A --phone 01011111111
```

---

### 시나리오 B: 구독권만 있는 회원

**회원 정보:**
- 전화번호: `01022222222`
- 이름: 구독권만
- 구독권: 상의 3회 / 하의 3회 / 수건 3회

**특징:**
- 결제 모달 없이 바로 비밀번호 입력
- 자동 배정 방식

**캡쳐 화면:**
1. 홈 화면
2. 상품 선택 화면 (구독권 정보 표시)
3. 마이페이지 (구독권 섹션)
4. 장바구니
5. 비밀번호 모달 (바로 진입!)
6. 비밀번호 입력 중
7. 대여 완료 화면

**수동 캡쳐:**
```bash
python3 scripts/testing/capture_screens.py --scenario B --phone 01022222222
```

---

### 시나리오 C: 금액권만 있는 회원

**회원 정보:**
- 전화번호: `01033333333`
- 이름: 금액권만
- 금액권: 50,000원

**특징:**
- 결제 모달 없이 바로 비밀번호 입력
- 자동 배정 방식

**캡쳐 화면:**
1. 홈 화면
2. 상품 선택 화면 (금액권 정보 표시)
3. 마이페이지 (금액권 섹션)
4. 장바구니
5. 비밀번호 모달 (바로 진입!)
6. 비밀번호 입력 중
7. 대여 완료 화면 (금액 차감 내역)

**수동 캡쳐:**
```bash
python3 scripts/testing/capture_screens.py --scenario C --phone 01033333333
```

---

### 시나리오 D1: 구독권 + 금액권 (구독권으로 전부 커버)

**회원 정보:**
- 전화번호: `01044444444`
- 이름: 구독금액둘다
- 구독권: 상의 3회 / 하의 3회
- 금액권: 10,000원

**특징:**
- 결제 확인 모달 표시 (구독권 자동 적용 섹션만)
- 금액권 결제 섹션 없음

**캡쳐 화면:**
1. 상품 선택 화면 (구독권 + 금액권 정보)
2. 마이페이지 (두 섹션 모두)
3. 장바구니
4. **결제 확인 모달** (구독권만 표시)
5. 비밀번호 모달
6. 대여 완료 화면

**수동 캡쳐:**
```bash
python3 scripts/testing/capture_screens.py --scenario D1 --phone 01044444444
```

---

### 시나리오 D2: 구독권 + 금액권 (혼합 결제) ⭐ 핵심!

**회원 정보:**
- 전화번호: `01055555555`
- 이름: 구독일부금액일부
- 구독권: 상의 1회 / 하의 0회 (거의 소진)
- 금액권: 5,000원 + 3,000원 (2개, 쪼개기 테스트)

**특징:**
- 가장 복잡한 시나리오
- 결제 확인 모달에 구독권 + 금액권 섹션 모두 표시
- 금액권 쪼개기 UI 표시
- 숫자 키패드 표시

**캡쳐 화면:**
1. 상품 선택 화면
2. 장바구니 (상의 2개 - 구독권 한도 초과)
3. **결제 확인 모달**
   - 구독권 자동 적용: 상의 1개
   - 금액권 결제: 상의 1개 = 1,000원
4. **금액권 쪼개기 UI**
   - 금액권 1: 5,000원
   - 금액권 2: 3,000원
5. **숫자 키패드** (금액 입력)
6. 비밀번호 모달
7. 대여 완료 화면 (혼합 결제 내역)

**수동 캡쳐:**
```bash
python3 scripts/testing/capture_screens.py --scenario D2 --phone 01055555555
```

---

### 시나리오 D3: 구독권 소진 + 금액권

**회원 정보:**
- 전화번호: `01066666666`
- 이름: 구독소진금액만
- 구독권: 상의 1회 / 하의 1회 (오늘 이미 사용, 소진)
- 금액권: 10,000원

**특징:**
- 구독권이 있지만 오늘 이미 사용하여 0회 남음
- 결제 확인 모달에 금액권 섹션만 표시

**캡쳐 화면:**
1. 상품 선택 화면 (구독권 0회 표시)
2. 마이페이지 (구독권 소진 상태)
3. 결제 확인 모달 (금액권만!)
4. 비밀번호 모달
5. 대여 완료 화면

**수동 캡쳐:**
```bash
python3 scripts/testing/capture_screens.py --scenario D3 --phone 01066666666
```

---

## 🛠️ 문제 해결

### 1. 클릭 위치가 맞지 않음

스크립트의 좌표는 **1280x800 해상도** 기준입니다.

**해상도 확인:**
```bash
xdpyinfo | grep dimensions
```

**좌표 조정:**
1. 마우스를 버튼 위로 이동
2. 터미널에서 실행: `xdotool getmouselocation`
3. 출력된 좌표를 `capture_screens.py`에 반영

**예시:**
```python
# scripts/testing/capture_screens.py 수정
keypad_positions = {
    '0': (640, 580),  # ← 실제 좌표로 변경
    '1': (540, 420),
    # ...
}
```

### 2. 브라우저 윈도우를 찾을 수 없음

**원인:** 윈도우 타이틀이 다름

**해결:**
```bash
# 현재 열린 윈도우 목록 확인
xdotool search --name "" getwindowname %@

# 키오스크 브라우저 윈도우 찾기
xdotool search --name "Chromium" getwindowname %@
```

`capture_screens.py`에서 `WINDOW_TITLE` 수정:
```python
WINDOW_TITLE = "실제_윈도우_이름"
```

### 3. 스크립트가 너무 빠름

UI 렌더링이 늦을 경우:

```python
# capture_screens.py의 wait() 시간 증가
self.wait(2.0)  # 1.0 → 2.0으로 변경
```

### 4. 테스트 데이터 초기화

```bash
# 데이터베이스 백업
cp ~/gym-rental-system/instance/fbox_local.db ~/fbox_local.db.backup

# 테스트 데이터 재생성
cd ~/gym-rental-system
python3 scripts/testing/setup_test_data.py
```

---

## 📊 캡쳐 결과 구조

```
~/screenshots/
├── A_no_payment_20241209_143022/
│   ├── 01_home_initial.png
│   ├── 02_home_input_partial.png
│   ├── 03_home_input_complete.png
│   ├── 04_home_loading.png
│   ├── 05_rental_initial.png
│   └── 06_mypage_panel.png
│
├── B_subscription_only_20241209_143145/
│   ├── 01_home_initial.png
│   ├── 02_home_input_partial.png
│   ├── 03_home_input_complete.png
│   ├── 04_home_loading.png
│   ├── 05_rental_initial.png
│   ├── 06_mypage_panel.png
│   ├── 07_rental_cart_one.png
│   ├── 08_password_modal.png
│   ├── 09_password_input_partial.png
│   ├── 10_password_input_complete.png
│   └── 11_complete_screen.png (--execute-rental 시)
│
├── C_voucher_only_20241209_143312/
│   └── ... (B와 유사)
│
├── D1_both_sub_covers_20241209_143428/
│   ├── ...
│   ├── 07_payment_modal.png           ← 구독권만 표시
│   └── ...
│
├── D2_both_mixed_20241209_143530/      ⭐ 핵심!
│   ├── 01_home_initial.png
│   ├── ...
│   ├── 07_rental_cart_two.png         ← 상품 2개
│   ├── 08_payment_modal.png           ← 구독권 + 금액권
│   ├── 09_numpad_overlay.png          ← 금액 쪼개기
│   ├── 10_password_modal.png
│   ├── 11_password_input_partial.png
│   ├── 12_password_input_complete.png
│   └── 13_complete_screen.png
│
└── D3_sub_exhausted_20241209_143712/
    └── ... (구독권 소진 상태)
```

---

## ⚠️ 주의사항

### 실제 대여 플래그 (`--execute-rental`)

- 이 옵션을 사용하면 **실제로 금액권이 차감**됩니다
- 테스트 후 데이터를 다시 생성해야 할 수 있습니다
- **권장:** 일단 화면만 캡쳐하고, 필요시 특정 시나리오만 실행

### 데이터 백업

```bash
# 실제 대여 실행 전 DB 백업
cp ~/gym-rental-system/instance/fbox_local.db \
   ~/gym-rental-system/instance/fbox_local.db.backup_$(date +%Y%m%d_%H%M%S)
```

### 화면 해상도

- 스크립트는 **1280x800** 기준
- 다른 해상도에서는 좌표 조정 필수

---

## 🎓 다음 단계

캡쳐 완료 후 활용 방안:

1. **문서화**
   - 사용자 매뉴얼에 스크린샷 삽입
   - API 문서에 UI 플로우 추가

2. **발표 자료**
   - 시나리오별 화면 정리
   - 핵심 기능(D2) 강조

3. **테스트 자료**
   - QA 팀에 공유
   - 회귀 테스트 기준 자료

4. **버그 리포트**
   - 실제 화면과 비교
   - 이슈 재현 시 참고

---

## 📞 도움말

- 스크립트 관련: `scripts/testing/README.md` 참고
- 좌표 조정: `xdotool getmouselocation` 사용
- 문제 발생 시: 프로젝트 이슈에 스크린샷과 함께 등록

**즐거운 캡쳐 되세요! 📸**

