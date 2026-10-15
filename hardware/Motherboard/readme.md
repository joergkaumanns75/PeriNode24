# PeriNode24 – Motherboard

KiCad-Projekt der PeriNode24-Hauptplatine (ESP32-S3, RFM69HW, 24 Zündkanäle).

| Datei | Inhalt |
|---|---|
| `PeriNode24.kicad_pro` | KiCad-Projekt (hiermit öffnen) |
| `PeriNode24.kicad_sch` | Schaltplan |
| `PeriNode24.kicad_pcb` | Platinenlayout |
| `PeriNode24.pdf` | Schaltplan als PDF |
| `fabrication-toolkit-options.json` | Einstellungen für das Fabrication-Toolkit-Plugin (JLCPCB) |

Verwendet nur KiCad-Standardbibliotheken sowie die Espressif-Bibliothek (Plugin- und Content-Manager).
Lokale Dateien wie `*.kicad_prl`, `fp-info-cache`, Backups und Freerouting-Dateien werden über `hardware/.gitignore` ausgeschlossen.
