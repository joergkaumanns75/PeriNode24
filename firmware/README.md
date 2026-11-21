# Perinode24 Lader – Firmware (PlatformIO)

ESP32-S3-WROOM-1-N8R8, Arduino-Framework, Core 3.x (über die Plattform pioarduino).

## In VS Code öffnen
1. Die Erweiterung **PlatformIO IDE** installieren. VS Code schlägt sie beim Öffnen dieses Ordners automatisch vor.
2. Über *PlatformIO → Open Project* den Ordner `firmware/` öffnen.
3. **Build:** Häkchen in der Statusleiste bzw. `pio run`. Beim ersten Build lädt PlatformIO die Plattform, die Toolchain und die Bibliotheken OneWire und DallasTemperature. Das dauert einige Minuten.
4. **Upload** über USB-C (natives USB des ESP32-S3): Pfeil in der Statusleiste bzw. `pio run -t upload`.
   Bei einem fabrikneuen Chip oder wenn der Upload hängt: **BOOT** gedrückt halten, **RESET** kurz drücken, dann hochladen.
5. **Serieller Monitor:** Stecker-Symbol bzw. `pio device monitor`. Mit `r` werden alle Fehler quittiert.

## Projektstruktur
| Pfad | Inhalt |
|---|---|
| `platformio.ini` | Plattform, Board (8 MB Flash, Octal-PSRAM), USB-CDC, Bibliotheken |
| `src/main.cpp` | Ladesteuerung (IUoU), INA226, DS18B20, WLAN, Webserver |
| `include/webui.h` | Weboberfläche (eingebettet, ohne externe Ressourcen) |
| `tools/host_sim/` | Simulation von 6 Akkus und der Ladehardware auf dem PC |
| `tools/ui_mock.py` | Testserver für die Weboberfläche mit Beispieldaten |
| `docs/weboberflaeche.png` | Bildschirmfoto |

## Ohne Hardware testen (VS Code: *Terminal → Run Task*)
- **Host-Simulation:** kompiliert `src/main.cpp` unverändert mit g++ gegen nachgebildete Arduino-APIs und simuliert 12 h Laden im Zeitraffer. Szenarien: normal, tiefentladen, voll, Zellschluss, kein Akku, Lastentnahme. Unter Windows wird dafür g++ benötigt (MSYS2/MinGW) oder WSL.
- **Weboberfläche mit Testdaten:** startet `tools/ui_mock.py`, danach http://127.0.0.1:8765 öffnen. Passwort: `perinode24`.

## Erste Inbetriebnahme
- Nach dem Flashen öffnet der Lader den WLAN-Access-Point **Perinode24-Lader** (Passwort `perinode24`). Die Oberfläche liegt unter http://192.168.4.1.
- Unter *WLAN und Passwort* das Heimnetz eintragen und das **Admin-Passwort ändern**. Danach ist der Lader unter http://perinode24.local erreichbar.
- Die ROM-Codes der DS18B20 werden beim Start seriell ausgegeben. Für eine feste Zuordnung Sensor → Kanal trägt man sie in `SENSOR[]` in `src/main.cpp` ein. Ohne Eintrag gilt die Reihenfolge am Bus.
- Kalibrierung: `VOUT0` / `K_VSET` in `src/main.cpp` mit Multimeter-Messwerten abgleichen. Der automatische Feinabgleich deckt ±0,3 V ab.

## Hinweis zur Plattformversion
`platformio.ini` nutzt den Kanal `stable` von pioarduino. Für reproduzierbare Builds eine feste Version eintragen, siehe Kommentar in der Datei.
