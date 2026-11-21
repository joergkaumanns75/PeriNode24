# Perinode24 – KiCad-Projekt Ladegerät 6 × 12 V / 2,4 Ah

Öffnen: `perinode24.kicad_pro` (KiCad 7; KiCad 8/9 konvertiert beim Speichern).

| Datei | Inhalt |
|---|---|
| `perinode24.kicad_sch` | Hauptblatt (A2): 24-V-DC-Eingang und Netzteil-Eingang mit Ideal-Dioden-ODER (LM74700), 5 V (LMR16006), 3,3 V (TLV75733), ESP32-S3-WROOM-1-N8R8, USB-C, I²C/1-Wire/OLED |
| `kanal1…6.kicad_sch` | je ein Ladekanal (A3): TPS54160A, CC/CV-Sollwertsteuerung, INA226 + INA181, Verpolschutz, PTC, Akku- und Sensoranschluss |
| `perinode24.kicad_sym` | Projektsymbole: TPS54160A (MSOP-10 PowerPAD), N-MOSFET SO-8 |
| `bom_jlcpcb.csv` | Stückliste im JLCPCB-Format (Comment, Designator, Footprint, LCSC Part #) |
| `perinode24_schaltplan.pdf` | PDF-Export aller Blätter |
| `tools/gen_schematic.py` | Generator – Werte/LCSC-Nummern in der Tabelle `P` ändern und neu erzeugen |

Jedes Bauteil hat die Felder **LCSC** und **MPN**. Diese Felder werden von JLCPCB-Exporttools übernommen, zum Beispiel vom Plugin „Fabrication Toolkit“ oder von „kicad-jlcpcb-tools“.

## Vor der Bestellung prüfen

- **C106/C206/… 47 pF (C1671):** Diese LCSC-Nummer ist nicht verifiziert. Alle anderen Nummern wurden im LCSC/JLCPCB-Katalog nachgeschlagen. Lagerbestand und die Einstufung Basic/Extended ändern sich laufend.
- **Alles SMD:** Stecker sind JST PH SMD.
  - J1/J2 (24 V): S6B-PH-SM4-TB, je 3 Pins parallel für + und −, 2 A pro Pin.
  - Akku + DS18B20: S4B-PH-SM4-TB mit Belegung 1 = Akku +, 2 = Akku − / GND, 3 = DQ, 4 = 3,3 V.
  - Display: Qwiic-Buchse SM04B-SRSS-TB.
  - Nur die Gehäuselaschen der USB-C-Buchse gehen durchs Board.
- **Footprint Drossel:** Die FXL1360-680-M (13,45 × 12,6 mm) liegt auf dem KiCad-Footprint L_TaiTech_TMPC1265_13.5x12.5mm. Pads gegen das Datenblatt des Herstellers prüfen.
- **TPS54160A:** Geprüft gegen das TI-Datenblatt SLVSB56C (Rev. C, Feb. 2014). Pinbelegung, VREF 0,8 V, EN-Schwelle 1,11–1,36 V (EN max. 5 V), BOOT 0,1 µF und Softstart (10 nF → 4 ms) stimmen. RT = 206033/f^1,0888, mit 390 k ergeben sich 316 kHz. Kompensation nach Abschnitt 9.2.2.10 (gmEA 97 µA/V, gmPS 6 A/V): Bei 0,6 A und einer wirksamen Ausgangskapazität von ca. 8 µF ergeben sich Rc ≈ 13,7 k und Cc ≈ 14 nF. Die gewählten 18 k / 15 nF ergeben eine Durchtrittsfrequenz fc ≈ 10 kHz, zulässig sind 4,1…15,9 kHz. Trotzdem mit Lastsprung messen.
- **Drossel:** FXL1360-680-M (C526032), 68 µH, 3 A Nennstrom, 4,5 A laut JLCPCB-Listing. Damit hat sie genug Reserve über der TPS54160A-Strombegrenzung (typ. 2,7 A). Ob die 4,5 A der Sättigungsstrom sind, in der I(L)-Kurve des Datenblatts prüfen.
- **ERC:** In KiCad ausführen. Die Prüfung hier erfolgte über den Netzlisten-Export: keine offenen Netze außer den bewusst nicht beschalteten Pins.
- Die Verbindungen sind über **Netzlabels** an Pin-Stichleitungen realisiert. Elektrisch ist das vollständig. Für eine schönere Darstellung kann man die Bauteile in KiCad umsortieren.

## Leiterplatte (`perinode24.kicad_pcb`)

**Stand: geroutet. DRC ohne Abstands-, Rand-, Bohr- oder Breitenverletzungen. 6 kurze Signalverbindungen sind noch von Hand zu ziehen** (siehe unten).

- **Format:** 200 × 131 mm, 4 Lagen, 1,6 mm (JLCPCB JLC04161H-7628), alle Bauteile SMD und oben.
- **Lagenaufbau:**
  - F.Cu: Bauteile, Signale, GND-Fläche
  - In1: durchgehende GND-Fläche (keine Leiterbahnen)
  - In2: Signale und +24-V-Fläche
  - B.Cu: Signale, GND-Fläche
- **Stitching:** rund 610 Vias im 5-mm-Raster verbinden die GND-Flächen. Unter der ESP32-Antenne ist auf allen Lagen kein Kupfer.
- **Netzklassen:**
  - Power24 0,8 mm: +24 V, Eingänge
  - Power 0,5 mm: Schaltknoten, Ausgang, Akku
  - Sense 0,3 mm: Shunt
  - Supply 0,3 mm: GND, +5 V, +3,3 V
  - Default 0,25 mm
  - Abstand 0,2 mm, Randabstand 0,2 mm (JLCPCB: ≥ 0,2 mm bei gefrästen Kanten), Mindestbahnbreite 0,12 mm
- `docs/platine_F.png`, `platine_In2.png`, `platine_B.png`: Ansichten der Lagen. `docs/drc_bericht.txt`: DRC-Bericht.

### Noch von Hand zu verbinden (in KiCad mit „Leiterbahn verlegen“, X)
| Kanal | Netz | von | nach |
|---|---|---|---|
| 1 | SS | U101 Pin 4 | C104 Pin 1 |
| 4 | SS | U401 Pin 4 | C404 Pin 1 |
| 6 | SS | U601 Pin 4 | C604 Pin 1 |
| 2 | EN_N | U201 Pin 3 | vorhandene Bahn auf In2 |
| 3 | EN_N | U301 Pin 3 | vorhandene Bahn auf In2 |
| 5 | EN_N | U501 Pin 3 → R504 Pin 1 → vorhandene Bahn (1,8 mm) |

Die Pins 3/4 des TPS54160A liegen im 0,5-mm-Raster zwischen bereits verlegten Bahnen. Am einfachsten verschiebt man die Bahn an Pin 5 (RT) etwas oder führt die Verbindung mit einem Via über B.Cu, wo unter dem IC Platz ist. Zwei winzige GND-Flächeninseln auf F.Cu werden nach dem Nachrouten mit einem Via angebunden oder können gelöscht werden. Danach Zonen füllen (B) und die DRC erneut ausführen.

### Wie die Leiterplatte entstanden ist (Werkzeuge in `tools/`)
1. `gen_pcb.py`: Footprints aus der Netzliste, Platzierung (Ankerplätze und automatische Platzierung), Umriss, Bohrungen, Flächen
2. `preroute.py`: kritische Anschlüsse der fein gerasterten ICs vorverlegen (TPS VIN → +24-V-Via, GND-Pins → Via bzw. Thermal-Pad) und fixieren
3. Export DSN, `dsn_classes.py` (Netzklassen ergänzen, GND für Freerouting ausblenden), **Freerouting 2.5.0** mit 10 Durchgängen
4. `import_ses.py`: Session einspielen
5. `postroute.py`: +24-V-Fläche auf In2, offene Pads an Flächen, Lücken schließen, Inseln, Stitching-Vias (alles mit KiCads Kollisionsprüfung)
6. `maze.py`: A*-Router für einzelne Restverbindungen
7. `check_pcb.py`: Zonen füllen und DRC. `set_netclasses.py` nach jedem Speichern über die API ausführen, weil KiCad 7 headless die Projekt-Netzklassen zurücksetzt.

Nach dem Nachrouten in KiCad: Gerber, Bohrdaten, BOM und CPL für JLCPCB erzeugen, zum Beispiel mit dem Plugin „Fabrication Toolkit“, das das Feld LCSC übernimmt.
