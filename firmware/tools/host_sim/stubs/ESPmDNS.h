#pragma once
struct MDNSC { bool begin(const char*) { return true; } void addService(const char*, const char*, int) {} };
extern MDNSC MDNS;
