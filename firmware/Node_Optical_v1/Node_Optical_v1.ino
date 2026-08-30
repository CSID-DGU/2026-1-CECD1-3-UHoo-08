// 화담 CARE — 측정 노드 펌웨어 (AS7341 + 측정 세션)
//
// 배선: AS7341  VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21  (SHT31 0x44와 같은 버스)
//
// ─────────────────────────────────────────────────────────────
// 환경 노드(Node_SHT31_v2·Node_Ambient_v1)와 근본적으로 다른 점
//
// 환경 노드는 시키지 않아도 10분마다 알아서 올린다. 측정할 대상이 늘
// 거기 있기 때문이다. 이 노드는 반대다. 사람이 시료를 올려놓아야 잴 것이
// 생기고, 그 결과를 기다리는 화면이 따로 있다.
//
// 그래서 이 노드는 버퍼링하지 않는다. 환경 노드가 Wi-Fi 장애 때 값을
// 쌓아 두는 것은 그 시각의 온도가 나중에 올라가도 여전히 의미가 있기
// 때문이다. 반면 측정값은 "지금 이 세션의 결과"라서, 세션이 닫힌 뒤에
// 도착하면 쓸 데가 없다. 전송에 실패하면 버리고 다시 재게 한다.
//
// ─────────────────────────────────────────────────────────────
// 이 노드에는 화면도 버튼도 없다. 안내와 트리거를 모두 키오스크가 한다.
//
// 노드는 측정부에 무엇이 올라와 있는지 알 수 없다. 그것을 아는 사람은
// 방금 손으로 올려놓은 사용자뿐이다. 사용자는 어차피 키오스크 화면을
// 보고 있으므로, 거기서 누른 것을 측정 신호로 삼는다. 노드에 버튼을
// 달면 시선은 화면에, 손은 노드에 두어야 해서 둘로 갈라진다.
//
//   키오스크  "측정하기"                → 서버에 세션 생성
//   노드      GET .../session           → 2초 간격 폴링 (step은 아직 비어 있음)
//   키오스크  "백색 표준판을 올린 뒤 측정을 눌러 주세요" → 사용자가 누름
//   노드      폴링에 step=white 도착    → 즉시 측정 → POST step=white
//   키오스크  "제품을 올린 뒤 측정을 눌러 주세요"        → 사용자가 누름
//   노드      폴링에 step=sample 도착   → 즉시 측정 → POST step=sample
//   키오스크  GET .../sessions/{id}     → 변화율 표시
//
// step이 비어 있는 동안에는 아무것도 하지 않는다. 그 상태에서 재면 아직
// 아무것도 올려놓지 않은 허공을 재게 되고, 그 값이 기준값으로 굳는다.
//
// 시리얼 출력은 개발용이다. 실제 사용자는 키오스크 화면만 본다.
//
// ─────────────────────────────────────────────────────────────
// 측정 한 번의 내부 순서 (백색·시료 모두 동일)
//
//   1) 백색 단계에서만: 자동 게인. 백색 표준판이 이 장면에서 가장 밝으므로
//      여기서 포화하지 않게 잡아 두면 시료에서는 포화하지 않는다.
//      시료 단계에서는 게인을 그대로 둔다. 게인이 다르면 두 값의 축척이
//      달라져, 시료/백색 나눗셈이 반사율이 아니라 게인 비를 섞은 값이 된다.
//   2) 암전류 측정 (LED 끔). 센서 누설과 새어 들어온 외부광이 섞여 있다.
//      매 측정 직전에 다시 잰다. 방 조명은 시간대와 사람 위치에 따라 바뀌고,
//      한 번 재둔 값을 계속 쓰면 그 변화가 그대로 시료의 색으로 둔갑한다.
//   3) LED 켜고 측정 → 암전류를 뺀다.
//   4) 포화 검사. 천장(65535)에 닿았으면 값이 잘려 나가 비교에 쓸 수 없다.
//      그 사실을 그대로 서버에 알린다. 서버가 세션을 실패로 닫는다.
//
// 오차 수준은 AS7341_BringUp의 m(재장착 반복성)으로 먼저 재 두어야 한다.
// 그 CV보다 작은 변화는 여기서 무엇을 해도 구분되지 않는다.
// ─────────────────────────────────────────────────────────────

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "Adafruit_AS7341.h"
#include <hwadam_secrets.h>   // WIFI_SSID, WIFI_PASS, SERVER_BASE, NODE_KEY

// ─── 노드별 설정 (플래시 전 반드시 확인) ──────────────
#define NODE_ID   "measure-01"
#define FW_TAG    "optical-v1"
// ──────────────────────────────────────────────────────

#define SDA_PIN 21
#define SCL_PIN 22

// 폴링 간격. 사용자가 키오스크에서 누른 뒤 실제로 재기까지의 지연이 이 값이다.
// 서버 MEASURE_POLL_SEC와 맞춘다.
const uint32_t POLL_MS        = 2000;
const uint32_t NTP_RESYNC_MS  = 21600000;  // 6시간
const uint16_t LED_WARMUP_MS  = 200;       // LED가 밝기를 잡는 데 걸리는 시간
const uint8_t  DARK_SAMPLES   = 3;         // 암전류 평균 횟수
const uint8_t  POST_RETRY     = 3;

// 적분 설정. AS7341_BringUp과 같은 값을 쓴다. 여기서 바꾸면 브링업에서
// 잰 CV·판별한계가 더 이상 이 노드의 숫자가 아니게 된다.
const uint8_t  ATIME_VAL = 100;
const uint16_t ASTEP_VAL = 999;

// 포화 경고 기준. 천장에 가까우면 값이 더 이상 빛에 비례하지 않는다.
const float SAT_WARN_RATIO = 0.90f;
// 자동 게인 목표 상한. 이보다 낮게 떨어질 때까지 게인을 내린다.
const float GAIN_TARGET_RATIO = 0.70f;

// readAllChannels가 채우는 12칸 버퍼에서 우리가 쓰는 자리.
// CLEAR·NIR이 두 번 들어가는데, F5~F8과 같은 적분 사이클에서 나온
// 뒤쪽([10],[11])을 쓴다. 앞쪽을 쓰면 정규화 기준이 채널마다 어긋난다.
const uint8_t CH_IDX[8]    = {0, 1, 2, 3, 6, 7, 8, 9};
const char*   CH_NAME[8]   = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"};
const uint8_t IDX_CLEAR = 10;
const uint8_t IDX_NIR   = 11;

Adafruit_AS7341 as7341;

// ─── 상태 ─────────────────────────────────────────────

enum Step { STEP_NONE, STEP_WHITE, STEP_SAMPLE };

String   sessionId   = "";
// 서버가 "지금 재라"고 한 단계. 사용자가 키오스크에서 누르기 전에는 NONE이다.
Step     armedStep   = STEP_NONE;
uint32_t lastPoll    = 0;
uint32_t lastNtpSync = 0;

as7341_gain_t curGain  = AS7341_GAIN_64X;
uint16_t      curLedMa = 10;

const char* gainName(as7341_gain_t g) {
  switch (g) {
    case AS7341_GAIN_0_5X: return "0.5x";
    case AS7341_GAIN_1X:   return "1x";
    case AS7341_GAIN_2X:   return "2x";
    case AS7341_GAIN_4X:   return "4x";
    case AS7341_GAIN_8X:   return "8x";
    case AS7341_GAIN_16X:  return "16x";
    case AS7341_GAIN_32X:  return "32x";
    case AS7341_GAIN_64X:  return "64x";
    case AS7341_GAIN_128X: return "128x";
    case AS7341_GAIN_256X: return "256x";
    case AS7341_GAIN_512X: return "512x";
  }
  return "?";
}

uint32_t fullScale() {
  uint32_t theoretical = (uint32_t)(ATIME_VAL + 1) * (uint32_t)(ASTEP_VAL + 1);
  return theoretical > 65535 ? 65535 : theoretical;   // 레지스터가 16비트다
}

// ─── 시각 ─────────────────────────────────────────────

bool timeIsSynced() {
  return time(nullptr) > 1700000000;   // 2023-11 이후면 동기화된 것으로 본다
}

String isoNow() {
  time_t t = time(nullptr);
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

  // configTime은 비동기다. 요청만 보내고 즉시 리턴하므로 기다려야 한다.
  configTime(0, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");

  Serial.print("  NTP");
  for (int i = 0; i < 30 && !timeIsSynced(); i++) {
    Serial.print(".");
    delay(1000);
  }

  if (timeIsSynced()) {
    lastNtpSync = millis();
    Serial.printf(" OK  %s\n", isoNow().c_str());
  } else {
    Serial.println(" 실패");
  }
}

// GET·POST 공용. 응답 본문을 돌려주고 code에 상태 코드를 넣는다.
//
// SERVER_BASE가 http면 평문, https면 TLS로 붙는다. 로컬 FastAPI(http)와
// 배포 서버(https)를 같은 펌웨어로 오갈 수 있어야 개발이 돌아간다.
String httpJson(const char* method, const String& url,
                const String& body, int* code) {
  if (!connectWiFi()) { *code = -1; return "wifi down"; }

  WiFiClientSecure tls;
  WiFiClient plain;
  tls.setInsecure();          // 루트 CA 검증 생략. 예선용 임시 조치

  HTTPClient http;
  bool secure = url.startsWith("https");
  bool ok = secure ? http.begin(tls, url) : http.begin(plain, url);
  if (!ok) { *code = -2; return "begin failed"; }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Node-Key", NODE_KEY);
  http.setTimeout(15000);

  int c = (strcmp(method, "GET") == 0) ? http.GET() : http.POST(body);
  String res = (c > 0) ? http.getString() : http.errorToString(c);
  http.end();

  *code = c;
  return res;
}

// ─── 측정 ─────────────────────────────────────────────

bool readChannels(uint16_t* buf, bool ledOn) {
  if (ledOn) {
    as7341.setLEDCurrent(curLedMa);
    as7341.enableLED(true);
    delay(LED_WARMUP_MS);
  }
  bool ok = as7341.readAllChannels(buf);
  // 측정이 끝나면 바로 끈다. 열이 쌓이면 그것 자체가 시료를 변화시킨다.
  if (ledOn) as7341.enableLED(false);
  return ok;
}

// 하나라도 천장에 닿았는지. 닿았으면 그 측정은 통째로 버려야 한다.
bool isSaturated(const uint16_t* buf) {
  uint32_t warn = (uint32_t)(fullScale() * SAT_WARN_RATIO);
  for (int i = 0; i < 8; i++) if (buf[CH_IDX[i]] >= warn) return true;
  return buf[IDX_CLEAR] >= warn;
}

// 백색 표준판에 맞춰 게인을 잡는다. 이 장면에서 가장 밝은 것이 표준판이므로
// 여기서 포화를 피하면 시료에서는 포화하지 않는다.
void autoGain() {
  const as7341_gain_t ladder[] = {
    AS7341_GAIN_0_5X, AS7341_GAIN_1X, AS7341_GAIN_2X, AS7341_GAIN_4X,
    AS7341_GAIN_8X, AS7341_GAIN_16X, AS7341_GAIN_32X, AS7341_GAIN_64X,
    AS7341_GAIN_128X, AS7341_GAIN_256X, AS7341_GAIN_512X
  };
  const int N = sizeof(ladder) / sizeof(ladder[0]);
  uint32_t fs = fullScale();
  uint16_t buf[12];

  for (int gi = N - 1; gi >= 0; gi--) {
    curGain = ladder[gi];
    as7341.setGain(curGain);
    if (!readChannels(buf, true)) return;

    uint16_t peak = buf[IDX_CLEAR];
    for (int i = 0; i < 8; i++) if (buf[CH_IDX[i]] > peak) peak = buf[CH_IDX[i]];

    if ((float)peak / fs <= GAIN_TARGET_RATIO) {
      Serial.printf("  게인 %s (최대 %u / %u)\n", gainName(curGain), peak, fs);
      return;
    }
  }
  Serial.println("  ! 최저 게인에서도 포화합니다. LED 전류를 낮추거나 거리를 늘리세요.");
}

// 암전류. LED를 끈 상태의 출력이며, 매 측정 직전에 다시 잰다.
void measureDark(float* darkCh, float* darkClear, float* darkNir) {
  double sum[8] = {0}, sc = 0, sn = 0;
  uint16_t buf[12];
  uint8_t n = 0;

  for (uint8_t k = 0; k < DARK_SAMPLES; k++) {
    if (!readChannels(buf, false)) continue;
    for (int i = 0; i < 8; i++) sum[i] += buf[CH_IDX[i]];
    sc += buf[IDX_CLEAR];
    sn += buf[IDX_NIR];
    n++;
  }

  if (n == 0) {
    for (int i = 0; i < 8; i++) darkCh[i] = 0;
    *darkClear = *darkNir = 0;
    return;
  }
  for (int i = 0; i < 8; i++) darkCh[i] = sum[i] / n;
  *darkClear = sc / n;
  *darkNir   = sn / n;
}

// ─── 세션 ─────────────────────────────────────────────

// 폴링은 2초마다 같은 답을 돌려준다. 상태가 실제로 바뀔 때만 안내를 찍는다.
void applyPoll(const char* id, const char* stepName) {
  Step want = STEP_NONE;
  if (stepName) {
    if (strcmp(stepName, "white") == 0)       want = STEP_WHITE;
    else if (strcmp(stepName, "sample") == 0) want = STEP_SAMPLE;
  }

  String newId = id ? String(id) : String("");
  bool changed = (sessionId != newId) || (armedStep != want);
  sessionId = newId;
  armedStep = want;
  if (!changed) return;

  if (newId.length() == 0)      Serial.println("[세션] 대기 중.");
  else if (want == STEP_NONE)   Serial.println("\n[세션] 열림. 키오스크에서 측정을 누르면 잽니다.");
  else if (want == STEP_WHITE)  Serial.println("[세션] 백색 표준판 측정 지시를 받았습니다.");
  else                          Serial.println("[세션] 시료 측정 지시를 받았습니다.");
}

// 서버가 세션의 주인이다. 노드는 자기 상태를 서버에 맞추기만 한다.
// 그래야 키오스크에서 취소했거나 시한이 지난 세션을 계속 붙들고 있지 않는다.
void pollSession() {
  lastPoll = millis();

  int code;
  String url = String(SERVER_BASE) + "/api/iot/nodes/" + NODE_ID + "/session";
  String res = httpJson("GET", url, "", &code);

  if (code != 200) {
    Serial.printf("  폴링 실패 %d %s\n", code, res.c_str());
    return;
  }

  JsonDocument doc;
  if (deserializeJson(doc, res)) {
    Serial.println("  폴링 응답 파싱 실패");
    return;
  }

  applyPoll(doc["session_id"], doc["step"]);
}

// 한 단계를 재서 올린다.
void captureAndPost() {
  const bool isWhite = (armedStep == STEP_WHITE);
  const char* stepName = isWhite ? "white" : "sample";

  if (!timeIsSynced()) {
    // 시각을 모르면 보내지 않는다. 서버가 NTP 미동기 시각을 거부하므로
    // 보내봐야 422로 돌아오고, 사용자는 이유를 알 수 없다.
    Serial.println("  NTP 미동기 — 시각부터 맞춥니다");
    syncTime();
    if (!timeIsSynced()) return;
  }

  Serial.printf("\n[측정] %s\n", stepName);

  // 게인은 백색에서 한 번만 잡고 시료에서는 그대로 쓴다.
  if (isWhite) autoGain();

  float darkCh[8], darkClear, darkNir;
  measureDark(darkCh, &darkClear, &darkNir);

  uint16_t buf[12];
  if (!readChannels(buf, true)) {
    Serial.println("  센서 읽기 실패 — 키오스크에서 다시 눌러 주세요");
    return;
  }

  bool saturated = isSaturated(buf);

  JsonDocument doc;
  doc["node_id"]      = NODE_ID;
  doc["step"]         = stepName;
  doc["ts"]           = isoNow();
  doc["saturated"]    = saturated;
  doc["gain"]         = gainName(curGain);
  doc["led_ma"]       = curLedMa;
  doc["dark_applied"] = true;
  doc["fw"]           = FW_TAG;

  JsonObject ch = doc["channels"].to<JsonObject>();
  for (int i = 0; i < 8; i++) {
    // 암전류를 뺀 값을 보낸다. 음수는 0으로 자른다. 보정 후 음수는
    // 신호가 암전류보다 작다는 뜻이라 물리적으로 의미가 없고,
    // 그대로 두면 반사율이 음수가 되어 변화율이 엉뚱하게 커진다.
    float v = buf[CH_IDX[i]] - darkCh[i];
    ch[CH_NAME[i]] = v > 0 ? v : 0;
    Serial.printf("  %-5s %8u → %8.1f\n", CH_NAME[i], buf[CH_IDX[i]], v > 0 ? v : 0);
  }
  float c = buf[IDX_CLEAR] - darkClear;
  float n = buf[IDX_NIR] - darkNir;
  ch["CLEAR"] = c > 0 ? c : 0;
  ch["NIR"]   = n > 0 ? n : 0;

  if (saturated) {
    Serial.println("  ! 포화 — 값이 잘렸습니다. 서버가 이 세션을 실패로 닫습니다.");
  }

  String body;
  serializeJson(doc, body);
  String url = String(SERVER_BASE) + "/api/iot/sessions/" + sessionId + "/samples";

  // 재전송은 하되 쌓아 두지는 않는다. 세션이 열려 있는 동안에만 의미가 있다.
  for (uint8_t attempt = 1; attempt <= POST_RETRY; attempt++) {
    int code;
    String res = httpJson("POST", url, body, &code);
    Serial.printf("  POST %s [%d] %s\n", stepName, code, res.c_str());

    if (code == 200) {
      // 이 단계는 끝났다. 다음 지시는 사용자가 키오스크에서 다시 누를 때
      // 폴링으로 온다. 여기서 바로 다음 단계로 넘어가면 안 된다 — 아직
      // 시료를 바꿔 올리지 않았다.
      armedStep = STEP_NONE;
      JsonDocument ack;
      if (!deserializeJson(ack, res) && !ack["next_step"].is<const char*>()) {
        Serial.println("[세션] 완료. 키오스크 화면을 보세요.");
      }
      return;
    }

    // 4xx는 다시 보내도 같은 답이 온다(순서 어긋남·포화·세션 종료).
    // 서버가 세션을 닫았을 테니 다음 폴링에서 정리된다.
    if (code >= 400 && code < 500) { armedStep = STEP_NONE; return; }

    delay(1000);
  }
  // 지시는 서버에 그대로 남아 있다(capturing_*). 다음 폴링에서 다시
  // 내려오므로, 여기서 armedStep을 비워도 사용자가 다시 누를 필요는 없다.
  Serial.println("  전송 실패 — 다음 폴링에서 다시 시도합니다");
}

// ─── 메인 ─────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.printf("\n=== HwaDam CARE Node [%s] measure ===\n", NODE_ID);

  if (!as7341.begin(AS7341_I2CADDR_DEFAULT, &Wire)) {
    Serial.println("AS7341을 찾지 못했습니다 (0x39). I2C_Scanner로 확인하세요.");
    while (1) delay(1000);
  }
  as7341.setATIME(ATIME_VAL);
  as7341.setASTEP(ASTEP_VAL);
  as7341.setGain(curGain);
  as7341.enableLED(false);
  Serial.printf("AS7341 OK  게인 %s  LED %umA  포화한계 %u\n",
                gainName(curGain), curLedMa, fullScale());

  connectWiFi();
  syncTime();
  Serial.println("\n대기 중 — 키오스크에서 측정을 시작하세요.\n");
}

void loop() {
  // 서버 상태를 계속 따라간다. 세션이 새로 열렸는지, 사용자가 측정을
  // 눌렀는지, 취소·만료되었는지 모두 이 한 곳에서 알게 된다.
  if (millis() - lastPoll >= POLL_MS) pollSession();

  // 지시가 내려와 있을 때만 잰다. 세션이 열려 있어도 사용자가 아직
  // 누르지 않았으면 측정부에 아무것도 없을 수 있다.
  if (armedStep != STEP_NONE) captureAndPost();

  if (millis() - lastNtpSync > NTP_RESYNC_MS) syncTime();

  delay(20);
}
