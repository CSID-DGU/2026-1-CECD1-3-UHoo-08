// 화담 CARE — AS7341 분광 센서 브링업
// 배선: VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21 (SHT31 0x44와 같은 버스)
// 라이브러리: Adafruit AS7341 (라이브러리 매니저에서 "Adafruit AS7341")
//
// ─────────────────────────────────────────────────────────────
// 이 스케치의 목적은 "값이 나온다"가 아니라 "그 값을 믿어도 되는가"다.
//
// 우리가 찾으려는 노화 신호는 5~10% 수준이다. 반사광 측정은 거리·각도·
// 외부광에 크게 흔들리므로, 측정 오차가 그보다 크면 이후 작업이 전부
// 무의미해진다. 그래서 브링업 단계에서 오차부터 실측한다.
//
// 명령(시리얼 모니터에서 문자 하나 + Enter, 줄 끝 설정은 아무거나):
//   ?  도움말
//   i  센서 상태 (게인·적분시간·포화 한계)
//   d  암전류 측정 (LED 끔) — 이후 모든 측정에서 빼는 기준값
//   s  단일 측정 (LED 켬) — 원시값·암전류 보정값·CLEAR 정규화값
//   r  반복 측정 20회 → 채널별 변동계수(CV) 산출          ★ 핵심
//   m  재장착 반복성 5세트 → 실제 오차 하한 산출          ★ 더 중요
//   a  자동 게인 (포화도 20~70% 구간에 맞춤)
//   +  게인 한 단계 위 / -  한 단계 아래
//   L  LED 전류 순환 (4 / 10 / 25 / 50 mA)
// ─────────────────────────────────────────────────────────────

#include <Wire.h>
#include <math.h>
#include "Adafruit_AS7341.h"

#define SDA_PIN 21
#define SCL_PIN 22

Adafruit_AS7341 as7341;

// ── 적분 설정 ────────────────────────────────────────────────
// 총 적분시간 = (ATIME+1) × (ASTEP+1) × 2.78µs
//             = 101 × 1000 × 2.78µs ≈ 281ms  (사이클 1회)
// readAllChannels는 SMUX를 바꿔가며 두 번 적분하므로 실제로는 약 560ms 걸린다.
// 길게 잡을수록 신호가 커지고 노이즈 비중이 줄지만, 그만큼 느려진다.
const uint8_t  ATIME_VAL = 100;
const uint16_t ASTEP_VAL = 999;

// ADC 포화 한계.
// 이론상 (ATIME+1)×(ASTEP+1) = 101,000이지만 레지스터가 16비트라
// 65535에서 잘린다. 즉 이 설정에서는 65535가 천장이다.
uint32_t fullScale() {
  uint32_t theoretical = (uint32_t)(ATIME_VAL + 1) * (uint32_t)(ASTEP_VAL + 1);
  return theoretical > 65535 ? 65535 : theoretical;
}

// 포화 경고 기준. 천장에 가까워지면 값이 더 이상 빛에 비례하지 않는다.
// 90%를 넘으면 이미 선형성이 의심스럽고, 100%면 정보가 잘려나간 것이다.
const float SAT_WARN_RATIO = 0.90f;

// ── 채널 인덱스 ──────────────────────────────────────────────
// readAllChannels(uint16_t*)는 12칸 버퍼를 채운다. 내부 동작은 이렇다.
//
//   1) SMUX를 F1~F4+Clear+NIR로 설정 → 적분 → ADC0~5를 buf[0..5]에 기록
//   2) SMUX를 F5~F8+Clear+NIR로 설정 → 적분 → ADC0~5를 buf[6..11]에 기록
//
// 그래서 CLEAR와 NIR이 두 번 들어간다. buf[4], buf[5]는 1차 사이클의 것이고
// buf[10], buf[11]은 2차 사이클의 것이다.
//
//   [0] F1 415nm    [4] CLEAR(1차) ← 쓰지 않는다
//   [1] F2 445nm    [5] NIR(1차)   ← 쓰지 않는다
//   [2] F3 480nm    [6] F5 555nm   [10] CLEAR ← 이것을 쓴다
//   [3] F4 515nm    [7] F6 590nm   [11] NIR   ← 이것을 쓴다
//                   [8] F7 630nm
//                   [9] F8 680nm
//
// 1차 CLEAR를 쓰면 F5~F8과 적분 시점이 달라 정규화 기준이 어긋난다.
// 조명이 조금만 흔들려도 앞 네 채널과 뒤 네 채널이 서로 다른 기준으로
// 나뉘어, 없는 스펙트럼 변화가 생긴 것처럼 보인다.
const uint8_t  CH_IDX[8] = {0, 1, 2, 3, 6, 7, 8, 9};
const uint16_t CH_NM[8]  = {415, 445, 480, 515, 555, 590, 630, 680};
const char*    CH_NAME[8] = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"};
const uint8_t  IDX_CLEAR = 10;
const uint8_t  IDX_NIR   = 11;

// ── 상태 ─────────────────────────────────────────────────────
as7341_gain_t curGain = AS7341_GAIN_64X;
uint16_t curLedMa = 10;

// 암전류(LED 끈 상태의 기본 출력). 센서 자체 누설과 외부광이 섞여 있다.
float darkCh[8] = {0};
float darkClear = 0, darkNir = 0;
bool  darkValid = false;

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

// ── 측정 ─────────────────────────────────────────────────────

// LED를 켜고 끄는 시점이 중요하다. LED는 켠 직후 밝기가 안정되지 않으므로
// 예열 시간을 준다. 반대로 측정이 끝나면 바로 꺼야 시료가 가열되지 않는다.
// (열이 쌓이면 그것 자체가 시료를 변화시킨다)
const uint16_t LED_WARMUP_MS = 200;

bool measure(uint16_t* buf, bool ledOn) {
  if (ledOn) {
    as7341.setLEDCurrent(curLedMa);
    as7341.enableLED(true);
    delay(LED_WARMUP_MS);
  }
  bool ok = as7341.readAllChannels(buf);
  if (ledOn) as7341.enableLED(false);
  return ok;
}

// 포화 검사. 하나라도 천장에 닿으면 그 측정은 통째로 버려야 한다.
int checkSaturation(const uint16_t* buf, bool verbose) {
  uint32_t fs = fullScale();
  uint32_t warn = (uint32_t)(fs * SAT_WARN_RATIO);
  int hits = 0;

  for (int i = 0; i < 8; i++) {
    uint16_t v = buf[CH_IDX[i]];
    if (v >= warn) {
      hits++;
      if (verbose) {
        Serial.printf("  [포화] %s %dnm = %u (%.0f%% / 한계 %u)\n",
                      CH_NAME[i], CH_NM[i], v, 100.0 * v / fs, fs);
      }
    }
  }
  if (buf[IDX_CLEAR] >= warn) {
    hits++;
    if (verbose) {
      Serial.printf("  [포화] CLEAR = %u (%.0f%% / 한계 %u)\n",
                    buf[IDX_CLEAR], 100.0 * buf[IDX_CLEAR] / fs, fs);
    }
  }
  if (hits && verbose) {
    Serial.println("  → 게인을 낮추거나(-) LED 전류를 줄이세요. 이 측정은 신뢰할 수 없습니다.");
  }
  return hits;
}

// ── 명령 구현 ────────────────────────────────────────────────

void cmdInfo() {
  uint32_t fs = fullScale();
  long tint = as7341.getTINT();
  Serial.println();
  Serial.println("── 센서 상태 ──");
  Serial.printf("  게인        %s\n", gainName(as7341.getGain()));
  Serial.printf("  ATIME/ASTEP %u / %u\n", as7341.getATIME(), as7341.getASTEP());
  Serial.printf("  적분시간    %ld ms (사이클 1회) · 전채널 약 %ld ms\n", tint, tint * 2);
  Serial.printf("  포화 한계   %u  (경고 기준 %u)\n", fs, (uint32_t)(fs * SAT_WARN_RATIO));
  Serial.printf("  LED 전류    %u mA\n", curLedMa);
  Serial.printf("  암전류      %s\n", darkValid ? "측정됨" : "없음 — 먼저 d 를 실행하세요");
  Serial.println();
}

void cmdDark() {
  Serial.println();
  Serial.println("── 암전류 측정 (LED 끔) ──");
  Serial.println("  뚜껑을 덮고 외부광을 차단한 상태여야 합니다. 5회 평균을 냅니다.");

  double sum[8] = {0}, sumClear = 0, sumNir = 0;
  uint16_t buf[12];
  int n = 0;

  for (int k = 0; k < 5; k++) {
    if (!measure(buf, false)) { Serial.println("  읽기 실패"); return; }
    for (int i = 0; i < 8; i++) sum[i] += buf[CH_IDX[i]];
    sumClear += buf[IDX_CLEAR];
    sumNir   += buf[IDX_NIR];
    n++;
  }

  Serial.println("  채널   파장    암전류");
  for (int i = 0; i < 8; i++) {
    darkCh[i] = sum[i] / n;
    Serial.printf("  %-5s %4dnm  %8.1f\n", CH_NAME[i], CH_NM[i], darkCh[i]);
  }
  darkClear = sumClear / n;
  darkNir   = sumNir / n;
  Serial.printf("  CLEAR         %8.1f\n", darkClear);
  Serial.printf("  NIR           %8.1f\n", darkNir);
  darkValid = true;

  // 암전류가 크다는 것은 빛이 새어 들어오고 있다는 뜻이다.
  // 이 상태로 반사광을 재면 외부광 변화가 그대로 오차가 된다.
  uint32_t fs = fullScale();
  float ratio = 100.0 * darkClear / fs;
  Serial.printf("\n  CLEAR 암전류가 포화 한계의 %.2f%%입니다.\n", ratio);
  if (ratio > 2.0) {
    Serial.println("  → 높습니다. 외부광이 새고 있을 가능성이 큽니다. 차광부터 잡으세요.");
  } else {
    Serial.println("  → 차광은 양호합니다.");
  }
  Serial.println();
}

void printOne(const uint16_t* buf) {
  uint32_t fs = fullScale();
  float clearCorr = buf[IDX_CLEAR] - (darkValid ? darkClear : 0);

  Serial.println("  채널   파장     원시    암보정   /CLEAR   포화율");
  for (int i = 0; i < 8; i++) {
    uint16_t raw = buf[CH_IDX[i]];
    float corr = raw - (darkValid ? darkCh[i] : 0);
    float norm = (clearCorr > 1.0) ? corr / clearCorr : NAN;
    Serial.printf("  %-5s %4dnm %8u %9.1f %8.4f %6.1f%%\n",
                  CH_NAME[i], CH_NM[i], raw, corr, norm, 100.0 * raw / fs);
  }
  Serial.printf("  CLEAR        %8u %9.1f          %6.1f%%\n",
                buf[IDX_CLEAR], clearCorr, 100.0 * buf[IDX_CLEAR] / fs);
  Serial.printf("  NIR          %8u %9.1f\n",
                buf[IDX_NIR], buf[IDX_NIR] - (darkValid ? darkNir : 0));
}

void cmdSingle() {
  uint16_t buf[12];
  Serial.println();
  Serial.println("── 단일 측정 (LED 켬) ──");
  if (!measure(buf, true)) { Serial.println("  읽기 실패"); return; }
  printOne(buf);
  checkSaturation(buf, true);
  if (!darkValid) Serial.println("  ! 암전류를 아직 안 쟀습니다(d). 암보정 값은 원시값과 같습니다.");
  Serial.println();
}

// 평균과 표본표준편차. 변동계수 CV = 표준편차 / 평균 × 100 [%]
void meanSd(const float* v, int n, float* outMean, float* outSd) {
  double s = 0;
  for (int i = 0; i < n; i++) s += v[i];
  double m = s / n;
  double q = 0;
  for (int i = 0; i < n; i++) { double d = v[i] - m; q += d * d; }
  *outMean = m;
  *outSd = (n > 1) ? sqrt(q / (n - 1)) : 0;
}

// CV로부터 "판별 가능한 최소 변화율"을 계산한다.
//
// 두 시점의 평균을 비교할 때 차이의 표준오차는 CV×√(2/n)이다.
// 95% 신뢰수준에서 우연이 아니라고 말하려면 대략 2.8×CV/√n 이상 차이나야 한다.
// n=20이면 2.8/4.47 ≈ 0.63이므로, CV의 약 0.63배가 판별 한계다.
float minDetectable(float cvPct, int n) {
  if (n < 2) return NAN;
  return 2.8f * cvPct / sqrt((float)n);
}

void printCvTable(const char* title, float data[9][20], int n) {
  Serial.println();
  Serial.printf("── %s (n=%d) ──\n", title, n);
  Serial.println("  채널   파장       평균     표준편차    CV%   판별한계%");

  const char* names[9] = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "CLR"};
  const uint16_t nms[9] = {415, 445, 480, 515, 555, 590, 630, 680, 0};

  float worstCv = 0;
  for (int i = 0; i < 9; i++) {
    float m, sd;
    meanSd(data[i], n, &m, &sd);
    float cv = (m > 1.0) ? 100.0 * sd / m : NAN;
    if (!isnan(cv) && i < 8 && cv > worstCv) worstCv = cv;

    if (nms[i]) {
      Serial.printf("  %-5s %4dnm %10.1f %10.2f %6.2f %8.2f\n",
                    names[i], nms[i], m, sd, cv, minDetectable(cv, n));
    } else {
      Serial.printf("  %-5s       %10.1f %10.2f %6.2f %8.2f\n",
                    names[i], m, sd, cv, minDetectable(cv, n));
    }
  }
  Serial.printf("\n  8채널 중 최악 CV = %.2f%%\n", worstCv);
}

void printJudgement(float worstCv, int n) {
  Serial.println();
  Serial.println("── 판단 기준 ──");
  Serial.println("  우리가 찾는 노화 신호는 5~10% 수준이다. 측정 오차가 그보다 크면");
  Serial.println("  실제 변화인지 흔들림인지 구분할 수 없다.");
  Serial.println();
  Serial.println("    CV ≤ 1%    단일 측정으로도 5% 변화를 잡아낸다");
  Serial.println("    1 ~ 3%     20회 평균이면 5% 변화를 잡아낸다");
  Serial.println("    3 ~ 5%     10% 이상 변화만 말할 수 있다");
  Serial.println("    5% 초과    사용 불가. 지그·차광·거리부터 고쳐야 한다");
  Serial.println();
  Serial.printf("  현재 최악 CV %.2f%% → 20회 평균 시 판별 한계 %.2f%%\n",
                worstCv, minDetectable(worstCv, n));
  if (worstCv <= 1.0)      Serial.println("  → 매우 양호합니다.");
  else if (worstCv <= 3.0) Serial.println("  → 쓸 만합니다. 평균을 내서 사용하세요.");
  else if (worstCv <= 5.0) Serial.println("  → 아슬아슬합니다. 5% 변화는 못 잡습니다.");
  else                     Serial.println("  → 이 상태로는 이후 작업이 무의미합니다. 지그를 고치세요.");
  Serial.println();
}

void cmdRepeat() {
  const int N = 20;
  static float data[9][20];
  uint16_t buf[12];

  Serial.println();
  Serial.println("── 반복 측정 20회 ──");
  Serial.println("  시료를 건드리지 마세요. 손도 대지 말고 그대로 두십시오.");
  Serial.println("  약 15초 걸립니다.");

  int satCount = 0;
  for (int k = 0; k < N; k++) {
    if (!measure(buf, true)) { Serial.println("  읽기 실패"); return; }
    if (checkSaturation(buf, false)) satCount++;
    for (int i = 0; i < 8; i++) data[i][k] = buf[CH_IDX[i]];
    data[8][k] = buf[IDX_CLEAR];
    Serial.print(".");
  }
  Serial.println();

  if (satCount) {
    Serial.printf("\n  ! %d/%d 회에서 포화가 발생했습니다. 아래 통계는 믿을 수 없습니다.\n",
                  satCount, N);
    Serial.println("    게인을 낮추고(-) 다시 실행하세요.");
  }

  printCvTable("원시값 변동", data, N);

  float worstRaw = 0;
  for (int i = 0; i < 8; i++) {
    float m, sd; meanSd(data[i], N, &m, &sd);
    float cv = (m > 1.0) ? 100.0 * sd / m : 0;
    if (cv > worstRaw) worstRaw = cv;
  }

  // CLEAR로 나눈 값의 변동도 함께 본다.
  //
  // 거리가 조금 멀어지면 모든 채널이 함께 작아진다. 이런 공통 변동은
  // CLEAR로 나누면 상쇄된다. 원시 CV는 큰데 정규화 CV가 작다면, 오차의
  // 주범이 거리·조명 세기이고 스펙트럼 모양 자체는 안정적이라는 뜻이다.
  // 그 경우 우리는 정규화된 값을 쓰면 된다.
  static float norm[9][20];
  for (int k = 0; k < N; k++) {
    float c = data[8][k];
    for (int i = 0; i < 8; i++) norm[i][k] = (c > 1.0) ? data[i][k] / c * 1000.0 : 0;
    norm[8][k] = 1000.0;
  }
  printCvTable("CLEAR 정규화 변동 (×1000)", norm, N);

  float worstNorm = 0;
  for (int i = 0; i < 8; i++) {
    float m, sd; meanSd(norm[i], N, &m, &sd);
    float cv = (m > 1.0) ? 100.0 * sd / m : 0;
    if (cv > worstNorm) worstNorm = cv;
  }

  Serial.printf("\n  원시 최악 CV %.2f%%  →  정규화 최악 CV %.2f%%\n", worstRaw, worstNorm);
  if (worstNorm < worstRaw * 0.7) {
    Serial.println("  → 정규화가 효과적입니다. 오차의 주범은 조명 세기·거리입니다.");
  } else {
    Serial.println("  → 정규화 효과가 작습니다. 오차가 채널별로 독립적이라는 뜻이며,");
    Serial.println("     보통 적분시간이 짧거나 신호가 약할 때 그렇습니다.");
  }

  printJudgement(worstNorm, N);
  Serial.println("  ! 이 CV는 '시료를 안 건드렸을 때'의 값입니다. 실제 오차는 이보다 큽니다.");
  Serial.println("    m 명령으로 재장착 반복성을 재보세요. 그쪽이 진짜 숫자입니다.");
  Serial.println();
}

void cmdRemount() {
  const int SETS = 5, REPS = 5;
  static float setMean[9][20];
  uint16_t buf[12];

  Serial.println();
  Serial.println("── 재장착 반복성 ──");
  Serial.println("  실제 사용은 며칠 간격으로 시료를 다시 올려놓고 재는 것입니다.");
  Serial.println("  그때 생기는 오차가 진짜 오차입니다. 5세트를 잽니다.");
  Serial.println("  각 세트마다 시료를 완전히 꺼냈다가 다시 올려놓으세요.");

  for (int s = 0; s < SETS; s++) {
    Serial.printf("\n  [%d/%d] 시료를 꺼냈다가 다시 올려놓고 Enter를 누르세요.\n", s + 1, SETS);
    while (Serial.available()) Serial.read();
    while (!Serial.available()) delay(50);
    while (Serial.available()) Serial.read();

    double sum[9] = {0};
    for (int k = 0; k < REPS; k++) {
      if (!measure(buf, true)) { Serial.println("  읽기 실패"); return; }
      for (int i = 0; i < 8; i++) sum[i] += buf[CH_IDX[i]];
      sum[8] += buf[IDX_CLEAR];
      Serial.print(".");
    }
    for (int i = 0; i < 9; i++) setMean[i][s] = sum[i] / REPS;
    Serial.printf(" CLEAR=%.0f", setMean[8][s]);
  }
  Serial.println();

  printCvTable("세트 간 변동 (재장착 포함)", setMean, SETS);

  static float norm[9][20];
  for (int s = 0; s < SETS; s++) {
    float c = setMean[8][s];
    for (int i = 0; i < 8; i++) norm[i][s] = (c > 1.0) ? setMean[i][s] / c * 1000.0 : 0;
    norm[8][s] = 1000.0;
  }
  printCvTable("세트 간 변동 · CLEAR 정규화 (×1000)", norm, SETS);

  float worst = 0;
  for (int i = 0; i < 8; i++) {
    float m, sd; meanSd(norm[i], SETS, &m, &sd);
    float cv = (m > 1.0) ? 100.0 * sd / m : 0;
    if (cv > worst) worst = cv;
  }

  Serial.println();
  Serial.println("  이 숫자가 optical_delta_pct의 오차 하한입니다.");
  Serial.printf("  재장착 CV %.2f%% → 이보다 작은 변화는 측정으로 구분할 수 없습니다.\n", worst);
  if (worst > 5.0) {
    Serial.println("  → 5%를 넘습니다. 지그의 위치 재현성이 부족합니다.");
    Serial.println("     시료를 놓는 자리에 물리적 가이드(모서리 두 변)를 만드세요.");
  }
  Serial.println();
}

void cmdAutoGain() {
  // 포화도 20~70% 구간을 목표로 한다.
  // 너무 낮으면 노이즈 비중이 커지고, 너무 높으면 포화 위험이 있다.
  const as7341_gain_t ladder[] = {
    AS7341_GAIN_0_5X, AS7341_GAIN_1X, AS7341_GAIN_2X, AS7341_GAIN_4X,
    AS7341_GAIN_8X, AS7341_GAIN_16X, AS7341_GAIN_32X, AS7341_GAIN_64X,
    AS7341_GAIN_128X, AS7341_GAIN_256X, AS7341_GAIN_512X
  };
  const int LADDER_N = sizeof(ladder) / sizeof(ladder[0]);
  uint32_t fs = fullScale();
  uint16_t buf[12];

  Serial.println();
  Serial.println("── 자동 게인 ──");

  for (int gi = LADDER_N - 1; gi >= 0; gi--) {
    curGain = ladder[gi];
    as7341.setGain(curGain);
    if (!measure(buf, true)) { Serial.println("  읽기 실패"); return; }

    uint16_t peak = 0;
    for (int i = 0; i < 8; i++) if (buf[CH_IDX[i]] > peak) peak = buf[CH_IDX[i]];
    if (buf[IDX_CLEAR] > peak) peak = buf[IDX_CLEAR];

    float ratio = 100.0 * peak / fs;
    Serial.printf("  %-6s 최대 %5u (%5.1f%%)\n", gainName(curGain), peak, ratio);

    if (ratio <= 70.0) {
      if (ratio < 20.0) {
        Serial.println("  → 이 아래로는 신호가 너무 약합니다. 여기서 멈춥니다.");
        Serial.println("     LED 전류를 올리거나(L) 거리를 좁히세요.");
      }
      Serial.printf("  선택: %s\n\n", gainName(curGain));
      return;
    }
  }
  Serial.println("  ! 최저 게인에서도 포화합니다. LED 전류를 낮추거나 거리를 늘리세요.\n");
}

void cmdGainStep(int dir) {
  int g = (int)curGain + dir;
  if (g < 0) g = 0;
  if (g > (int)AS7341_GAIN_512X) g = (int)AS7341_GAIN_512X;
  curGain = (as7341_gain_t)g;
  as7341.setGain(curGain);
  Serial.printf("  게인 → %s (암전류를 다시 재세요: d)\n", gainName(curGain));
  darkValid = false;   // 게인이 바뀌면 암전류도 달라진다
}

void cmdLedStep() {
  const uint16_t steps[] = {4, 10, 25, 50};
  int i = 0;
  for (; i < 4; i++) if (steps[i] == curLedMa) break;
  curLedMa = steps[(i + 1) % 4];
  Serial.printf("  LED 전류 → %u mA\n", curLedMa);
}

void help() {
  Serial.println();
  Serial.println("=== 명령 ===");
  Serial.println("  i  센서 상태        d  암전류 측정(LED 끔)");
  Serial.println("  s  단일 측정        r  반복 20회 → CV");
  Serial.println("  m  재장착 반복성    a  자동 게인");
  Serial.println("  +  게인 up          -  게인 down       L  LED 전류");
  Serial.println();
  Serial.println("권장 순서: a → d → s → r → m");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.println("=== 화담 CARE — AS7341 브링업 ===");

  if (!as7341.begin(AS7341_I2CADDR_DEFAULT, &Wire)) {
    Serial.println("AS7341을 찾지 못했습니다.");
    Serial.println("  · 0x39가 맞는지 I2C_Scanner로 확인");
    Serial.println("  · SHT31(0x44)과 같은 버스를 쓰므로 SDA/SCL 배선을 함께 점검");
    Serial.println("  · 풀업 저항은 보드에 내장된 경우가 많으나, 두 보드가 동시에 달리면");
    Serial.println("    풀업이 병렬이 되어 값이 절반이 됩니다. 보통 문제없지만 통신이");
    Serial.println("    불안정하면 한쪽 풀업을 떼는 것을 고려하세요.");
    while (1) delay(1000);
  }

  as7341.setATIME(ATIME_VAL);
  as7341.setASTEP(ASTEP_VAL);
  as7341.setGain(curGain);

  Serial.println("AS7341 OK (0x39)");
  cmdInfo();
  help();
  Serial.println("먼저 a(자동 게인) → d(암전류) 순으로 실행하세요.");
}

void loop() {
  if (!Serial.available()) return;

  char c = Serial.read();
  if (c == '\n' || c == '\r' || c == ' ') return;

  switch (c) {
    case '?': help(); break;
    case 'i': cmdInfo(); break;
    case 'd': cmdDark(); break;
    case 's': cmdSingle(); break;
    case 'r': cmdRepeat(); break;
    case 'm': cmdRemount(); break;
    case 'a': cmdAutoGain(); break;
    case '+': cmdGainStep(1); break;
    case '-': cmdGainStep(-1); break;
    case 'L': case 'l': cmdLedStep(); break;
    default:
      Serial.printf("  알 수 없는 명령: %c  (? 로 도움말)\n", c);
  }
}
