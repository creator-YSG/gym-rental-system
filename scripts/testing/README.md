# 화면 캡쳐 자동화 스크립트

라즈베리파이 키오스크에서 회원 유형별 시나리오 화면을 자동으로 캡쳐하는 스크립트입니다.

## 📋 시나리오 목록

| 시나리오 | 회원 유형 | 전화번호 | 특징 |
|---------|-----------|----------|------|
| **A** | 이용권 없음 | 01011111111 | 결제 불가 상태 |
| **B** | 구독권만 | 01022222222 | 자동 배정 (모달 없음) |
| **C** | 금액권만 | 01033333333 | 자동 배정 (모달 없음) |
| **D1** | 구독권 + 금액권 | 01044444444 | 구독권으로 전부 커버 |
| **D2** | 구독권 + 금액권 | 01055555555 | **혼합 결제 (핵심!)** |
| **D3** | 구독권 소진 + 금액권 | 01066666666 | 구독권 소진 상태 |

---

## 🚀 사용 방법

### 1단계: 테스트 데이터 생성

```bash
# 로컬 또는 라즈베리파이에서 실행
cd ~/gym-rental-system
python3 scripts/testing/setup_test_data.py
```

이 스크립트는:
- 테스트 회원 6명 생성 (TEST-A ~ TEST-D3)
- 각 회원에 맞는 구독권/금액권 생성
- 결제 비밀번호 설정 (모두 123456)

### 2단계: 키오스크 앱 실행

```bash
# 라즈베리파이에서 키오스크 모드로 앱 실행
~/gym-rental-system/scripts/deployment/start_kiosk.sh
```

또는 이미 실행 중이면 그대로 두세요.

### 3단계: 화면 캡쳐 실행

#### 방법 1: 개별 시나리오 실행

```bash
# 시나리오 A (이용권 없음)
python3 scripts/testing/capture_screens.py --scenario A --phone 01011111111

# 시나리오 B (구독권만)
python3 scripts/testing/capture_screens.py --scenario B --phone 01022222222

# 시나리오 D2 (혼합 결제, 실제 대여 실행)
python3 scripts/testing/capture_screens.py --scenario D2 --phone 01055555555 --execute-rental
```

#### 방법 2: 모든 시나리오 일괄 실행

```bash
# 실제 대여 없이 화면만 캡쳐 (권장)
./scripts/testing/run_all_scenarios.sh

# 실제 대여까지 수행 (금액권 차감됨!)
./scripts/testing/run_all_scenarios.sh --execute-rental
```

---

## 📸 캡쳐 결과

캡쳐된 스크린샷은 `~/screenshots/` 디렉토리에 저장됩니다:

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
│   ├── ...
│   └── 09_complete_screen.png
│
└── D2_both_mixed_20241209_143530/  ← 핵심 시나리오!
    ├── 01_home_initial.png
    ├── ...
    ├── 08_payment_modal.png        ← 구독권 + 금액권 혼합 모달
    ├── 09_numpad_overlay.png       ← 금액 쪼개기 키패드
    └── 12_complete_screen.png
```

---

## ⚙️ 좌표 조정

스크립트의 클릭 좌표는 1280x800 해상도 기준입니다.
라즈베리파이 화면 해상도가 다르면 `capture_screens.py`의 좌표를 수정하세요:

```python
# 예시: 키패드 버튼 위치
keypad_positions = {
    '0': (640, 580),  # (x, y) 좌표
    '1': (540, 420),
    # ...
}
```

좌표 확인 방법:
```bash
# xdotool로 현재 마우스 위치 확인
xdotool getmouselocation
```

---

## 🛠️ 문제 해결

### 1. xdotool 또는 scrot 없음

```bash
sudo apt update
sudo apt install xdotool scrot
```

### 2. 브라우저 윈도우를 찾을 수 없음

스크립트는 "Chromium" 윈도우를 찾습니다. 
다른 브라우저 사용 시 `capture_screens.py`의 `WINDOW_TITLE` 수정:

```python
WINDOW_TITLE = "Firefox"  # 또는 사용 중인 브라우저
```

### 3. 클릭이 정확하지 않음

- 해상도가 다르면 좌표 조정 필요
- `xdotool getmouselocation`으로 실제 버튼 위치 확인

### 4. 데이터베이스 오류

```bash
# DB 초기화 후 다시 시도
cd ~/gym-rental-system
python3 scripts/testing/setup_test_data.py
```

---

## 📝 주의사항

1. **실제 대여 플래그 (`--execute-rental`)**
   - 이 옵션을 사용하면 실제로 금액권이 차감됩니다
   - 테스트 후에는 데이터를 다시 생성해야 할 수 있습니다

2. **자동화 속도**
   - 너무 빠르면 UI 렌더링이 안 될 수 있음
   - 필요시 `wait()` 시간 조정

3. **화면 해상도**
   - 1280x800 기준으로 좌표 설정됨
   - 다른 해상도에서는 좌표 조정 필요

---

## 🎯 다음 단계

캡쳐 완료 후:

1. 스크린샷 확인: `ls -la ~/screenshots/`
2. 필요시 로컬로 복사:
   ```bash
   # 로컬에서 실행
   scp -r pi@192.168.0.27:~/screenshots/ ./
   ```
3. 문서나 프레젠테이션에 활용

---

## 📞 문의

스크립트 관련 문제나 개선 사항은 프로젝트 이슈에 등록해주세요.

