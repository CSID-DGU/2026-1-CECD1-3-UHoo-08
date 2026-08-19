// 화담 CARE — SHT31 온습도 읽기 + 절대습도 산출
// 배선: VIN→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21

#include <Wire.h>
#include "Adafruit_SHT31.h"

#define SDA_PIN 21
#define SCL_PIN 22
#define SHT31_ADDR 0x44

Adafruit_SHT31 sht31 = Adafruit_SHT31();

// 절대습도 [g/m³] — PSRI의 핵심 지표
// 상대습도는 온도에 따라 변해서 "공기가 실제로 얼마나 건조한가"를 못 나타낸다.
float absoluteHumidity(float t, float rh) {
  float es = 6.112 * exp(17.67 * t / (t + 243.5));   // 포화수증기압 [hPa]
  return 2.1674 * es * rh / (273.15 + t);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.println("=== HwaDam CARE SHT31 ===");

  if (!sht31.begin(SHT31_ADDR)) {
    Serial.println("SHT31 초기화 실패. 주소/배선 확인.");
    while (1) delay(1000);
  }

  // 내장 히터는 결로 제거용. 켜면 측정값이 왜곡되므로 반드시 OFF.
  sht31.heater(false);
  Serial.printf("OK. heater=%s\n\n", sht31.isHeaterEnabled() ? "ON" : "OFF");
  Serial.println("temp[C]\thumid[%]\tAH[g/m3]");
}

void loop() {
  float t = sht31.readTemperature();
  float h = sht31.readHumidity();

  if (isnan(t) || isnan(h)) {
    Serial.println("read failed");
  } else {
    Serial.printf("%.2f\t%.2f\t\t%.2f\n", t, h, absoluteHumidity(t, h));
  }

  delay(2000);
}