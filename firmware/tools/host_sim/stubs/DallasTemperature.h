#pragma once
#include <OneWire.h>
typedef uint8_t DeviceAddress[8];
#define DEVICE_DISCONNECTED_C -127
class DallasTemperature {
 public:
  DallasTemperature(OneWire*) {}
  void begin() {}
  uint8_t getDeviceCount();
  bool getAddress(uint8_t* a, uint8_t i) { memset(a, 0, 8); a[0] = 0x28; a[7] = i; return true; }
  void setWaitForConversion(bool) {}
  void requestTemperatures() {}
  float getTempC(const uint8_t* a) { return getTempCByIndex(a[7]); }
  float getTempCByIndex(uint8_t i);
};
