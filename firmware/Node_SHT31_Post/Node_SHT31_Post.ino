// 화담 CARE — 공간/보관 노드 펌웨어 (SHT31 + Wi-Fi + 서버 전송)
// 배선: VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "Adafruit_SHT31.h"
#include <hwadam_secrets.h>   // WIFI_SSID, WIFI_PASS, SERVER_URL, NODE_KEY

// ─── 설정 ────────────────────────────────
const char* NODE_ID    = "storage-01";

const uint32_t INTERVAL_MS = 600000;   // 10분
// ─────────────────────────────────────────

#define SDA_PIN 21
#define SCL_PIN 22
#define SHT31_ADDR 0x44

Adafruit_SHT31 sht31 = Adafruit_SHT31();

float absoluteHumidity(float t, float rh) {
  float es = 6.112 * exp(17.67 * t / (t + 243.5));
  return 2.1674 * es * rh / (273.15 + t);
}

// NTP 동기화. 서버가 2020년 이전 타임스탬프를 422로 거부하므로 필수.
bool syncTime() {
  configTime(0, 0, "pool.ntp.org", "time.google.com");   // UTC로 고정
  Serial.print("NTP 동기화");
  for (int i = 0; i < 30; i++) {
    time_t now = time(nullptr);
    if (now > 1700000000) {          // 2023-11 이후면 동기화 성공
      Serial.printf(" OK (epoch=%ld)\n", now);
      return true;
    }
    Serial.print(".");
    delay(1000);
  }
  Serial.println(" 실패");
  return false;
}

// ISO8601 UTC 문자열 생성 (예: 2026-08-16T12:34:00Z)
String isoNow() {
  time_t now = time(nullptr);
  struct tm t;
  gmtime_r(&now, &t);
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Wi-Fi 연결");
  for (int i = 0; i < 40; i++) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf(" OK  IP=%s  RSSI=%d dBm\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      return true;
    }
    Serial.print(".");
    delay(500);
  }
  Serial.printf(" 실패 (status=%d)\n", WiFi.status());
  return false;
}

void postReading(float t, float h) {
  if (!connectWiFi()) return;

  // 서버는 readings를 항상 배열로 받는다. 지금은 1건, 추후 버퍼 재전송 시 다건.
  JsonDocument doc;
  doc["node_id"] = NODE_ID;
  JsonArray arr = doc["readings"].to<JsonArray>();
  JsonObject r = arr.add<JsonObject>();
  r["ts"] = isoNow();
  r["temperature"] = t;
  r["humidity"] = h;

  String body;
  serializeJson(doc, body);

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Node-Key", NODE_KEY);
  http.setTimeout(15000);

  int code = http.POST(body);
  Serial.printf("  POST %d  %s\n", code,
                code > 0 ? http.getString().c_str() : http.errorToString(code).c_str());
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.printf("=== HwaDam CARE Node [%s] ===\n", NODE_ID);

  if (!sht31.begin(SHT31_ADDR)) {
    Serial.println("SHT31 초기화 실패");
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
  } else {
    Serial.printf("%s  %.2fC  %.2f%%  AH=%.2f\n",
                  isoNow().c_str(), t, h, absoluteHumidity(t, h));
    postReading(t, h);
  }

  delay(INTERVAL_MS);
}