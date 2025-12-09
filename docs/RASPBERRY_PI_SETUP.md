# 🖥️ 라즈베리파이 접속 정보

> **프로젝트**: 운동복/수건 대여 시스템  
> **업데이트**: 2025-11-30

---

## 📡 네트워크 정보

### 라즈베리파이 정보
- **IP 주소**: `192.168.0.27`
- **호스트명**: `raspberry-pi` (또는 설정할 이름)
- **사용자명**: `pi`
- **기본 비밀번호**: (설정 필요)

---

## 🔐 SSH 접속 방법

### 기본 접속

```bash
# IP 주소로 직접 접속
ssh pi@192.168.0.27

# 또는 호스트명으로 접속 (설정된 경우)
ssh pi@raspberry-pi
```

### SSH 키 설정 (권장)

비밀번호 없이 자동 로그인:

```bash
# 1. 로컬에서 SSH 키 생성 (이미 있다면 건너뛰기)
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 공개키를 라즈베리파이에 복사
ssh-copy-id pi@192.168.0.27

# 3. 이제 비밀번호 없이 접속 가능
ssh pi@192.168.0.27
```

### SSH Config 설정 (편리한 접속)

`~/.ssh/config` 파일에 추가:

```bash
# SSH config 파일 편집
nano ~/.ssh/config
```

**추가할 내용:**
```
Host gym-rental
    HostName 192.168.0.27
    User pi
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

**이제 간단하게 접속:**
```bash
ssh gym-rental
```

---

## 📂 프로젝트 위치

라즈베리파이에서 프로젝트 설치 위치:

```bash
/home/pi/gym-rental-system/
```

---

## 🔄 파일 전송 (rsync)

로컬에서 라즈베리파이로 파일 동기화:

### 전체 프로젝트 동기화

```bash
# 로컬에서 실행
rsync -av --exclude 'instance/*.db' --exclude '__pycache__' --exclude '*.pyc' \
  /Users/yunseong-geun/Projects/gym-rental-system/ \
  pi@192.168.0.27:~/gym-rental-system/
```

### 특정 파일만 전송

```bash
# 설정 파일만
rsync -av config/ pi@192.168.0.27:~/gym-rental-system/config/

# Python 코드만
rsync -av app/ pi@192.168.0.27:~/gym-rental-system/app/
```

---

## 🚀 라즈베리파이 초기 설정

### 1. SSH 접속 확인

```bash
ssh pi@192.168.0.27
```

### 2. 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Python 환경 설정

```bash
# Python 및 pip 설치 확인
python3 --version
pip3 --version

# 가상환경 생성 (선택사항)
cd ~/gym-rental-system
python3 -m venv venv
source venv/bin/activate
```

### 4. 프로젝트 의존성 설치

```bash
cd ~/gym-rental-system
pip3 install -r requirements.txt
```

### 5. 데이터베이스 초기화

```bash
python3 scripts/setup/init_database.py
```

### 6. 터치스크린 설정

터치스크린 설정은 `docs/TOUCHSCREEN_SETUP.md` 참고

---

## 🛠️ 유용한 명령어

### 시스템 정보 확인

```bash
# 라즈베리파이 모델 확인
cat /proc/device-tree/model

# OS 버전 확인
cat /etc/os-release

# 네트워크 상태
ip addr show

# 디스크 사용량
df -h

# 메모리 사용량
free -h
```

### 프로세스 관리

```bash
# Flask 서버 실행 중인지 확인
ps aux | grep python

# 프로세스 종료
pkill -f "python3 run.py"

# 포트 사용 확인
sudo netstat -tulpn | grep :5000
```

### 로그 확인

```bash
# Flask 로그
tail -f ~/gym-rental-system/logs/flask.log

# 시스템 로그
journalctl -xe
```

---

## 🔧 트러블슈팅

### SSH 접속 안 됨

```bash
# 1. 핑 테스트
ping 192.168.0.27

# 2. SSH 서비스 상태 확인 (라즈베리파이에서)
sudo systemctl status ssh

# 3. SSH 재시작 (라즈베리파이에서)
sudo systemctl restart ssh
```

### 파일 권한 문제

```bash
# 스크립트 실행 권한 부여
chmod +x scripts/deployment/*.sh
```

### Python 모듈 없음

```bash
# 의존성 재설치
pip3 install -r requirements.txt --force-reinstall
```

---

## 📝 빠른 참조

### 자주 쓰는 명령어

```bash
# SSH 접속
ssh pi@192.168.0.27

# 프로젝트로 이동
cd ~/gym-rental-system

# 서버 실행
python3 run.py

# 키오스크 모드
./scripts/deployment/start_kiosk.sh

# 코드 동기화 (로컬에서)
rsync -av /Users/yunseong-geun/Projects/gym-rental-system/ pi@192.168.0.27:~/gym-rental-system/
```

---

## 🔐 보안 설정 (권장)

### 1. 기본 비밀번호 변경

```bash
passwd
```

### 2. SSH 포트 변경 (선택사항)

```bash
sudo nano /etc/ssh/sshd_config
# Port 22를 다른 번호로 변경
sudo systemctl restart ssh
```

### 3. 방화벽 설정

```bash
sudo apt install ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 5000/tcp  # Flask
sudo ufw enable
```

---

**마지막 업데이트**: 2025-11-30  
**라즈베리파이 IP**: 192.168.0.27  
**프로젝트**: 운동복/수건 대여 시스템


