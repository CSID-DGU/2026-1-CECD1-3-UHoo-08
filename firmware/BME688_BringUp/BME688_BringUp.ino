// 화담 CARE — BME688 가스 센서 브링업
// 배선: VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21
//       (SHT31 0x44 · AS7341 0x39과 같은 버스. 주소가 겹치지 않는다)
// 라이브러리: Adafruit BME680 + Adafruit Unified Sensor
//
// ─────────────────────────────────────────────────────────────
// 라이브러리 이름이 "BME680"인 이유
//
// BME688은 BME680과 칩 ID가 같고 레지스터 구조도 호환된다. 그래서
// Adafruit_BME680 라이브러리가 그대로 동작한다. BME688에만 있는 기능은
// 히터 프로파일 스캔(여러 온도를 순차로 가열해 가스를 구분)인데, 그건
// Bosch BSEC2를 써야 하고 우리는 쓰지 않는다.
//
// BSEC2를 안 쓰는 이유: BSEC은 폐쇄 바이너리이고 내부에서 자체 기준선을
// 학습해 IAQ 점수를 뱉는다. 그 학습 과정을 우리가 통제할 수 없고, 언제
// 어떻게 보정되는지 설명할 수 없다. 설계서는 log(R)을 온습도로 회귀
// 보정해 잔차를 보는 방식이라, 원시 저항값만 있으면 충분하다.
//
// ─────────────────────────────────────────────────────────────
// 이 센서로 알 수 있는 것과 없는 것
//
// BME688이 주는 값은 가열된 금속산화물의 **저항 하나**다.
//   공기가 깨끗하다 → 저항이 높다
//   VOC가 늘어난다  → 저항이 떨어진다
//
// 어떤 물질인지는 구분하지 못한다. 향수를 뿌려도, 화장품이 산패해도,
// 알코올 솜을 열어도 똑같이 저항이 떨어진다. 그래서 설계서가 VOC를
// "판정"이 아니라 "언제 확인할지 알려주는 트리거"로만 쓰고, 급등하면
// 키오스크가 사용자에게 되묻는 구조를 택한 것이다.
//
// ─────────────────────────────────────────────────────────────
// 명령 (시리얼 모니터에서 문자 하나 + Enter)
//   ?  도움말
//   i  센서 상태
//   s  단일 측정 (SHT31이 있으면 나란히 비교)
//   c  자체 발열 측정 — BME688 온도가 SHT31보다 얼마나 높은가   ★
//   w  예열 드리프트 감시 — 저항이 언제 안정되는가              ★
//   t  반응 시험 — 알코올 솜·입김에 저항이 떨어지는가           ★
//   l  CSV 로그 — 회귀 보정용 데이터 수집
// ─────────────────────────────────────────────────────────────

#include <Wire.h>
#include <math.h>
#include "Adafruit_BME680.h"
#include "Adafruit_SHT31.h"

#define SDA_PIN 21
#define SCL_PIN 22

// 기본 생성자는 내부적으로 &Wire를 쓴다. Wire.begin(SDA,SCL)을 먼저
// 호출하면 ESP32의 임의 핀 지정이 그대로 반영된다.
Adafruit_BME680 bme;
Adafruit_SHT31  sht31 = Adafruit_SHT31();

uint8_t bmeAddr = 0;
bool    shtOk   = false;

// ── 히터 설정 ────────────────────────────────────────────────
// 320℃ · 150ms는 Bosch 권장 기본값이다. 온도를 바꾸면 저항의 절대값이
// 통째로 달라지므로, 한 번 정하면 기준선 학습 내내 바꾸면 안 된다.
// 중간에 바꾸면 그동안 모은 기준선이 전부 무효가 된다.
const uint16_t HEATER_TEMP_C = 320;
const uint16_t HEATER_MS     = 150;

struct Reading {
  float tBme, rhBme, pHpa, rOhm;
  float tSht, rhSht;
  bool  ok;
};

Reading readAll() {
  Reading r = {NAN, NAN, NAN, NAN, NAN, NAN, false};

  if (!bme.performReading()) return r;
  r.tBme  = bme.temperature;
  r.rhBme = bme.humidity;
  r.pHpa  = bme.pressure / 100.0;
  r.rOhm  = bme.gas_resistance;

  if (shtOk) {
    r.tSht  = sht31.readTemperature();
    r.rhSht = sht31.readHumidity();
  }
  r.ok = true;
  return r;
}

// 절대습도 [g/m³]. SHT31_Read 스케치와 같은 식을 쓴다.
float absoluteHumidity(float t, float rh) {
  float es = 6.112 * exp(17.67 * t / (t + 243.5));
  return 2.1674 * es * rh / (273.15 + t);
}

// ── 명령 ─────────────────────────────────────────────────────

void cmdInfo() {
  Serial.println();
  Serial.println("── 센서 상태 ──");
  Serial.printf("  BME688   0x%02X\n", bmeAddr);
  Serial.printf("  SHT31    %s\n", shtOk ? "0x44 연결됨" : "없음 — 자체 발열 비교 불가");
  Serial.printf("  히터     %u℃ · %ums\n", HEATER_TEMP_C, HEATER_MS);
  Serial.println();
}

void cmdSingle() {
  Serial.println();
  Serial.println("── 단일 측정 ──");
  Reading r = readAll();
  if (!r.ok) { Serial.println("  읽기 실패"); return; }

  Serial.printf("  BME688  %.2f℃  %.1f%%RH  %.1f hPa\n", r.tBme, r.rhBme, r.pHpa);
  Serial.printf("  가스저항  %.0f Ω  (%.1f kΩ)\n", r.rOhm, r.rOhm / 1000.0);

  if (shtOk && !isnan(r.tSht)) {
    Serial.printf("  SHT31   %.2f℃  %.1f%%RH  AH %.2f g/m³\n",
                  r.tSht, r.rhSht, absoluteHumidity(r.tSht, r.rhSht));
    Serial.printf("  차이    온도 %+.2f℃  습도 %+.1f%%RH  (BME − SHT)\n",
                  r.tBme - r.tSht, r.rhBme - r.rhSht);
  }
  Serial.println();
}

// ── 자체 발열 측정 ───────────────────────────────────────────
//
// BME688은 가스를 재려고 내부 히터를 320℃까지 올린다. 그 열이 같은
// 패키지 안의 온도 센서로 새어 들어가서, BME688의 온도는 실제 공기보다
// 높게 나온다. 습도는 온도에 연동되므로 함께 낮게 나온다.
//
// 이게 왜 중요한가: 열이력 적산(erl.py)은 온도를 Q10 지수에 넣는다.
// 1℃가 높게 들어가면 노화 속도가 약 7% 부풀려진다. 몇 달 적산하면
// 무시할 수 없는 차이가 된다.
//
// 따라서 보관 노드에서 **온습도는 SHT31, 가스는 BME688**로 나눠 쓴다.
// 이 명령은 그 차이가 실제로 얼마인지 재서 판단 근거를 남긴다.
void cmdSelfHeat() {
  const int N = 10;

  Serial.println();
  Serial.println("── 자체 발열 측정 ──");
  if (!shtOk) {
    Serial.println("  SHT31이 없어 비교할 수 없습니다. 같은 버스에 연결하세요.");
    Serial.println();
    return;
  }

  Serial.println("  두 센서를 같은 자리에 두고 10회 비교합니다. 손을 대지 마세요.");
  Serial.println();
  Serial.println("  회차   BME688     SHT31      온도차     습도차");

  double sumT = 0, sumRh = 0;
  int n = 0;

  for (int k = 0; k < N; k++) {
    Reading r = readAll();
    if (!r.ok || isnan(r.tSht)) { Serial.println("  읽기 실패"); continue; }

    float dT  = r.tBme - r.tSht;
    float dRh = r.rhBme - r.rhSht;
    sumT += dT; sumRh += dRh; n++;

    Serial.printf("  %2d   %6.2f℃   %6.2f℃   %+6.2f℃   %+6.1f%%\n",
                  k + 1, r.tBme, r.tSht, dT, dRh);
    delay(2000);
  }

  if (!n) { Serial.println("  측정 실패"); return; }

  float mT = sumT / n, mRh = sumRh / n;
  Serial.printf("\n  평균 온도차 %+.2f℃  ·  평균 습도차 %+.1f%%RH\n", mT, mRh);

  // Q10 = 2 기준: 1℃ 차이는 노화 속도 2^(1/10) ≈ 7.2% 차이를 만든다.
  float speedErr = (pow(2.0, mT / 10.0) - 1.0) * 100.0;
  Serial.printf("  이 온도차를 열이력에 그대로 쓰면 노화 속도가 %+.1f%% 어긋납니다.\n",
                speedErr);

  if (fabs(mT) < 0.3) {
    Serial.println("  → 차이가 작습니다. 다만 원칙대로 온습도는 SHT31을 쓰는 것이 맞습니다.");
  } else {
    Serial.println("  → 예상대로 BME688이 높게 나옵니다.");
    Serial.println("     보관 노드에서 온습도는 SHT31, 가스는 BME688로 나눠 씁니다.");
  }
  Serial.println();
}

// ── 예열 드리프트 ────────────────────────────────────────────
//
// MOX 센서는 전원을 켜자마자 제값을 내지 않는다. 히터가 데워지고 표면에
// 흡착된 것들이 떨어져 나가는 동안 저항이 계속 움직인다. 보통 수십 분,
// 길게는 며칠에 걸쳐 서서히 안정된다.
//
// 이 구간의 값을 기준선에 섞으면 "시간이 지날수록 공기가 나빠지는" 것처럼
// 보이는 가짜 추세가 생긴다. 그래서 언제부터 안정되는지 실측해두고,
// 노드 가동 후 그 시간만큼은 기준선 학습에서 빼야 한다.
void cmdWarmup() {
  Serial.println();
  Serial.println("── 예열 드리프트 감시 ──");
  Serial.println("  5초마다 재고 30초마다 요약합니다. 아무 키나 누르면 중단합니다.");
  Serial.println("  최소 20분은 지켜보세요. 그동안 방 안에 향수·알코올을 쓰지 마세요.");
  Serial.println();
  Serial.println("  경과      저항(kΩ)   시작대비   최근1분기울기   온도    습도");

  while (Serial.available()) Serial.read();

  uint32_t t0 = millis();
  float rFirst = NAN;
  float hist[12];        // 최근 1분 (5초 × 12)
  int   histN = 0;
  uint32_t lastReport = 0;

  while (!Serial.available()) {
    Reading r = readAll();
    if (!r.ok) { delay(5000); continue; }

    if (isnan(rFirst)) rFirst = r.rOhm;

    // 최근 1분 창을 밀어 넣는다
    if (histN < 12) hist[histN++] = r.rOhm;
    else {
      for (int i = 0; i < 11; i++) hist[i] = hist[i + 1];
      hist[11] = r.rOhm;
    }

    uint32_t elapsed = (millis() - t0) / 1000;
    if (elapsed - lastReport >= 30) {
      lastReport = elapsed;

      // 최근 1분 기울기 (최소제곱). 이게 0에 가까워지면 안정된 것이다.
      float slope = NAN;
      if (histN >= 6) {
        double sx = 0, sy = 0, sxy = 0, sxx = 0;
        for (int i = 0; i < histN; i++) {
          double x = i * 5.0;              // 초
          sx += x; sy += hist[i]; sxy += x * hist[i]; sxx += x * x;
        }
        double d = histN * sxx - sx * sx;
        if (fabs(d) > 1e-9) slope = (histN * sxy - sx * sy) / d * 60.0;  // Ω/분
      }

      float pct = (rFirst > 1) ? (r.rOhm - rFirst) / rFirst * 100.0 : NAN;
      Serial.printf("  %3lu:%02lu   %8.1f   %+7.1f%%   %+10.0f Ω/분   %5.1f℃  %4.1f%%\n",
                    elapsed / 60, elapsed % 60, r.rOhm / 1000.0, pct, slope,
                    r.tBme, r.rhBme);
    }
    delay(5000);
  }

  while (Serial.available()) Serial.read();
  Serial.println();
  Serial.println("  중단했습니다.");
  Serial.println("  기울기가 저항값의 0.5%/분 아래로 떨어지면 안정된 것으로 봅니다.");
  Serial.println("  그때까지 걸린 시간을 기록해 두세요. 노드 가동 후 그만큼은");
  Serial.println("  기준선 학습에서 제외해야 합니다.");
  Serial.println();
}

// ── 반응 시험 ────────────────────────────────────────────────
//
// 설계서에서 "가장 불확실"하다고 표시한 항목이다. 저항이 VOC에 실제로
// 반응하는지, 반응한다면 얼마나 크게·얼마나 빨리 반응하는지 본다.
//
// 산패한 화장품으로 시험하는 게 최종 목표지만, 그건 시료를 몇 주 묵혀야
// 한다. 지금은 확실히 VOC를 내는 것(알코올 솜, 입김)으로 센서가 살아
// 있는지부터 확인한다. 여기서 반응이 없으면 산패 시료에도 반응하지 않는다.
void cmdResponse() {
  Serial.println();
  Serial.println("── 반응 시험 ──");
  Serial.println("  1) 먼저 30초간 기준값을 잡습니다. 가만히 두세요.");
  Serial.println("  2) 그다음 알코올 솜을 센서 5cm 앞에서 열거나 입김을 부세요.");
  Serial.println("  아무 키나 누르면 중단합니다.");
  Serial.println();

  while (Serial.available()) Serial.read();

  // 기준값: 30초 평균
  double sum = 0; int n = 0;
  Serial.print("  기준값 측정 중");
  uint32_t t0 = millis();
  while (millis() - t0 < 30000) {
    Reading r = readAll();
    if (r.ok) { sum += r.rOhm; n++; Serial.print("."); }
    delay(2000);
  }
  Serial.println();

  if (!n) { Serial.println("  측정 실패"); return; }
  float base = sum / n;
  Serial.printf("  기준 저항 %.1f kΩ (n=%d)\n\n", base / 1000.0, n);
  Serial.println("  이제 VOC를 가까이 하세요.");
  Serial.println("  저항(kΩ)   기준대비    판정");

  float minPct = 0;
  while (!Serial.available()) {
    Reading r = readAll();
    if (!r.ok) { delay(1000); continue; }

    float pct = (r.rOhm - base) / base * 100.0;
    if (pct < minPct) minPct = pct;

    // 저항이 떨어지면 VOC가 늘어난 것이다. 방향이 반대면 뭔가 잘못됐다.
    const char* mark = "";
    if (pct < -30) mark = "◆◆◆ 강한 반응";
    else if (pct < -10) mark = "◆◆ 반응";
    else if (pct < -3) mark = "◆ 약한 반응";
    else if (pct > 10) mark = "↑ 상승 (환기·건조?)";

    Serial.printf("  %8.1f   %+7.1f%%   %s\n", r.rOhm / 1000.0, pct, mark);
    delay(1500);
  }

  while (Serial.available()) Serial.read();
  Serial.printf("\n  최대 하락 %.1f%%\n", minPct);
  if (minPct < -20) {
    Serial.println("  → 센서가 VOC에 확실히 반응합니다.");
  } else if (minPct < -5) {
    Serial.println("  → 반응은 있으나 약합니다. 더 가까이서 다시 해보세요.");
  } else {
    Serial.println("  → 반응이 없습니다. 예열이 덜 됐거나(w로 확인) 배선을 점검하세요.");
  }
  Serial.println();
}

// ── CSV 로그 ─────────────────────────────────────────────────
//
// 설계서의 기준선 모델은 log(R) ≈ a + b×T + c×RH 이다. 이 계수를 구하려면
// 온습도가 여러 값을 오가는 동안의 데이터가 필요하다. 하루 이상 켜두고
// 낮밤 온습도 변화를 담아야 회귀가 의미를 가진다.
//
// 이 명령은 첫 감을 잡기 위한 것이다. 실제 1~2주 기준선 학습은 노드
// 펌웨어가 sensor_readings에 쌓는 방식으로 간다(gas_resistance 컬럼이
// 이미 있다). 브링업에서는 시리얼 출력을 파일로 받아 회귀를 한 번
// 돌려보고, 계수가 말이 되는지만 확인한다.
void cmdLog() {
  Serial.println();
  Serial.println("── CSV 로그 (10초 간격) ──");
  Serial.println("  아무 키나 누르면 중단합니다. 시리얼 모니터 내용을 복사해 두세요.");
  Serial.println();
  Serial.println("t_s,T_bme,RH_bme,P_hpa,R_ohm,T_sht,RH_sht");

  while (Serial.available()) Serial.read();
  uint32_t t0 = millis();

  while (!Serial.available()) {
    Reading r = readAll();
    if (r.ok) {
      Serial.printf("%lu,%.2f,%.2f,%.2f,%.0f,",
                    (millis() - t0) / 1000, r.tBme, r.rhBme, r.pHpa, r.rOhm);
      if (shtOk && !isnan(r.tSht)) Serial.printf("%.2f,%.2f\n", r.tSht, r.rhSht);
      else                          Serial.println(",");
    }
    delay(10000);
  }

  while (Serial.available()) Serial.read();
  Serial.println("\n  중단했습니다.\n");
}

void help() {
  Serial.println();
  Serial.println("=== 명령 ===");
  Serial.println("  i  센서 상태        s  단일 측정");
  Serial.println("  c  자체 발열 측정   w  예열 드리프트");
  Serial.println("  t  반응 시험        l  CSV 로그");
  Serial.println();
  Serial.println("권장 순서: s → c → w(20분 이상) → t → l");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.println("=== 화담 CARE — BME688 브링업 ===");

  // 주소는 보드마다 다르다. SDO가 GND면 0x76, 3V3이면 0x77이다.
  // 둘 다 시도해서 잡히는 쪽을 쓴다.
  if (bme.begin(0x76)) {
    bmeAddr = 0x76;
  } else if (bme.begin(0x77)) {
    bmeAddr = 0x77;
  } else {
    Serial.println("BME688을 찾지 못했습니다.");
    Serial.println("  · I2C_Scanner로 0x76 또는 0x77이 잡히는지 확인");
    Serial.println("  · 보드에 CS 핀이 있으면 3V3에 연결해야 I2C로 동작하는 경우가 있음");
    Serial.println("  · SDO는 띄우거나 GND(0x76) / 3V3(0x77)");
    while (1) delay(1000);
  }
  Serial.printf("BME688 OK (0x%02X)\n", bmeAddr);

  // 오버샘플링과 IIR 필터.
  // 온습도는 어차피 SHT31을 쓸 것이므로 과하게 잡지 않고, 가스 측정의
  // 안정성에 무게를 둔다. IIR 필터는 압력·온도의 순간 변동을 눌러준다.
  bme.setTemperatureOversampling(BME680_OS_8X);
  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_4X);
  bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
  bme.setGasHeater(HEATER_TEMP_C, HEATER_MS);

  shtOk = sht31.begin(0x44);
  if (shtOk) {
    sht31.heater(false);   // 내장 히터는 결로 제거용. 켜면 측정이 왜곡된다
    Serial.println("SHT31 OK (0x44) — 자체 발열 비교 가능");
  } else {
    Serial.println("SHT31 없음 — c(자체 발열 측정)는 쓸 수 없습니다");
  }

  cmdInfo();
  help();
  Serial.println("전원을 켠 직후에는 저항이 계속 움직입니다.");
  Serial.println("먼저 w로 언제 안정되는지 확인하세요.");
}

void loop() {
  if (!Serial.available()) return;

  char c = Serial.read();
  if (c == '\n' || c == '\r' || c == ' ') return;

  switch (c) {
    case '?': help(); break;
    case 'i': cmdInfo(); break;
    case 's': cmdSingle(); break;
    case 'c': cmdSelfHeat(); break;
    case 'w': cmdWarmup(); break;
    case 't': cmdResponse(); break;
    case 'l': case 'L': cmdLog(); break;
    default:
      Serial.printf("  알 수 없는 명령: %c  (? 로 도움말)\n", c);
  }
}
