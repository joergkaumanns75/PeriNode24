#pragma once
#include <Arduino.h>
typedef enum { WIFI_OFF, WIFI_STA, WIFI_AP, WIFI_AP_STA } wifi_mode_t;
enum { WL_IDLE_STATUS = 0, WL_CONNECTED = 3, WL_DISCONNECTED = 6 };
struct IPAddress { String toString() const { return String("192.168.4.1"); } };
struct WiFiC {
  bool setHostname(const char*) { return true; }
  bool mode(wifi_mode_t) { return true; }
  int begin(const char*, const char*) { return 0; }
  int status() { return WL_DISCONNECTED; }
  IPAddress localIP() { return {}; }
  bool softAP(const char*, const char*) { return true; }
  IPAddress softAPIP() { return {}; }
  int RSSI() { return 0; }
};
extern WiFiC WiFi;
