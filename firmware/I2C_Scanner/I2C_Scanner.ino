// 화담 CARE — I2C 주소 스캐너
// 배선: 센서 VCC→3V3, GND→GND, SDA→GPIO21, SCL→GPIO22

#include <Wire.h>

#define SDA_PIN 21
#define SCL_PIN 22

void setup() {
  Serial.begin(115200);
  delay(1500);                      // 시리얼 모니터 연결 대기
  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.println();
  Serial.println("=== HwaDam CARE I2C Scanner ===");
  Serial.printf("SDA=GPIO%d  SCL=GPIO%d\n\n", SDA_PIN, SCL_PIN);
}

void loop() {
  Serial.println("Scanning 0x01 ~ 0x7E ...");
  byte found = 0;

  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte err = Wire.endTransmission();

    if (err == 0) {
      Serial.printf("  0x%02X  ", addr);
      switch (addr) {
        case 0x44: Serial.print("<- SHT31  (temp/humidity)"); break;
        case 0x45: Serial.print("<- SHT31  (ADDR pin HIGH)"); break;
        case 0x76: Serial.print("<- BME688 (gas)");           break;
        case 0x77: Serial.print("<- BME688 (alt address)");   break;
        case 0x39: Serial.print("<- AS7341 (spectral)");      break;
        default:   Serial.print("<- unknown");                break;
      }
      Serial.println();
      found++;
    } else if (err == 4) {
      Serial.printf("  0x%02X  !! bus error\n", addr);
    }
  }

  if (found == 0) {
    Serial.println("  (none) -- check VCC / GND / SDA / SCL wiring");
  }
  Serial.printf("Done. %d device(s) found.\n\n", found);

  delay(3000);
}