/*
 * Node_PMS7003_BringUp.ino
 *
 * PMS7003 단독 브링업. Wi-Fi도 서버 전송도 없다.
 * 목적은 하나 — "UART로 32바이트 프레임이 실제로 들어오는가"만 확인한다.
 *
 * 통합 전에 이걸 먼저 하는 이유:
 *   SHT31(I2C)은 스캐너로 주소가 잡히면 배선이 맞는지 즉시 알 수 있지만,
 *   UART는 TX/RX가 뒤집혀도 아무 에러가 안 난다. 그냥 조용하다.
 *   전송 코드까지 붙여놓고 디버깅하면 원인 후보가 다섯 배로 늘어난다.
 *
 * 배선 (ESP32 DevKitC WROOM-32D 기준)
 *   PMS7003 VCC  → ESP32 5V (VIN)     ※ 3V3 아님. 팬을 돌려야 한다
 *   PMS7003 GND  → ESP32 GND
 *   PMS7003 TXD  → ESP32 GPIO16       ※ 센서가 말하고 ESP32가 듣는다
 *   PMS7003 RXD  → ESP32 GPIO17
 *   SET / RESET  → 미연결 (내부 풀업으로 정상 동작 모드)
 *
 *   PMS7003은 3.3V 로직으로 신호를 내보내므로 레벨 시프터 없이 직결해도 안전하다.
 *   전원만 5V, 신호는 3.3V다.
 *
 * 주의
 *   - 핀 번호가 아니라 브레이크아웃 보드의 실크스크린 글자(VCC/GND/RX/TX)를 보고 꽂을 것.
 *     PMS7003 커넥터는 제조사·변환 케이블마다 배열이 다르다.
 *   - GPIO16/17은 WROOM 계열에서 자유롭게 쓸 수 있다.
 *     WROVER 모듈은 이 두 핀을 PSRAM이 쓰므로 다른 핀으로 옮겨야 한다.
 *
 * 정상 동작 신호
 *   - 전원 인가 즉시 "위잉" 하는 팬 소리가 난다. 소리가 없으면 5V가 안 들어간 것이다.
 *   - 시리얼 모니터(115200)에 1초에 한 번씩 프레임이 찍힌다.
 *   - 값은 30초 정도 지나야 안정된다. 팬이 관을 채우는 시간이다.
 */

#include <HardwareSerial.h>

// UART2를 쓴다. UART0은 USB 시리얼 모니터가 점유하고 있다.
HardwareSerial PmsSerial(2);

static const int PMS_RX_PIN = 16;   // ESP32가 수신 ← PMS7003 TXD
static const int PMS_TX_PIN = 17;   // ESP32가 송신 → PMS7003 RXD

static const uint8_t  FRAME_LEN   = 32;
static const uint16_t BODY_LEN    = 28;   // 헤더 4바이트를 제외한 길이 필드 기대값

uint8_t  frame[FRAME_LEN];
uint8_t  idx = 0;

unsigned long totalBytes   = 0;
unsigned long goodFrames   = 0;
unsigned long badChecksum  = 0;
unsigned long lastReport   = 0;
unsigned long bootAt       = 0;

static uint16_t be16(uint8_t hi, uint8_t lo) {
  return ((uint16_t)hi << 8) | lo;
}

void setup() {
  Serial.begin(115200);
  delay(300);

  PmsSerial.begin(9600, SERIAL_8N1, PMS_RX_PIN, PMS_TX_PIN);
  bootAt = millis();

  Serial.println();
  Serial.println("=== PMS7003 bring-up ===");
  Serial.println("팬 소리가 나야 정상. 값은 30초 예열 후 안정됩니다.");
  Serial.println("5초마다 수신 통계를 함께 출력합니다.");
  Serial.println();
}

void loop() {
  // ── 바이트 단위 프레임 동기화 ────────────────────────────────
  // 0x42 0x4D 두 바이트가 프레임의 시작이다. 중간부터 들어와도
  // 헤더를 만날 때까지 버리면 자동으로 정렬이 맞는다.
  while (PmsSerial.available()) {
    uint8_t b = PmsSerial.read();
    totalBytes++;

    if (idx == 0) {
      if (b != 0x42) continue;          // 첫 바이트가 아니면 버린다
    } else if (idx == 1) {
      if (b != 0x4D) { idx = 0; continue; }
    }

    frame[idx++] = b;

    if (idx < FRAME_LEN) continue;
    idx = 0;                            // 32바이트 확보. 다음 프레임을 위해 리셋

    // ── 체크섬 검증 ──────────────────────────────────────────
    uint16_t sum = 0;
    for (int i = 0; i < 30; i++) sum += frame[i];
    uint16_t recv = be16(frame[30], frame[31]);

    if (sum != recv) {
      badChecksum++;
      Serial.printf("[BAD] checksum calc=%u recv=%u\n", sum, recv);
      continue;
    }
    goodFrames++;

    uint16_t bodyLen = be16(frame[2], frame[3]);

    // CF=1 : 공장 보정 표준입자 기준값
    uint16_t pm1_cf  = be16(frame[4],  frame[5]);
    uint16_t pm25_cf = be16(frame[6],  frame[7]);
    uint16_t pm10_cf = be16(frame[8],  frame[9]);

    // atm : 대기환경 보정값. 실내외 공기질에는 이쪽을 쓴다.
    uint16_t pm1_atm  = be16(frame[10], frame[11]);
    uint16_t pm25_atm = be16(frame[12], frame[13]);
    uint16_t pm10_atm = be16(frame[14], frame[15]);

    unsigned long upSec = (millis() - bootAt) / 1000;

    Serial.printf(
      "[OK] t=%lus len=%u | atm PM1.0=%u PM2.5=%u PM10=%u | cf PM2.5=%u %s\n",
      upSec, bodyLen,
      pm1_atm, pm25_atm, pm10_atm,
      pm25_cf,
      (upSec < 30 ? "(예열중)" : "")
    );
  }

  // ── 5초마다 수신 통계 ────────────────────────────────────────
  // 아무 프레임도 안 들어올 때 원인을 좁히기 위한 것이다.
  if (millis() - lastReport >= 5000) {
    lastReport = millis();
    Serial.printf("  -- 통계: 수신바이트=%lu 정상프레임=%lu 체크섬오류=%lu\n",
                  totalBytes, goodFrames, badChecksum);

    if (totalBytes == 0) {
      Serial.println("  -- 바이트가 0입니다. 아래를 확인하세요:");
      Serial.println("     1) 팬 소리가 나는가       → 안 나면 5V/GND 문제");
      Serial.println("     2) TXD가 GPIO16에 갔는가  → RX/TX를 바꿔 꽂아볼 것");
      Serial.println("     3) GND가 공통인가         → 별도 전원 쓰면 GND 연결 필수");
    }
  }
}
