// Minimale Nachbildung der Arduino-ESP32-API für den Host-Test (nur was der Sketch nutzt)
#pragma once
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <string>
#include <functional>
#include <algorithm>
typedef uint8_t byte;
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
uint32_t millis();
void pinMode(int, int);
void digitalWrite(int, int);
bool ledcAttach(uint8_t pin, uint32_t freq, uint8_t res);
bool ledcWrite(uint8_t pin, uint32_t duty);
bool sigmaDeltaAttach(uint8_t pin, uint32_t freq);
bool sigmaDeltaWrite(uint8_t pin, uint8_t duty);
void analogReadResolution(int);
uint32_t analogReadMilliVolts(uint8_t pin);
class String {
  std::string s;
 public:
  String() {}
  String(const char* c) : s(c ? c : "") {}
  String(const std::string& x) : s(x) {}
  explicit String(int v) : s(std::to_string(v)) {}
  explicit String(unsigned v) : s(std::to_string(v)) {}
  explicit String(long v) : s(std::to_string(v)) {}
  explicit String(unsigned long v) : s(std::to_string(v)) {}
  String& operator+=(const String& o) { s += o.s; return *this; }
  String& operator+=(const char* o) { s += o; return *this; }
  String& operator+=(char c) { s += c; return *this; }
  size_t length() const { return s.size(); }
  char operator[](size_t i) const { return s[i]; }
  const char* c_str() const { return s.c_str(); }
  void reserve(size_t n) { s.reserve(n); }
  int toInt() const { return atoi(s.c_str()); }
  float toFloat() const { return (float)atof(s.c_str()); }
  bool operator==(const String& o) const { return s == o.s; }
  bool operator==(const char* o) const { return s == o; }
  bool operator!=(const char* o) const { return s != o; }
};
struct SerialC {
  void begin(int) {}
  int available() { return 0; }
  int read() { return -1; }
  int printf(const char* f, ...) __attribute__((format(printf, 2, 3)));
};
extern SerialC Serial;
struct EspC { void restart(); };
extern EspC ESP;
