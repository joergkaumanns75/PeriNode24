# PeriCharger – Ladegerät für 6 × 12 V / 2,4 Ah Blei-Gel (Perinode24)

Sechs unabhängige Ladekanäle (IUoU: Konstantstrom 0,6 A → 14,4 V → Erhaltung 13,65 V, temperaturkompensiert),
gesteuert von einem ESP32-S3 mit Weboberfläche. Versorgung: 24 V DC oder 230/240 V AC über ein Netzteil (Mean Well LRS-100-24).

| Ordner | Inhalt |
|---|---|
| [`kicad/`](kicad/) | KiCad-Projekt (`perinode24.kicad_pro`): Schaltplan (7 Blätter), 4-lagige Leiterplatte, JLCPCB-Stückliste mit LCSC-Nummern, Generator-Werkzeuge – siehe [kicad/README.md](kicad/README.md) |
| [`firmware/`](firmware/) | PlatformIO-Projekt für den ESP32-S3 (Arduino-Core 3.x): Ladesteuerung, WLAN, Weboberfläche, Host-Simulation – siehe [firmware/README.md](firmware/README.md) |

**Stand Leiterplatte:** geroutet und DRC-sauber. Noch sind 6 kurze Signalverbindungen an den Spannungsreglern von Hand zu ziehen (Liste in kicad/README.md).
Die Firmware ist auf dem PC simuliert und getestet, aber noch nicht auf echter Hardware.
