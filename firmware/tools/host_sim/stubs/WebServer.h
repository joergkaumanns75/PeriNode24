#pragma once
#include <Arduino.h>
#include <map>
#include <vector>
enum HTTPMethod { HTTP_ANY, HTTP_GET, HTTP_POST };
class WebServer {
 public:
  struct Route { std::string path; HTTPMethod m; std::function<void()> fn; };
  std::vector<Route> routes; std::function<void()> nf;
  std::map<std::string, std::string> args;
  int code = 0; std::string type, body;
  WebServer(int) {}
  void on(const char* p, HTTPMethod m, std::function<void()> fn) { routes.push_back({p, m, fn}); }
  void onNotFound(std::function<void()> fn) { nf = fn; }
  void begin() {}
  void handleClient() {}
  bool hasArg(const char* n) { return args.count(n); }
  String arg(const char* n) { auto it = args.find(n); return it == args.end() ? String("") : String(it->second); }
  void send(int c, const char* t, const String& b) { code = c; type = t; body = b.c_str(); }
  void send(int c, const char* t, const char* b) { code = c; type = t; body = b; }
  // Testhilfe: Anfrage ausführen
  int request(HTTPMethod m, const std::string& p, std::map<std::string, std::string> a = {}) {
    args = a; code = 0;
    for (auto& r : routes) if (r.path == p && r.m == m) { r.fn(); return code; }
    nf(); return code;
  }
};
