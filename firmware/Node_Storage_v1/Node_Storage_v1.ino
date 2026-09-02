// 화담 CARE — 보관 노드 펌웨어 (SHT31 + BME680 + 오프라인 버퍼링 + 배치 재전송)
//
// Node_SHT31_v2와 동일한 구조 위에 BME680 가스 저항 측정을 얹은 것이다.
// 네트워크·버퍼·NTP 처리는 v2·Node_Ambient_v1과 같으므로 한쪽을 고치면
// 나머지도 맞춰야 한다.
//
// v2 대비 추가된 것:
//   - BME680 가스 저항(gas_resistance) 측정. 히터 320℃ · 150ms 고정
//   - 측정 직전 버림 구간 + 다중 샘플 중앙값으로 히터 열상태를 재현 가능하게 고정
//   - 전원 인가 후 예열 구간 동안 gas_resistance를 전송하지 않음
//   - Sample 구조체와 전송 페이로드에 gas_resistance 필드 추가
//
// 배선: SHT31   VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21
//       BME680  VIN→3V3, GND→GND, SCK→GPIO22, SDI→GPIO21
//               (3Vo · SDO · CS는 연결하지 않는다. 핀 이름이 SPI 기준이라
//                SCK가 SCL, SDI가 SDA다. 주소는 0x76 또는 0x77)
//       SHT31 0x44와 주소가 겹치지 않으므로 같은 버스를 쓴다.
//
// ─────────────────────────────────────────────────────────────
// 온습도는 SHT31, 가스는 BME680으로 나눠 쓴다
//
// BME680은 가스를 재려고 내부 히터를 320℃까지 올린다. 그 열이 같은 패키지
// 안의 온습도 센서로 새어 들어간다. 브링업 실측(2026-08-27)에서 SHT31 대비
// 온도 +0.54℃, 습도 -8.2%RH였다. 열이력 적산(erl.py)은 온도를 Q10 지수에
// 넣으므로 이 차이를 그대로 쓰면 노화 속도가 약 +3.8% 어긋난다.
//
// 따라서 이 펌웨어는 BME680의 온습도·기압을 읽되 서버로 보내지 않는다.
// temperature·humidity는 SHT31 값만 올라간다.
//
// ─────────────────────────────────────────────────────────────
// 가스 저항을 재는 방식 — 측정 주기를 고정해야 하는 이유
//
// MOX 센서의 저항 절대값은 히터가 얼마나 자주 켜졌는지에 따라 달라진다.
// 브링업에서 측정 주기를 5초 → 1.5초로 바꾸자 79 kΩ이 110 kΩ으로 올랐다.
// 히터가 더 자주 켜져 표면이 더 뜨겁고 건조해지기 때문으로 보인다.
//
// 10분에 한 번만 재면 히터는 매번 식은 상태에서 150ms만 켜지므로, 그때의
// 저항은 재현성이 떨어진다. 그래서 매 사이클마다
//   ① 1.5초 간격으로 GAS_DISCARD회 읽어 버리고 (히터 열상태를 일정하게 만든다)
//   ② 이어서 GAS_SAMPLES회 읽어 중앙값을 취한다
// 이렇게 하면 기록되는 시점의 히터 상태가 항상 같아져 사이클 간 비교가 선다.
//
// GAS_STEP_MS·GAS_DISCARD·GAS_SAMPLES·HEATER_*는 기준선 학습 내내 바꾸면
// 안 된다. 중간에 바꾸면 그동안 모은 기준선이 전부 무효가 된다.
//
// ─────────────────────────────────────────────────────────────
// 예열 구간 (GAS_WARMUP_MS)
//
// 전원을 켜자마자 제값이 나오지 않는다. 브링업 실측에서 25.8 kΩ → 80 kΩ으로
// 3.1배 오르며 약 30분에 안정됐다. 이 구간을 기준선에 섞으면 "시간이
// 지날수록 공기가 나빠지는" 가짜 추세가 생긴다.
//
// 그래서 전원 인가 후 30분 동안은 gas_resistance 필드를 아예 빼고 보낸다.
// 온습도는 그동안에도 정상 수집된다(서버는 필드 생략을 허용한다).
// 키오스크 대시보드에 VOC가 뜨는 것도 그만큼 늦으므로, 시연 전에는 최소
// 30분 전에 전원을 넣어 둔다.
//
// ─────────────────────────────────────────────────────────────
// 이 값으로 할 수 있는 것과 없는 것
//
// BME680이 주는 것은 가열된 금속산화물의 저항 하나뿐이다. 어떤 물질인지
// 구분하지 못한다. 향수를 뿌려도, 화장품이 산패해도, 알코올 솜을 열어도
// 똑같이 저항이 떨어진다. 그래서 이 값은 "변질 판정"이 아니라 "언제
// 확인할지 알려주는 트리거"로만 쓰고, 급등하면 키오스크가 사용자에게
// 되묻는 구조(Human-in-the-Loop)를 택한다.

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <math.h>
#include "Adafruit_SHT31.h"
#include "Adafruit_BME680.h"
#include <hwadam_secrets.h>   // WIFI_SSID, WIFI_PASS, SERVER_URL, NODE_KEY

// ─── 노드별 설정 (플래시 전 반드시 확인) ──────────────
#define NODE_ID   "storage-01"
// ──────────────────────────────────────────────────────

const uint32_t INTERVAL_MS   = 600000;   // 10분. 검증 중에는 60000(1분)
const uint32_t NTP_RESYNC_MS = 21600000; // 6시간마다 재동기

#define SDA_PIN 21
#define SCL_PIN 22
#define SHT31_ADDR 0x44

// 히터 설정. 온도를 바꾸면 저항의 절대값이 통째로 달라진다.
const uint16_t HEATER_TEMP_C = 320;
const uint16_t HEATER_MS     = 150;

// 가스 측정. 브링업 반응 시험과 같은 1.5초 주기를 쓴다.
#define GAS_STEP_MS   1500
#define GAS_DISCARD   6      // 버리는 횟수 (히터 열상태 정렬용)
#define GAS_SAMPLES   5      // 중앙값을 낼 샘플 수
// → 한 사이클당 약 (6+5) × 1.5초 + 측정시간 ≈ 19초

// 예열 구간. 이 시간 전에는 gas_resistance를 전송하지 않는다.
const uint32_t GAS_WARMUP_MS = 1800000;  // 30분

// 버퍼: 10분 주기 기준 288건 = 2일치.
// gas_resistance가 붙어 한 건이 16바이트가 되었으나 약 4.6KB로 여유가 있다.
#define BUF_MAX   288
#define CHUNK     60   // 1회 POST당 최대 건수. JSON 문자열 메모리 여유 확보용

struct Sample {
  time_t ts;
  float  temperature;
  float  humidity;
  float  gasResistance;   // 측정 실패·예열 중이면 -1. 전송 시 필드 자체를 생략한다
};

Sample   buf[BUF_MAX];
uint16_t bufCount = 0;
uint32_t lastNtpSync = 0;
uint32_t bootMs = 0;

Adafruit_SHT31  sht31 = Adafruit_SHT31();
Adafruit_BME680 bme;
uint8_t bmeAddr = 0;

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

int cmpFloat(const void* a, const void* b) {
  float x = *(const float*)a, y = *(const float*)b;
  return (x > y) - (x < y);
}

// ─── BME680 ───────────────────────────────────────────

// 버림 구간 → 다중 샘플 → 중앙값. 실패하거나 예열 중이면 -1.
float gasMeasure() {
  if (millis() - bootMs < GAS_WARMUP_MS) {
    uint32_t left = (GAS_WARMUP_MS - (millis() - bootMs)) / 60000;
    Serial.printf("  가스 예열 중 — 약 %lu분 남음. gas_resistance 전송 보류\n", left);
    return -1;
  }

  // 버림 구간. 값을 쓰지 않고 히터 열상태만 맞춘다.
  for (uint8_t i = 0; i < GAS_DISCARD; i++) {
    bme.performReading();
    delay(GAS_STEP_MS);
  }

  float vals[GAS_SAMPLES];
  uint8_t n = 0;
  for (uint8_t i = 0; i < GAS_SAMPLES; i++) {
    if (bme.performReading() && bme.gas_resistance > 0) {
      vals[n++] = (float)bme.gas_resistance;
    }
    delay(GAS_STEP_MS);
  }

  if (n == 0) {
    Serial.println("  BME680 읽기 실패 — gas_resistance 없이 진행");
    return -1;
  }

  // 평균이 아니라 중앙값을 쓴다. 이상치 한 건이 평균을 끌고 간다.
  qsort(vals, n, sizeof(float), cmpFloat);
  float median = (n % 2) ? vals[n / 2]
                         : (vals[n / 2 - 1] + vals[n / 2]) / 2.0f;

  Serial.printf("  BME680 %u건  중앙값=%.1f kΩ  (최소 %.1f 최대 %.1f)  자체발열 %+.2f℃\n",
                n, median / 1000.0, vals[0] / 1000.0, vals[n - 1] / 1000.0,
                bme.temperature - sht31.readTemperature());
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

void bufPush(time_t ts, float t, float h, float g) {
  if (bufCount >= BUF_MAX) {
    // 가득 차면 가장 오래된 것을 버린다. 최근 데이터가 더 중요하다.
    memmove(buf, buf + 1, sizeof(Sample) * (BUF_MAX - 1));
    bufCount = BUF_MAX - 1;
    Serial.println("  버퍼 가득참 — 최오래 1건 폐기");
  }
  buf[bufCount++] = { ts, t, h, g };
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
    // 가스 측정에 실패했거나 예열 중이던 건은 필드를 생략한다.
    // 온습도까지 버리지 않는다.
    if (buf[i].gasResistance >= 0) r["gas_resistance"] = buf[i].gasResistance;
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
  bootMs = millis();

  Serial.printf("\n=== HwaDam CARE Node [%s] storage ===\n", NODE_ID);

  if (!sht31.begin(SHT31_ADDR)) {
    Serial.println("SHT31 초기화 실패. 주소/배선 확인.");
    while (1) delay(1000);
  }
  sht31.heater(false);   // 내장 히터는 결로 제거용. 켜면 측정이 왜곡된다
  Serial.println("SHT31 OK (0x44)");

  // 주소는 보드마다 다르다. SDO가 GND면 0x76, 3V3이면 0x77이다.
  if (bme.begin(0x76))      bmeAddr = 0x76;
  else if (bme.begin(0x77)) bmeAddr = 0x77;

  if (bmeAddr) {
    // 온습도·기압은 어차피 SHT31을 쓰므로 과하게 잡지 않고,
    // 가스 측정의 안정성에 무게를 둔다.
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
    bme.setGasHeater(HEATER_TEMP_C, HEATER_MS);
    Serial.printf("BME680 OK (0x%02X)  히터 %u℃ · %ums\n",
                  bmeAddr, HEATER_TEMP_C, HEATER_MS);
    Serial.printf("가스 예열 %lu분 — 그동안 온습도만 전송한다\n",
                  GAS_WARMUP_MS / 60000);
  } else {
    // 가스가 없어도 열이력·습도는 살아 있어야 한다. 멈추지 않는다.
    Serial.println("BME680을 찾지 못했습니다 — 온습도만 수집합니다.");
    Serial.println("  · I2C_Scanner로 0x76/0x77이 잡히는지 확인");
    Serial.println("  · 핀 이름이 SPI 기준이다. SCK가 SCL, SDI가 SDA다");
  }

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
    float g = bmeAddr ? gasMeasure() : -1;   // 약 19초 소요
    time_t now = time(nullptr);
    bufPush(now, t, h, g);
    Serial.printf("%s  %.2fC  %.2f%%  AH=%.2f  R=%.1fk  buf=%u\n",
                  isoOf(now).c_str(), t, h, absoluteHumidity(t, h),
                  g >= 0 ? g / 1000.0 : -1.0, bufCount);
    flushBuffer();
  }

  if (millis() - lastNtpSync > NTP_RESYNC_MS) syncTime();

  // 가스 측정에만 약 19초가 들어간다. 그대로 두면 실제 주기가 10분 19초가
  // 되고 오차가 계속 누적된다. 이번 사이클에 쓴 시간을 빼서 10분에 고정한다.
  uint32_t elapsed = millis() - cycleStart;
  delay(elapsed < INTERVAL_MS ? INTERVAL_MS - elapsed : 1000);
}
