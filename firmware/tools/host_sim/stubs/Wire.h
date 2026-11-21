#pragma once
#include <Arduino.h>
class TwoWire {
 public:
  bool begin(int sda, int scl, uint32_t f);
  void beginTransmission(uint8_t a);
  size_t write(uint8_t b);
  uint8_t endTransmission(bool stop = true);
  uint8_t requestFrom(uint8_t a, uint8_t n);
  int read();
};
extern TwoWire Wire;
