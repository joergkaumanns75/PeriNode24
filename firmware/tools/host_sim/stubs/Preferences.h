#pragma once
#include <Arduino.h>
#include <map>
#include <vector>
class Preferences {
  static std::map<std::string, std::vector<uint8_t>>& store() { static std::map<std::string, std::vector<uint8_t>> m; return m; }
 public:
  bool begin(const char*, bool) { return true; }
  void end() {}
  size_t getBytesLength(const char* k) { return store().count(k) ? store()[k].size() : 0; }
  size_t getBytes(const char* k, void* b, size_t n) { auto& v = store()[k]; memcpy(b, v.data(), std::min(n, v.size())); return v.size(); }
  size_t putBytes(const char* k, const void* b, size_t n) { store()[k].assign((const uint8_t*)b, (const uint8_t*)b + n); return n; }
  String getString(const char* k, const char* d) { return store().count(k) ? String(std::string(store()[k].begin(), store()[k].end())) : String(d); }
  size_t putString(const char* k, const String& s) { store()[k].assign(s.c_str(), s.c_str() + s.length()); return s.length(); }
};
