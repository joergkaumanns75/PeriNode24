/*
  Perinode24 – 6-Kanal-Ladegerät für 12 V / 2,4 Ah Blei-Gel/AGM (VRLA) mit Weboberfläche
  MCU : ESP32-S3-WROOM-1-N8R8, PlatformIO + Arduino-ESP32 Core 3.x (pioarduino), siehe platformio.ini
  Libs: OneWire, DallasTemperature (lib_deps); WiFi/WebServer/Preferences sind im Core
  Schaltplan: ../kicad/perinode24.kicad_pro (GPIO-Belegung und Teilerwerte passen zu dieser Firmware)

  Ladeverfahren IUoU: (Vorladen) -> Konstantstrom -> Konstantspannung -> Erhaltungsladung.
  Die Hardware regelt CC/CV selbst (TPS54160A + analoger Stromregler); die Firmware setzt
  Sollwerte, gleicht die Spannung über den INA226 fein ab und führt die Ladephasen.

  Weboberfläche: http://perinode24.local  bzw.  http://192.168.4.1 im Access-Point-Modus
  Ohne gespeichertes WLAN (oder wenn die Verbindung scheitert) öffnet der Lader den
  Access Point "Perinode24-Lader" mit dem Admin-Passwort (Werkseinstellung: perinode24).
*/
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_task_wdt.h>
#include <math.h>
#include "webui.h"

constexpr int N = 6;
#define FW_VERSION "2.0"

// ---------------- Pins (ESP32-S3-WROOM-1) ----------------
constexpr int PIN_SDA = 8, PIN_SCL = 9, PIN_1WIRE = 10, PIN_VBUS = 1;
constexpr int PIN_VSET[N] = {4, 5, 6, 7, 15, 16};      // LEDC-PWM  -> RC -> 330k -> FB
constexpr int PIN_ISET[N] = {17, 18, 21, 38, 39, 40};  // Sigma-Delta -> RC -> Stromregler
constexpr int PIN_EN[N]   = {11, 12, 13, 14, 41, 42};  // -> 10k -> EN TPS54160A (+ INA226-ALERT)
constexpr uint8_t INA_ADDR[N] = {0x40, 0x41, 0x42, 0x43, 0x44, 0x45};

// ---------------- Hardwarekonstanten ----------------
constexpr float R_SHUNT     = 0.050f;
constexpr float ISENSE_GAIN = 50.0f * R_SHUNT;   // INA181A2: 2,5 V/A
constexpr float VOUT0 = 14.83f, K_VSET = 0.588f; // Uout = VOUT0 - K * Uvset (Teiler 200k/11,8k, 330k)
constexpr float VIO   = 3.30f;
constexpr uint16_t INA_CFG = 0x4927;             // 16x Mittelung, 1,1 ms, kontinuierlich
constexpr float V_HW_LIMIT = 15.0f;              // INA226-ALERT (Bus-Überspannung)

// ---------------- Feste Grenzen ----------------
constexpr float V_PRESENT = 2.0f, V_DEEP = 10.5f, V_PRE_END = 11.5f, V_REST_LOW = 12.4f;
constexpr float T_MIN = 0.0f;
constexpr uint32_t MIN_ = 60000UL, HOUR = 60 * MIN_;
constexpr uint32_t T_PRE_MAX = 2 * HOUR;

// ---------------- Einstellbare Parameter (NVS) ----------------
struct Params {
  uint16_t ver   = 2;
  float vAbs     = 14.40f;   // Ladeschlussspannung bei 20 °C
  float vFloat   = 13.65f;   // Erhaltungsspannung bei 20 °C
  float tk       = -0.018f;  // V/K je 12-V-Block
  float iBulk    = 0.60f;    // Konstantstrom
  float iPre     = 0.24f;    // Vorladestrom (Tiefentladung)
  float iTerm    = 0.072f;   // Umschaltung auf Erhaltung
  float iRebulk  = 0.30f;    // Nachladen, wenn Erhaltungsstrom 60 s darüber
  float tMax     = 45.0f;    // °C
  float hAbsMax  = 4.0f;     // h Konstantspannungsphase
  float hChgMax  = 10.0f;    // h gesamt
  uint8_t enMask = 0x3F;     // Kanal aktiv (Bit 0 = Kanal 1)
} par;

Preferences prefs;
String wifiSsid, wifiPass, adminPw;

static bool validParams(const Params& p) {
  return p.vAbs >= 13.8f && p.vAbs <= 14.8f && p.vFloat >= 13.2f && p.vFloat <= 13.9f &&
         p.vFloat < p.vAbs && p.tk >= -0.03f && p.tk <= 0.0f &&
         p.iBulk >= 0.10f && p.iBulk <= 0.72f && p.iPre >= 0.05f && p.iPre <= p.iBulk &&
         p.iTerm >= 0.02f && p.iTerm <= 0.30f && p.iRebulk > p.iTerm && p.iRebulk <= p.iBulk &&
         p.tMax >= 30.0f && p.tMax <= 50.0f && p.hAbsMax >= 1.0f && p.hAbsMax <= 8.0f &&
         p.hChgMax >= 4.0f && p.hChgMax <= 16.0f;
}
static void loadSettings() {
  prefs.begin("p24", true);
  Params p;
  if (prefs.getBytesLength("par") == sizeof(Params)) prefs.getBytes("par", &p, sizeof(Params));
  if (p.ver == 2 && validParams(p)) par = p;
  wifiSsid = prefs.getString("ssid", "");
  wifiPass = prefs.getString("pass", "");
  adminPw  = prefs.getString("apw", "perinode24");
  prefs.end();
}
static void saveParams() {
  prefs.begin("p24", false); prefs.putBytes("par", &par, sizeof(Params)); prefs.end();
}

// ---------------- Temperatur ----------------
OneWire ow(PIN_1WIRE);
DallasTemperature ds(&ow);
// ROM-Codes je Kanal eintragen (werden beim Start seriell ausgegeben). Alle 0 -> Busreihenfolge.
DeviceAddress SENSOR[N] = {};

// ---------------- Kanalzustand ----------------
enum St : uint8_t { NO_BAT, PRE, BULK, ABSORB, FLOAT_, PAUSE, FAULT, OFF };
const char* ST_NAME[] = {"kein Akku", "Vorladen", "Konstantstrom", "Konstantspannung",
                         "Erhaltung", "Pruefpause", "Fehler", "Aus"};
struct Ch {
  St st = NO_BAT;
  float v = 0, i = 0, t = NAN, trim = 0, vcmd = 0, vTarget = 0, ah = 0;
  bool inaOk = false, alert = false, on = false;
  uint32_t tState = 0, tCycle = 0, tA = 0;
  const char* err = "";
} ch[N];

// Verlauf: alle 30 s ein Wert, 240 Werte = 2 h
constexpr int HIST = 240;
constexpr uint32_t HIST_MS = 30000;
struct Hist { uint16_t mv[HIST]; int16_t ma[HIST]; } hist[N];
int histHead = 0, histCount = 0;

static void go(Ch& c, St s) { c.st = s; c.tState = millis(); c.tA = 0; }
static void fault(Ch& c, const char* e) { go(c, FAULT); c.err = e; }
static bool held(bool cond, uint32_t& t0, uint32_t ms) {   // Bedingung ms lang stabil?
  uint32_t n = millis();
  if (!cond) { t0 = 0; return false; }
  if (!t0) t0 = n ? n : 1;                 // 0 = "nicht gestartet"
  return (int32_t)(n - t0) >= (int32_t)ms;  // vorzeichenbehaftet: kein Überlauf bei t0 = n+1
}

// ---------------- INA226 ----------------
static bool inaWrite(uint8_t a, uint8_t r, uint16_t v) {
  Wire.beginTransmission(a); Wire.write(r); Wire.write(v >> 8); Wire.write(v & 0xFF);
  return Wire.endTransmission() == 0;
}
static bool inaRead(uint8_t a, uint8_t r, int16_t& out) {
  Wire.beginTransmission(a); Wire.write(r);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(a, (uint8_t)2) != 2) return false;
  int hi = Wire.read(), lo = Wire.read();
  out = (int16_t)((hi << 8) | lo);
  return true;
}
static bool inaInit(uint8_t a) {
  return inaWrite(a, 0x00, INA_CFG)
      && inaWrite(a, 0x07, (uint16_t)(V_HW_LIMIT / 1.25e-3f))  // Alert-Grenze Busspannung
      && inaWrite(a, 0x06, 0x1001);                             // BOL + Latch, ALERT low-aktiv
}
static void measure(int k) {
  Ch& c = ch[k]; uint8_t a = INA_ADDR[k]; int16_t cfg, sh, bus, me;
  if (!inaRead(a, 0x00, cfg) || (uint16_t)cfg != INA_CFG) {   // Reset/Ausfall -> neu konfigurieren
    if (!inaInit(a)) { c.inaOk = false; return; }
  }
  c.inaOk = inaRead(a, 0x01, sh) && inaRead(a, 0x02, bus) && inaRead(a, 0x06, me);
  if (!c.inaOk) return;
  c.i = sh * 2.5e-6f / R_SHUNT;
  c.v = (uint16_t)bus * 1.25e-3f;
  c.alert = me & 0x0010;          // AFF (Lesen quittiert den Latch)
}

// ---------------- Temperaturen ----------------
static bool addrSet(const DeviceAddress a) { for (int i = 0; i < 8; i++) if (a[i]) return true; return false; }
static void readTemps(bool force) {
  static uint32_t last = 0;
  if (!force && millis() - last < 2000) return;
  last = millis();
  for (int k = 0; k < N; k++) {
    float t = addrSet(SENSOR[k]) ? ds.getTempC(SENSOR[k]) : ds.getTempCByIndex(k);
    ch[k].t = (t < -55.0f) ? NAN : t;     // -127 = Sensor fehlt
  }
  ds.requestTemperatures();               // asynchron, Ergebnis beim nächsten Aufruf
}

// ---------------- Ausgang ansteuern ----------------
static void drive(int k, bool en, float vt = 0, float is = 0) {
  Ch& c = ch[k];
  c.vTarget = en ? vt : 0;
  if (!en) {
    c.on = false;
    digitalWrite(PIN_EN[k], LOW);
    ledcWrite(PIN_VSET[k], 4095);          // kleinste Spannung
    sigmaDeltaWrite(PIN_ISET[k], 0);       // Strom-Soll 0
    return;
  }
  // Feinabgleich nur im CV-Bereich nach dem Hochlaufen (kein Windup in CC-Phase)
  if (c.on && fabsf(c.vcmd - vt) < 0.01f && c.i < 0.85f * is && millis() - c.tState > 5000)
    c.trim = constrain(c.trim + 0.02f * (vt - c.v), -0.30f, 0.30f);
  // Sanftanlauf: Sollwert startet knapp über der Akkuspannung und steigt mit max. 1 V/s
  if (!c.on) { c.vcmd = fminf(c.v + 0.10f, vt); c.on = true; }
  c.vcmd += constrain(vt - c.vcmd, -0.50f, 0.20f);   // je 200-ms-Zyklus
  float vdac = (VOUT0 - (c.vcmd + c.trim)) / K_VSET;
  ledcWrite(PIN_VSET[k], (uint32_t)constrain(lroundf(vdac / VIO * 4095.0f), 0L, 4095L));
  sigmaDeltaWrite(PIN_ISET[k], (uint8_t)constrain(lroundf(is * ISENSE_GAIN / VIO * 255.0f), 0L, 255L));
  digitalWrite(PIN_EN[k], HIGH);
}

// ---------------- Zustandsautomat je Kanal ----------------
static void step(int k, bool busOk) {
  Ch& c = ch[k];
  uint32_t now = millis(), ts = now - c.tState;
  float tc   = isnan(c.t) ? 20.0f : constrain(c.t, 0.0f, 40.0f);
  float vAbs = par.vAbs + par.tk * (tc - 20.0f);
  float vFl  = par.vFloat + par.tk * (tc - 20.0f);
  bool active = c.st == PRE || c.st == BULK || c.st == ABSORB || c.st == FLOAT_;

  if (!(par.enMask & (1 << k))) { drive(k, false); if (c.st != OFF) { go(c, OFF); c.err = ""; } return; }
  if (c.st == OFF) go(c, NO_BAT);

  if (!c.inaOk) { drive(k, false); if (c.st != FAULT) fault(c, "Messung (INA226)"); return; }
  if (active) {
    if (c.alert)                 fault(c, "HW-Ueberspannung (INA226-ALERT)");
    else if (isnan(c.t))         fault(c, "Temperatursensor fehlt");
    else if (c.t > par.tMax)     fault(c, "Uebertemperatur");
    else if (c.v > vAbs + 0.4f)  fault(c, "Ueberspannung");
  }
  if (!busOk && c.st != FAULT) { drive(k, false); return; }   // Versorgung ausserhalb 18..33 V

  if (active && c.i > 0) c.ah += c.i * 0.2f / 3600.0f;       // 200-ms-Zyklus

  switch (c.st) {
    case NO_BAT:
      drive(k, false); c.trim = 0;
      if (held(c.v > V_PRESENT && !isnan(c.t) && c.t >= T_MIN && c.t <= par.tMax, c.tA, 3000)) {
        c.tCycle = now; c.ah = 0; go(c, c.v < V_DEEP ? PRE : BULK);
      }
      break;
    case PRE:
      drive(k, true, vAbs, par.iPre);
      if (held(c.v > V_PRE_END, c.tA, 30000)) go(c, BULK);
      else if (ts > T_PRE_MAX) fault(c, "Tiefentladen/defekt");
      break;
    case BULK:
      drive(k, true, vAbs, par.iBulk);
      if (held(c.v >= vAbs - 0.05f, c.tA, 10000)) go(c, ABSORB);
      else if (now - c.tCycle > (uint32_t)(par.hChgMax * HOUR)) fault(c, "Ladezeit ueberschritten");
      break;
    case ABSORB:
      drive(k, true, vAbs, par.iBulk);
      if (held(c.i < par.iTerm, c.tA, 10 * MIN_)) go(c, FLOAT_);
      else if (ts > (uint32_t)(par.hAbsMax * HOUR)) {
        if (c.i > 0.10f) fault(c, "Strom sinkt nicht (Zellschluss?)");
        else go(c, FLOAT_);
      }
      break;
    case FLOAT_:
      drive(k, true, vFl, par.iBulk);
      if (held(c.i > par.iRebulk, c.tA, MIN_)) { c.tCycle = now; c.ah = 0; go(c, BULK); }  // Last hat entladen
      else if (ts > 10 * MIN_) go(c, PAUSE);
      break;
    case PAUSE:                       // Lader 8 s aus: Akku noch vorhanden / Ruhespannung ok?
      drive(k, false);
      if (ts > 8000) {
        if (c.v < 5.0f) go(c, NO_BAT);
        else if (c.v < V_REST_LOW) { c.tCycle = now; c.ah = 0; go(c, BULK); }
        else go(c, FLOAT_);
      }
      break;
    case FAULT:                       // Quittierung: Akku abklemmen oder Weboberfläche/Serial
      drive(k, false);
      if (held(c.v < 1.0f, c.tA, 5000)) { c.err = ""; go(c, NO_BAT); }
      break;
    case OFF:
      break;
  }
}

static void resetFault(int k) { if (ch[k].st == FAULT) { ch[k].err = ""; go(ch[k], NO_BAT); } }

// ---------------- WLAN ----------------
WebServer server(80);
float vbusNow = 0;
bool apActive = false, mdnsStarted = false;
uint32_t wifiStart = 0;

static void startAP() {
  if (apActive) return;
  WiFi.mode(wifiSsid.length() ? WIFI_AP_STA : WIFI_AP);
  String pw = adminPw.length() >= 8 ? adminPw : String("perinode24");
  WiFi.softAP("Perinode24-Lader", pw.c_str());
  apActive = true;
  Serial.printf("Access Point 'Perinode24-Lader' aktiv, http://%s\n", WiFi.softAPIP().toString().c_str());
}
static void startWifi() {
  WiFi.setHostname("perinode24");
  if (wifiSsid.length()) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
    wifiStart = millis();
  } else {
    startAP();
  }
}
static void wifiTask() {
  bool sta = WiFi.status() == WL_CONNECTED;
  if (wifiSsid.length() && !sta && !apActive && millis() - wifiStart > 20000) startAP();  // Fallback
  if ((sta || apActive) && !mdnsStarted) {
    if (MDNS.begin("perinode24")) { MDNS.addService("http", "tcp", 80); mdnsStarted = true; }
    if (sta) Serial.printf("WLAN verbunden: http://%s  (perinode24.local)\n", WiFi.localIP().toString().c_str());
  }
}

// ---------------- Webserver ----------------
static String jsonEsc(const String& s) {
  String o; o.reserve(s.length() + 4);
  for (size_t i = 0; i < s.length(); i++) {
    char ch_ = s[i];
    if (ch_ == '"' || ch_ == '\\') { o += '\\'; o += ch_; }
    else if ((uint8_t)ch_ < 0x20) o += ' ';
    else o += ch_;
  }
  return o;
}
static void fnum(String& s, float v, int dec) {
  char b[24];
  if (isnan(v)) s += "null"; else { snprintf(b, sizeof(b), "%.*f", dec, v); s += b; }
}
static bool authOk() {
  if (server.arg("pw") == adminPw) return true;
  server.send(403, "application/json", "{\"ok\":false,\"msg\":\"Admin-Passwort falsch\"}");
  return false;
}
static void handleStatus() {
  String s; s.reserve(1800);
  bool sta = WiFi.status() == WL_CONNECTED;
  s += "{\"fw\":\"" FW_VERSION "\",\"up\":"; s += String(millis() / 1000);
  s += ",\"vbus\":"; fnum(s, vbusNow, 1);
  s += ",\"wifi\":{\"sta\":"; s += sta ? "true" : "false";
  s += ",\"ssid\":\""; s += jsonEsc(wifiSsid); s += "\",\"ip\":\"";
  s += sta ? WiFi.localIP().toString() : String(""); s += "\",\"rssi\":"; s += String(sta ? WiFi.RSSI() : 0);
  s += ",\"ap\":"; s += apActive ? "true" : "false"; s += "},\"ch\":[";
  for (int k = 0; k < N; k++) {
    Ch& c = ch[k];
    if (k) s += ",";
    s += "{\"st\":"; s += String((int)c.st);
    s += ",\"name\":\""; s += ST_NAME[c.st];
    s += "\",\"v\":"; fnum(s, c.v, 3);
    s += ",\"i\":"; fnum(s, c.i, 3);
    s += ",\"t\":"; fnum(s, c.t, 1);
    s += ",\"vt\":"; fnum(s, c.vTarget, 2);
    s += ",\"ah\":"; fnum(s, c.ah, 3);
    s += ",\"ts\":"; s += String((millis() - c.tState) / 1000);
    s += ",\"en\":"; s += (par.enMask & (1 << k)) ? "true" : "false";
    s += ",\"err\":\""; s += c.err; s += "\"}";
  }
  s += "]}";
  server.send(200, "application/json", s);
}
static void handleHistory() {
  int k = server.arg("ch").toInt();
  if (k < 0 || k >= N) k = 0;
  String s; s.reserve(histCount * 12 + 64);
  s += "{\"ch\":"; s += String(k); s += ",\"step\":"; s += String(HIST_MS / 1000); s += ",\"v\":[";
  int start = (histHead - histCount + HIST) % HIST;
  for (int j = 0; j < histCount; j++) { if (j) s += ","; s += String(hist[k].mv[(start + j) % HIST]); }
  s += "],\"i\":[";
  for (int j = 0; j < histCount; j++) { if (j) s += ","; s += String(hist[k].ma[(start + j) % HIST]); }
  s += "]}";
  server.send(200, "application/json", s);
}
static void sendParams() {
  String s; s.reserve(400);
  s += "{\"vAbs\":"; fnum(s, par.vAbs, 2);
  s += ",\"vFloat\":"; fnum(s, par.vFloat, 2);
  s += ",\"tk\":"; fnum(s, par.tk * 1000.0f, 1);
  s += ",\"iBulk\":"; fnum(s, par.iBulk, 3);
  s += ",\"iPre\":"; fnum(s, par.iPre, 3);
  s += ",\"iTerm\":"; fnum(s, par.iTerm, 3);
  s += ",\"iRebulk\":"; fnum(s, par.iRebulk, 3);
  s += ",\"tMax\":"; fnum(s, par.tMax, 1);
  s += ",\"hAbsMax\":"; fnum(s, par.hAbsMax, 1);
  s += ",\"hChgMax\":"; fnum(s, par.hChgMax, 1);
  s += ",\"ssid\":\""; s += jsonEsc(wifiSsid); s += "\"}";
  server.send(200, "application/json", s);
}
static void handleParamsPost() {
  if (!authOk()) return;
  Params p = par;
  auto rd = [](const char* n, float& dst, float scale = 1.0f) {
    if (server.hasArg(n)) dst = server.arg(n).toFloat() * scale;
  };
  rd("vAbs", p.vAbs); rd("vFloat", p.vFloat); rd("tk", p.tk, 0.001f);
  rd("iBulk", p.iBulk); rd("iPre", p.iPre); rd("iTerm", p.iTerm); rd("iRebulk", p.iRebulk);
  rd("tMax", p.tMax); rd("hAbsMax", p.hAbsMax); rd("hChgMax", p.hChgMax);
  if (!validParams(p)) {
    server.send(400, "application/json", "{\"ok\":false,\"msg\":\"Werte ausserhalb des zulaessigen Bereichs\"}");
    return;
  }
  par = p; saveParams();
  server.send(200, "application/json", "{\"ok\":true,\"msg\":\"Gespeichert\"}");
}
static void handleCmd() {
  if (!authOk()) return;
  String a = server.arg("action");
  String c = server.arg("ch");
  int from = 0, to = N - 1;
  if (c != "all") { from = to = c.toInt(); if (from < 0 || from >= N) { server.send(400, "application/json", "{\"ok\":false,\"msg\":\"Kanal?\"}"); return; } }
  for (int k = from; k <= to; k++) {
    if (a == "reset") resetFault(k);
    else if (a == "enable") par.enMask |= (1 << k);
    else if (a == "disable") par.enMask &= ~(1 << k);
    else { server.send(400, "application/json", "{\"ok\":false,\"msg\":\"Aktion?\"}"); return; }
  }
  if (a != "reset") saveParams();
  server.send(200, "application/json", "{\"ok\":true}");
}
static bool restartPending = false;
static uint32_t restartAt = 0;
static void handleWifi() {
  if (!authOk()) return;
  String ssid = server.arg("ssid"), pass = server.arg("pass"), npw = server.arg("newpw");
  if (npw.length() && npw.length() < 8) {
    server.send(400, "application/json", "{\"ok\":false,\"msg\":\"Neues Passwort: mind. 8 Zeichen\"}");
    return;
  }
  prefs.begin("p24", false);
  prefs.putString("ssid", ssid);
  if (pass.length() || !ssid.length()) prefs.putString("pass", pass);
  if (npw.length()) prefs.putString("apw", npw);
  prefs.end();
  server.send(200, "application/json", "{\"ok\":true,\"msg\":\"Gespeichert - Neustart in 2 s\"}");
  restartPending = true; restartAt = millis();
}
static void setupWeb() {
  server.on("/", HTTP_GET, []() { server.send(200, "text/html; charset=utf-8", INDEX_HTML); });
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/history", HTTP_GET, handleHistory);
  server.on("/api/params", HTTP_GET, sendParams);
  server.on("/api/params", HTTP_POST, handleParamsPost);
  server.on("/api/cmd", HTTP_POST, handleCmd);
  server.on("/api/wifi", HTTP_POST, handleWifi);
  server.onNotFound([]() { server.send(404, "text/plain", "nicht gefunden"); });
  server.begin();
}

static void recordHistory() {
  static uint32_t last = 0;
  if (millis() - last < HIST_MS && histCount) return;
  last = millis();
  for (int k = 0; k < N; k++) {
    hist[k].mv[histHead] = (uint16_t)constrain(lroundf(ch[k].v * 1000.0f), 0L, 65535L);
    hist[k].ma[histHead] = (int16_t)constrain(lroundf(ch[k].i * 1000.0f), -32768L, 32767L);
  }
  histHead = (histHead + 1) % HIST;
  if (histCount < HIST) histCount++;
}

static void report(float vbus) {
  Serial.printf("\nVBUS %.1f V\n", vbus);
  for (int k = 0; k < N; k++) {
    Ch& c = ch[k];
    Serial.printf(" K%d %-16s U=%6.3f V  I=%6.3f A  T=%5.1f C  %.3f Ah  %s\n",
                  k + 1, ST_NAME[c.st], c.v, c.i, c.t, c.ah, c.err);
  }
}

void setup() {
  for (int k = 0; k < N; k++) {        // zuerst alles sicher aus
    pinMode(PIN_EN[k], OUTPUT); digitalWrite(PIN_EN[k], LOW);
    ledcAttach(PIN_VSET[k], 19531, 12); ledcWrite(PIN_VSET[k], 4095);
    sigmaDeltaAttach(PIN_ISET[k], 312500); sigmaDeltaWrite(PIN_ISET[k], 0);
  }
  Serial.begin(115200);
  analogReadResolution(12);
  loadSettings();
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  for (int k = 0; k < N; k++) { ch[k].inaOk = inaInit(INA_ADDR[k]); go(ch[k], NO_BAT); }

  ds.begin();
  DeviceAddress a;
  for (int i = 0; i < ds.getDeviceCount(); i++) if (ds.getAddress(a, i)) {
    Serial.printf("DS18B20 #%d: ", i);
    for (int j = 0; j < 8; j++) Serial.printf("0x%02X%s", a[j], j < 7 ? "," : "\n");
  }
  ds.setWaitForConversion(true);  ds.requestTemperatures();   // erste Messung blockierend
  ds.setWaitForConversion(false); readTemps(true);

  startWifi();
  setupWeb();

  esp_task_wdt_config_t wdt = {.timeout_ms = 3000, .idle_core_mask = 0, .trigger_panic = true};
  esp_task_wdt_reconfigure(&wdt);
  esp_task_wdt_add(NULL);
}

void loop() {
  static uint32_t last = 0, lastRep = 0;
  server.handleClient();
  wifiTask();
  if (restartPending && millis() - restartAt > 2000) ESP.restart();
  if (Serial.available() && Serial.read() == 'r')
    for (int k = 0; k < N; k++) resetFault(k);
  if (millis() - last < 200) return;
  last = millis();
  esp_task_wdt_reset();

  readTemps(false);
  vbusNow = analogReadMilliVolts(PIN_VBUS) * 11.0f / 1000.0f;   // Teiler 100k/10k
  bool busOk = vbusNow > 18.0f && vbusNow < 33.0f;
  for (int k = 0; k < N; k++) { measure(k); step(k, busOk); }
  recordHistory();
  if (millis() - lastRep > 2000) { lastRep = millis(); report(vbusNow); }
}
