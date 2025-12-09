# 🏃 운동복/수건 대여 시스템

> 라즈베리파이 기반 헬스장 운동복/수건 자동 대여 시스템

## 📋 시스템 개요

바코드 스캔을 통한 운동복과 수건의 자동 대여/반납 시스템입니다.

### 주요 기능

- 🎫 **바코드 스캔**: 회원 바코드로 간편 인증
- 👕 **운동복 대여**: 사이즈별 재고 관리
- 🧺 **수건 대여**: 자동 재고 차감
- 📊 **재고 관리**: 실시간 재고 현황 확인
- 🔄 **반납 처리**: 간편한 반납 및 재고 복원
- 📱 **터치스크린 UI**: 직관적인 키오스크 인터페이스

## 🏗️ 시스템 구성

- **중앙 제어**: 라즈베리파이 + SQLite
- **인터페이스**: Flask 웹 기반 터치스크린
- **하드웨어**: 바코드 스캐너

## 🚀 빠른 시작

### 설치

```bash
# 의존성 설치
pip3 install -r requirements.txt

# 데이터베이스 초기화
python3 scripts/setup/init_database.py
```

### 실행

```bash
# 개발 모드
python3 run.py

# 키오스크 모드
./scripts/deployment/start_kiosk.sh
```

## 📁 프로젝트 구조

```
gym-rental-system/
├── app/                    # Flask 애플리케이션
│   ├── models/            # 데이터 모델 (Member, Rental, Item)
│   ├── services/          # 비즈니스 로직
│   ├── templates/         # HTML 템플릿
│   └── static/            # CSS, JS, 이미지
├── database/              # 데이터베이스 관리
├── config/                # 설정 파일
├── scripts/               # 유틸리티 스크립트
└── docs/                  # 문서
```

## 🎯 사용 흐름

1. **회원 바코드 스캔** → 회원 인증
2. **물품 선택** → 운동복(사이즈) 또는 수건 선택
3. **대여 완료** → 재고 차감 및 대여 기록
4. **반납** → 회원 바코드 스캔 후 반납 처리

## 📚 문서

- [시스템 가이드](docs/SYSTEM_GUIDE.md)
- [데이터베이스 설계](docs/DATABASE_DESIGN.md)
- [개발 가이드](docs/DEVELOPMENT.md)

## 🔧 개발 환경

- Python 3.7+
- Flask 2.3+
- SQLite3
- Raspberry Pi OS

---

**프로젝트 시작일**: 2025-11-30


