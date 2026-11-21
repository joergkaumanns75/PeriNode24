// Host-Simulation: kompiliert den unveränderten Sketch gegen nachgebildete Arduino-APIs und
// simuliert 6 Akkus + Ladehardware (TPS54160A-CC/CV, INA226, DS18B20) im Zeitraffer.
//   aus firmware/: g++ -std=gnu++17 -O2 -Itools/host_sim/stubs -Iinclude -o sim tools/host_sim/sim.cpp && ./sim 12
#include <Arduino.h>
#include <cstdarg>
#include <map>
#include <vector>

static uint64_t simMs = 0;
uint32_t millis() { return (uint32_t)simMs; }
SerialC Serial;
static bool quiet = true;
int SerialC::printf(const char* f, ...) {
  if (quiet) return 0;
  va_list a; va_start(a, f); int r = vprintf(f, a); va_end(a); return r;
}
EspC ESP;
void EspC::restart() { ::printf("[ESP.restart]\n"); }
#include <WiFi.h>
#include <ESPmDNS.h>
WiFiC WiFi;
MDNSC MDNS;

// ---------------- Sketch (unverändert) ----------------
#include "../../src/main.cpp"

// ---------------- Hardware-Modell ----------------
static std::map<int, int> pinLevel;
static std::map<int, uint32_t> ledc, sdm;
void pinMode(int, int) {}
void digitalWrite(int p, int v) { pinLevel[p] = v; }
bool ledcAttach(uint8_t, uint32_t, uint8_t) { return true; }
bool ledcWrite(uint8_t p, uint32_t d) { ledc[p] = d; return true; }
bool sigmaDeltaAttach(uint8_t, uint32_t) { return true; }
bool sigmaDeltaWrite(uint8_t p, uint8_t d) { sdm[p] = d; return true; }
void analogReadResolution(int) {}
uint32_t analogReadMilliVolts(uint8_t) { return 24000 / 11; }   // 24-V-Bus

struct Batt {
  const char* name;
  bool present; float soc; bool shorted; bool deep; bool sensor;
  float q = 0;            // geladene Ah seit Start
  float v = 0, i = 0;     // Klemmenspannung, Ladestrom (aus Sicht Lader)
  float load = 0;         // Entladestrom
  bool alertLatched = false;
  uint16_t cfg = 0x4127;
};
static Batt bat[6] = {
  {"normal 30%",      true, 0.30f, false, false, true},
  {"tiefentladen",    true, 0.02f, false, true,  true},
  {"voll",            true, 1.00f, false, false, true},
  {"Zellschluss",     true, 0.50f, true,  false, true},
  {"kein Akku",       false, 0.0f, false, false, false},
  {"Last nach 8 h",   true, 0.50f, false, false, true},
};
// Hardware weicht absichtlich von den Nennwerten ab -> Feinabgleich muss das ausregeln
constexpr float HW_VOUT0 = 14.86f, HW_K = 0.592f;

static float ocv(Batt& b) {
  if (b.shorted) return 10.0f + 0.67f * b.soc;                 // 5 Zellen
  float o = 12.0f + 0.8f * b.soc;
  if (b.deep) o -= 2.0f * expf(-b.q / 0.02f);                  // tiefentladen: erholt sich beim Laden
  return o;
}
static float rint(Batt& b) { return b.shorted ? 0.5f : 0.5f + 40.0f * powf(b.soc, 10); }

static void physics(int k, float dt) {
  Batt& b = bat[k];
  if (!b.present) { b.v = 0; b.i = 0; return; }
  bool en = pinLevel[PIN_EN[k]] && !b.alertLatched;
  float vdac = ledc[PIN_VSET[k]] / 4095.0f * 3.3f;
  float vset = HW_VOUT0 - HW_K * vdac;
  float iset = sdm[PIN_ISET[k]] / 255.0f * 3.3f / 2.5f;
  float o = ocv(b), r = rint(b);
  float ich = 0, ib;
  if (en) {
    ib = (vset - o) / r;                       // CV: Akkustrom
    ich = ib + b.load;
    if (ich > iset) { ich = iset; ib = iset - b.load; }
    if (ich < 0) { ich = 0; ib = -b.load; }    // Diode: Lader kann nicht senken
  } else ib = -b.load;
  float rr = ib >= 0 ? r : 0.3f;
  b.v = o + ib * rr;
  b.i = ich;
  float eta = ib > 0 ? 0.9f : 1.0f;
  b.soc = std::min(1.0f, std::max(0.0f, b.soc + ib * eta * dt / 3600.0f / 2.4f));
  if (ib > 0) b.q += ib * dt / 3600.0f;
  if (b.v > 15.0f) b.alertLatched = true;
}

// ---------------- I2C: INA226 ----------------
static int curAddr = -1, curReg = 0, wrCount = 0; static uint8_t wrBuf[3];
static std::vector<uint8_t> rdBuf; static size_t rdPos = 0;
TwoWire Wire;
bool TwoWire::begin(int, int, uint32_t) { return true; }
void TwoWire::beginTransmission(uint8_t a) { curAddr = a; wrCount = 0; }
size_t TwoWire::write(uint8_t b) { if (wrCount < 3) wrBuf[wrCount++] = b; return 1; }
static int chOf(int a) { return (a >= 0x40 && a <= 0x45) ? a - 0x40 : -1; }
uint8_t TwoWire::endTransmission(bool) {
  int k = chOf(curAddr); if (k < 0) return 2;
  curReg = wrBuf[0];
  if (wrCount == 3 && curReg == 0x00) bat[k].cfg = (wrBuf[1] << 8) | wrBuf[2];
  return 0;
}
uint8_t TwoWire::requestFrom(uint8_t a, uint8_t n) {
  int k = chOf(a); if (k < 0) return 0;
  Batt& b = bat[k]; uint16_t v = 0;
  switch (curReg) {
    case 0x00: v = b.cfg; break;
    case 0x01: v = (uint16_t)(int16_t)lroundf(b.i * 0.05f / 2.5e-6f); break;
    case 0x02: v = (uint16_t)lroundf(b.v / 1.25e-3f); break;
    case 0x06: v = b.alertLatched ? 0x0010 : 0; b.alertLatched = false; break;
  }
  rdBuf = {(uint8_t)(v >> 8), (uint8_t)v}; rdPos = 0; return n;
}
int TwoWire::read() { return rdPos < rdBuf.size() ? rdBuf[rdPos++] : -1; }

// ---------------- DS18B20 ----------------
uint8_t DallasTemperature::getDeviceCount() { int n = 0; for (auto& b : bat) n += b.sensor; return n; }
float DallasTemperature::getTempCByIndex(uint8_t i) { return (i < 6 && bat[i].sensor) ? 25.0f : DEVICE_DISCONNECTED_C; }


int main(int argc, char** argv) {
  double hours = argc > 1 ? atof(argv[1]) : 12.0;
  setup();
  int lastSt[6]; for (int k = 0; k < 6; k++) lastSt[k] = -1;
  const uint64_t end = (uint64_t)(hours * 3600e3);
  for (simMs = 1000; simMs < end; simMs += 50) {
    if (simMs % 200 == 0) for (int k = 0; k < 6; k++) physics(k, 0.2f);
    // Szenario Kanal 6: nach 8 h 40 min lang 1 A Last
    bat[5].load = (simMs > 8 * 3600e3 && simMs < 8 * 3600e3 + 40 * 60e3) ? 1.0f : 0.0f;
    loop();
    for (int k = 0; k < 6; k++) if (ch[k].st != lastSt[k]) {
      ::printf("%7.3f h  K%d %-14s -> %-16s U=%6.3f V I=%6.3f A SoC=%3.0f%% %.3f Ah %s\n", simMs / 3600e3, k + 1,
               bat[k].name, ST_NAME[ch[k].st], ch[k].v, ch[k].i, bat[k].soc * 100, ch[k].ah, ch[k].err);
      lastSt[k] = ch[k].st;
    }
  }
  ::printf("\nEndzustand nach %.1f h:\n", hours);
  for (int k = 0; k < 6; k++)
    ::printf("  K%d %-14s %-16s U=%6.3f V (Soll %.2f, Trim %+.3f) I=%6.3f A SoC=%3.0f%%\n", k + 1, bat[k].name,
             ST_NAME[ch[k].st], ch[k].v, ch[k].vTarget, ch[k].trim, ch[k].i, bat[k].soc * 100);

  // ---------------- Web-API ----------------
  FILE* f = fopen("api_out.txt", "w");
  auto dump = [&](const char* tag, int code) { fprintf(f, "### %s %d\n%s\n", tag, code, server.body.c_str()); };
  dump("GET /api/status", server.request(HTTP_GET, "/api/status"));
  dump("GET /api/history", server.request(HTTP_GET, "/api/history", {{"ch", "0"}}));
  dump("GET /api/params", server.request(HTTP_GET, "/api/params"));
  dump("POST /api/params falsches pw", server.request(HTTP_POST, "/api/params", {{"pw", "x"}, {"vAbs", "14.5"}}));
  dump("POST /api/params ungueltig", server.request(HTTP_POST, "/api/params", {{"pw", "perinode24"}, {"vAbs", "16"}}));
  dump("POST /api/params ok", server.request(HTTP_POST, "/api/params", {{"pw", "perinode24"}, {"vAbs", "14.5"}, {"tk", "-20"}}));
  dump("GET /api/params", server.request(HTTP_GET, "/api/params"));
  dump("POST /api/cmd disable 2", server.request(HTTP_POST, "/api/cmd", {{"pw", "perinode24"}, {"action", "disable"}, {"ch", "2"}}));
  for (int n = 0; n < 10; n++) { simMs += 200; loop(); }
  dump("GET /api/status", server.request(HTTP_GET, "/api/status"));
  dump("POST /api/cmd reset all", server.request(HTTP_POST, "/api/cmd", {{"pw", "perinode24"}, {"action", "reset"}, {"ch", "all"}}));
  dump("POST /api/wifi kurzes pw", server.request(HTTP_POST, "/api/wifi", {{"pw", "perinode24"}, {"ssid", "Heim\"netz"}, {"newpw", "123"}}));
  dump("GET /", server.request(HTTP_GET, "/"));
  fclose(f);
  ::printf("\nWeb-API-Antworten in api_out.txt\n");
}
