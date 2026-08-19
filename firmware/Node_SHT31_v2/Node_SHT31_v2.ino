// 화담 CARE — 노드 펌웨어 v2 (SHT31 + 오프라인 버퍼링 + 배치 재전송)
//
// v1 대비 변경점:
//   - Wi-Fi/서버 장애 시 측정값을 RAM 버퍼에 보관했다가 복구 시 일괄 전송
//   - NTP 미동기 상태에서는 기록하지 않음 (잘못된 타임스탬프 유입 차단)
//   - Wi-Fi 자동 재연결, 주기적 NTP 재동기
//
// 서버는 (node_id, ts) 유니크 인덱스 기반 upsert-ignore이므로,
// 같은 구간을 중복 전송해도 안전하다. 그래서 전송 실패 시 버퍼를 비우지 않는다.
//
// 배선: SHT31  VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "Adafruit_SHT31.h"
#include <hwadam_secrets.h>   // WIFI_SSID, WIFI_PASS, SERVER_URL, NODE_KEY

// ─── 노드별 설정 (플래시 전 반드시 확인) ──────────────
#define NODE_ID   "storage-01"          // storage-01 | ambient-01 | ambient-02
// ──────────────────────────────────────────────────────

const uint32_t INTERVAL_MS   = 600000;  // 10분. 검증 중에는 60000(1분)
const uint32_t NTP_RESYNC_MS = 21600000; // 6시간마다 재동기

#define SDA_PIN 21
#define SCL_PIN 22
#define SHT31_ADDR 0x44

// 버퍼: 10분 주기 기준 288건 = 2일치.
// 한 건이 12바이트라 약 3.5KB로 ESP32 힙에 충분히 들어간다.
#define BUF_MAX   288
#define CHUNK     60   // 1회 POST당 최대 건수. JSON 문자열 메모리 여유 확보용

struct Sample {
  time_t ts;
  float  temperature;
  float  humidity;
};

Sample   buf[BUF_MAX];
uint16_t bufCount = 0;
uint32_t lastNtpSync = 0;

Adafruit_SHT31 sht31 = Adafruit_SHT31();

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

void bufPush(time_t ts, float t, float h) {
  if (bufCount >= BUF_MAX) {
    // 가득 차면 가장 오래된 것을 버린다. 최근 데이터가 더 중요하다.
    memmove(buf, buf + 1, sizeof(Sample) * (BUF_MAX - 1));
    bufCount = BUF_MAX - 1;
    Serial.println("  버퍼 가득참 — 최오래 1건 폐기");
  }
  buf[bufCount++] = { ts, t, h };
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

  Serial.printf("\n=== HwaDam CARE Node [%s] v2 ===\n", NODE_ID);

  if (!sht31.begin(SHT31_ADDR)) {
    Serial.println("SHT31 초기화 실패. 주소/배선 확인.");
    while (1) delay(1000);
  }
  sht31.heater(false);

  connectWiFi();
  syncTime();
  Serial.println();
}

void loop() {
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
    time_t now = time(nullptr);
    bufPush(now, t, h);
    Serial.printf("%s  %.2fC  %.2f%%  AH=%.2f  buf=%u\n",
                  isoOf(now).c_str(), t, h, absoluteHumidity(t, h), bufCount);
    flushBuffer();
  }

  if (millis() - lastNtpSync > NTP_RESYNC_MS) syncTime();

  delay(INTERVAL_MS);
}
