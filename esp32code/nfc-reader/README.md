# NFC 리더 ESP32 (운동복 대여기용)

이 ESP32는 **운동복 토출기 ESP32와 별개**입니다.
라즈베리파이 옆에 USB로 연결하여 NFC 태그를 읽는 전용 장치입니다.

## 하드웨어

- **ESP32 개발 보드** (ESP32 DevKit v1 또는 유사 제품)
- **NFC 리더 모듈**: PN532 (권장) 또는 RC522

## 하드웨어 연결

### PN532 (I2C 방식 권장)

| PN532 | ESP32 |
|-------|-------|
| VCC   | 3.3V  |
| GND   | GND   |
| SDA   | GPIO21 (I2C SDA) |
| SCL   | GPIO22 (I2C SCL) |

### RC522 (SPI 방식)

| RC522 | ESP32 |
|-------|-------|
| VCC   | 3.3V  |
| RST   | GPIO22 |
| GND   | GND   |
| MISO  | GPIO19 |
| MOSI  | GPIO23 |
| SCK   | GPIO18 |
| SDA   | GPIO5  |

## 펌웨어 빌드

### PlatformIO 사용 (권장)

```bash
cd nfc-reader-pn532  # 또는 nfc-reader-rc522
pio run
pio run --target upload
pio device monitor
```

### Arduino IDE 사용

1. Arduino IDE 열기
2. 보드: "ESP32 Dev Module" 선택
3. 포트 선택
4. 라이브러리 설치:
   - PN532: "Adafruit PN532" by Adafruit
   - RC522: "MFRC522" by GithubCommunity
5. 업로드

## 동작 방식

```
1. NFC 카드 감지
2. UID 읽기 (예: 5A41B914524189)
3. 시리얼로 전송: {"nfc_uid":"5A41B914524189"}
4. 라즈베리파이가 수신하여 락카키 대여기 API 호출
```

## 테스트

### 시리얼 모니터에서 확인

```
NFC Reader ESP32 Starting...
PN532 Firmware Version: 0x32
NFC Reader Ready. Waiting for cards...

[카드 태그 시]
{"nfc_uid":"5A41B914524189"}
```

### 라즈베리파이에서 확인

```bash
# 포트 확인
ls -l /dev/ttyUSB* /dev/ttyACM*

# minicom으로 테스트
minicom -b 115200 -D /dev/ttyUSB0

# NFC 카드 태그 시 출력 확인
{"nfc_uid":"5A41B914524189"}
```

## 트러블슈팅

### PN532 not found

- I2C 연결 확인 (SDA, SCL)
- PN532 모드 스위치 확인 (I2C 모드로 설정)
- 전원 확인 (3.3V)

### 라즈베리파이에서 포트 안 보임

```bash
# 권한 설정
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyUSB0

# 재부팅 필요할 수 있음
```

### UID가 잘못 읽힘

- NFC 카드를 리더에 가까이 (1-3cm)
- 여러 카드가 동시에 감지되지 않도록 주의

## 참고 문서

- `/Users/yunseong-geun/Projects/gym-rental-system/docs/LOCKER_INTEGRATION.md`

