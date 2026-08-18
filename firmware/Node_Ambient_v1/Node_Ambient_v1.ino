// 화담 CARE — 공간 노드 펌웨어 (SHT31 + PMS7003 + 오프라인 버퍼링 + 배치 재전송)
//
// Node_SHT31_v2와 동일한 구조 위에 PM2.5 측정을 얹은 것이다.
// 네트워크·버퍼·NTP 처리는 v2와 같으므로 한쪽을 고치면 다른 쪽도 맞춰야 한다.
//
// v2 대비 추가된 것:
//   - PMS7003(PM2.5) UART 측정. 라이브러리 없이 32바이트 프레임 직접 파싱
//   - 팬 듀티 사이클링. 측정 직전에만 깨우고 끝나면 재운다
//   - 다중 샘플 중앙값으로 이상치 제거
//   - Sample 구조체와 전송 페이로드에 pm25 필드 추가
//
// 배선: SHT31    VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21
//       PMS7003  VCC→5V(VIN), GND→GND, TXD→GPIO16, RXD→GPIO17
//       PMS7003의 SET/RESET은 연결하지 않는다. 절전은 UART 명령으로 건다.

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "Adafruit_SHT31.h"
#include <hwadam_secrets.h>   // WIFI_SSID, WIFI_PASS, SERVER_URL, NODE_KEY

// ─── 노드별 설정 (플래시 전 반드시 확인) ──────────────
#define NODE_ID   "ambient-01"          // ambient-01 | ambient-02
// ──────────────────────────────────────────────────────

const uint32_t INTERVAL_MS   = 600000;   // 10분. 검증 중에는 60000(1분)
const uint32_t NTP_RESYNC_MS = 21600000; // 6시간마다 재동기

#define SDA_PIN 21
#define SCL_PIN 22
#define SHT31_ADDR 0x44

#define PMS_RX_PIN 16   // ESP32가 수신 ← PMS7003 TXD
#define PMS_TX_PIN 17   // ESP32가 송신 → PMS7003 RXD

// 팬 예열 시간. 관 안의 공기가 교체되어 값이 안정될 때까지 걸리는 시간이다.
// 브링업 실측에서 약 30초 후 값이 평탄해졌다.
#define PMS_WARMUP_MS  30000
#define PMS_SAMPLES    10       // 중앙값을 낼 프레임 수
#define PMS_COLLECT_MS 15000    // 샘플 수집 타임아웃

// 버퍼: 10분 주기 기준 288건 = 2일치.
// pm25가 붙어 한 건이 16바이트가 되었으나 약 4.6KB로 여전히 여유가 있다.
#define BUF_MAX   288
#define CHUNK     60   // 1회 POST당 최대 건수. JSON 문자열 메모리 여유 확보용

struct Sample {
  time_t ts;
  float  temperature;
  float  humidity;
  float  pm25;         // 측정 실패 시 -1. 전송 시 필드 자체를 생략한다
};

Sample   buf[BUF_MAX];
uint16_t bufCount = 0;
uint32_t lastNtpSync = 0;

Adafruit_SHT31 sht31 = Adafruit_SHT31();
HardwareSerial PmsSerial(2);   // UART0은 시리얼 모니터가 점유하므로 UART2를 쓴다

// ─── 유틸 ─────────────────────────────────────────────

float absoluteHumidity(float t, float rh) {
  float es = 6.112 * exp(17.67 * t / (t + 243.5));   // 포화수증기압 [hPa]
  return 2.1674 * es * rh / (273.15 + t);            // RH는 백분율 그대로
}

bool timeIsSynced() {
  return time(nullptr) > 1700000000;   // 2023-11 이후면 동기화된 것으로 본다
}

String isoOf(time_t t) {
  struct tm tmv;
  gmtime_r(&t, &tmv);
  char b[32];
  strftime(b, sizeof(b), "%Y-%m-%dT%H:%M:%SZ", &tmv);
  return String(b);
}

// ─── PMS7003 ──────────────────────────────────────────

// 명령 프레임: 42 4D <cmd> <data_h> <data_l> <ck_h> <ck_l>
// 체크섬은 앞 5바이트의 합이다.
void pmsCommand(uint8_t cmd, uint8_t dataH, uint8_t dataL) {
  uint8_t f[7] = { 0x42, 0x4D, cmd, dataH, dataL, 0, 0 };
  uint16_t sum = 0;
  for (int i = 0; i < 5; i++) sum += f[i];
  f[5] = sum >> 8;
  f[6] = sum & 0xFF;
  PmsSerial.write(f, 7);
  PmsSerial.flush();
}

void pmsSleep() { pmsCommand(0xE4, 0x00, 0x00); }   // 42 4D E4 00 00 01 73
void pmsWake()  { pmsCommand(0xE4, 0x00, 0x01); }   // 42 4D E4 00 01 01 74

// 32바이트 프레임 하나를 읽어 atm 기준 PM2.5를 돌려준다. 실패 시 -1.
// 헤더(0x42 0x4D)를 만날 때까지 버리면 중간부터 들어와도 자동 정렬된다.
int pmsReadFrame(uint32_t timeoutMs) {
  uint8_t f[32];
  uint8_t idx = 0;
  uint32_t start = millis();

  while (millis() - start < timeoutMs) {
    if (!PmsSerial.available()) { delay(2); continue; }
    uint8_t b = PmsSerial.read();

    if (idx == 0) {
      if (b != 0x42) continue;
    } else if (idx == 1) {
      if (b != 0x4D) { idx = 0; continue; }
    }

    f[idx++] = b;
    if (idx < 32) continue;
    idx = 0;

    uint16_t sum = 0;
    for (int i = 0; i < 30; i++) sum += f[i];
    if (sum != (((uint16_t)f[30] << 8) | f[31])) continue;   // 체크섬 불일치는 버린다

    // f[4..9]는 CF=1(표준입자) 기준, f[10..15]는 atm(대기환경 보정) 기준.
    // 실내외 공기질에는 atm을 쓴다.
    return ((uint16_t)f[12] << 8) | f[13];   // atm PM2.5
  }
  return -1;
}

int cmpInt(const void* a, const void* b) {
  int x = *(const int*)a, y = *(const int*)b;
  return (x > y) - (x < y);
}

// 깨우기 → 예열 → 다중 샘플 → 중앙값 → 재우기. 실패 시 -1.
//
// 팬을 상시 돌리지 않는 이유: PMS7003 팬의 정격 수명이 연속 가동 기준
// 약 8,000시간이라 1년이 못 간다. 10분 주기에서 40초만 돌리면 약 7%로
// 떨어져 수명이 수년 단위로 늘어난다.
float pmsMeasure() {
  pmsWake();

  Serial.print("  PMS 예열");
  uint32_t t0 = millis();
  while (millis() - t0 < PMS_WARMUP_MS) {
    // 예열 중 프레임은 버린다. UART 버퍼가 넘치지 않도록 비워만 준다.
    while (PmsSerial.available()) PmsSerial.read();
    delay(500);
    if ((millis() - t0) % 5000 < 500) Serial.print(".");
  }
  Serial.println();

  int vals[PMS_SAMPLES];
  uint8_t n = 0;
  uint32_t t1 = millis();
  while (n < PMS_SAMPLES && millis() - t1 < PMS_COLLECT_MS) {
    int v = pmsReadFrame(2000);
    if (v >= 0) vals[n++] = v;
  }

  pmsSleep();

  if (n == 0) {
    Serial.println("  PMS 프레임 수신 실패 — pm25 없이 진행");
    return -1;
  }

  // 평균이 아니라 중앙값을 쓴다. 광산란식은 프레임 편차가 커서
  // 이상치 한 건이 평균을 끌고 간다.
  qsort(vals, n, sizeof(int), cmpInt);
  float median = (n % 2) ? (float)vals[n / 2]
                         : (vals[n / 2 - 1] + vals[n / 2]) / 2.0f;

  Serial.printf("  PMS %u건  중앙값=%.1f  (최소 %d 최대 %d)\n",
                n, median, vals[0], vals[n - 1]);
  return median;
}

// ─── 네트워크 ─────────────────────────────────────────

bool connectWiFi(uint16_t tries = 40) {
  if (WiFi.status() == WL_CONNECTED) return true;

  // 이전 연결 시도가 진행 중이면 새 begin()이 거부된다(sta is connecting).
  // 먼저 정리한 뒤 다시 시작해야 재시도가 성립한다.
  WiFi.disconnect(true);
  delay(200);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("  Wi-Fi");
  for (uint16_t i = 0; i < tries; i++) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf(" OK  %s  RSSI=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      return true;
    }
    Serial.print(".");
    delay(500);
  }
  Serial.printf(" 실패 (status=%d)\n", WiFi.status());
  return false;
}

void syncTime() {
  if (WiFi.status() != WL_CONNECTED) return;

  // configTime은 비동기다. 요청만 보내고 즉시 리턴하므로,
  // 시각이 실제로 갱신될 때까지 충분히 기다려야 한다.
  // 셀룰러 핫스팟은 DNS·NTP 왕복이 집 공유기보다 느리다.
  configTime(0, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");

  Serial.print("  NTP");
  for (int i = 0; i < 30 && !timeIsSynced(); i++) {
    Serial.print(".");
    delay(1000);
  }

  if (timeIsSynced()) {
    lastNtpSync = millis();
    Serial.printf(" OK  %s\n", isoOf(time(nullptr)).c_str());
  } else {
    Serial.println(" 실패");
  }
}

// ─── 버퍼 ─────────────────────────────────────────────

void bufPush(time_t ts, float t, float h, float pm) {
  if (bufCount >= BUF_MAX) {
    // 가득 차면 가장 오래된 것을 버린다. 최근 데이터가 더 중요하다.
    memmove(buf, buf + 1, sizeof(Sample) * (BUF_MAX - 1));
    bufCount = BUF_MAX - 1;
    Serial.println("  버퍼 가득참 — 최오래 1건 폐기");
  }
  buf[bufCount++] = { ts, t, h, pm };
}

void bufDropFront(uint16_t n) {
  if (n >= bufCount) { bufCount = 0; return; }
  memmove(buf, buf + n, sizeof(Sample) * (bufCount - n));
  bufCount -= n;
}

// 버퍼 앞쪽 n건을 전송. 성공 시 true.
bool sendChunk(uint16_t n) {
  JsonDocument doc;
  doc["node_id"] = NODE_ID;
  JsonArray arr = doc["readings"].to<JsonArray>();

  for (uint16_t i = 0; i < n; i++) {
    JsonObject r = arr.add<JsonObject>();
    r["ts"]          = isoOf(buf[i].ts);
    r["temperature"] = buf[i].temperature;
    r["humidity"]    = buf[i].humidity;
    // PM 측정에 실패한 건은 필드를 생략한다. 온습도까지 버리지 않는다.
    if (buf[i].pm25 >= 0) r["pm25"] = buf[i].pm25;
  }

  String body;
  serializeJson(doc, body);

  WiFiClientSecure client;
  client.setInsecure();          // 루트 CA 검증 생략. 예선용 임시 조치
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Node-Key", NODE_KEY);
  http.setTimeout(20000);        // TLS 핸드셰이크 + 배치 전송 여유

  int code = http.POST(body);
  String res = (code > 0) ? http.getString() : http.errorToString(code);
  http.end();

  Serial.printf("  POST[%u] %d  %s\n", n, code, res.c_str());

  // 2xx만 성공으로 본다.
  // 4xx는 재전송해도 계속 실패하므로 버려야 하지만, 원인 파악이 우선이라
  // 예선 단계에서는 보관한다. 버퍼가 차면 오래된 것부터 자연히 밀려난다.
  return code >= 200 && code < 300;
}

void flushBuffer() {
  if (bufCount == 0) return;
  if (!connectWiFi()) return;

  // 밀린 데이터가 많으면 한 사이클에서 여러 번 나눠 보낸다.
  for (int guard = 0; guard < 10 && bufCount > 0; guard++) {
    uint16_t n = (bufCount < CHUNK) ? bufCount : CHUNK;
    if (!sendChunk(n)) break;
    bufDropFront(n);
  }
  if (bufCount > 0) Serial.printf("  버퍼 잔여 %u건\n", bufCount);
}

// ─── 메인 ─────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.printf("\n=== HwaDam CARE Node [%s] ambient ===\n", NODE_ID);

  if (!sht31.begin(SHT31_ADDR)) {
    Serial.println("SHT31 초기화 실패. 주소/배선 확인.");
    while (1) delay(1000);
  }
  sht31.heater(false);

  PmsSerial.begin(9600, SERIAL_8N1, PMS_RX_PIN, PMS_TX_PIN);
  delay(100);
  pmsSleep();                    // 부팅 직후 팬을 재워 둔다
  Serial.println("PMS7003 UART2 초기화 — 대기 모드");

  connectWiFi();
  syncTime();
  Serial.println();
}

void loop() {
  uint32_t cycleStart = millis();

  float t = sht31.readTemperature();
  float h = sht31.readHumidity();

  if (isnan(t) || isnan(h)) {
    Serial.println("read failed");
  } else if (!timeIsSynced()) {
    // 시각을 모르면 기록 자체를 하지 않는다.
    // 잘못된 ts가 섞이면 열이력 적산이 망가지고 사후 추적이 어렵다.
    Serial.println("NTP 미동기 — 기록 보류");
    connectWiFi();
    syncTime();
  } else {
    float pm = pmsMeasure();     // 약 40초 소요 (예열 30초 + 수집)
    time_t now = time(nullptr);
    bufPush(now, t, h, pm);
    Serial.printf("%s  %.2fC  %.2f%%  AH=%.2f  PM2.5=%.1f  buf=%u\n",
                  isoOf(now).c_str(), t, h, absoluteHumidity(t, h), pm, bufCount);
    flushBuffer();
  }

  if (millis() - lastNtpSync > NTP_RESYNC_MS) syncTime();

  // v2는 delay(INTERVAL_MS)로 끝냈지만, 여기서는 PMS 예열에만 40초가 들어가
  // 그대로 두면 실제 주기가 10분 40초가 되고 오차가 계속 누적된다.
  // 이번 사이클에 쓴 시간을 빼서 주기를 10분에 고정한다.
  uint32_t elapsed = millis() - cycleStart;
  delay(elapsed < INTERVAL_MS ? INTERVAL_MS - elapsed : 1000);
}
