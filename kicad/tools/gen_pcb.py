#!/usr/bin/env python3
"""
Erzeugt die Leiterplatte perinode24.kicad_pcb aus der Schaltplan-Netzliste (KiCad 7 pcbnew-API).

  - 4 Lagen (JLCPCB JLC04161H-7628): F.Cu Signale/GND | In1 GND-Fläche | In2 Signale (+24V) | B.Cu Signale/GND
  - Footprints mit Netzen, LCSC-Feldern und Schaltplan-Verknüpfung (Update PCB from Schematic funktioniert)
  - Platzierung: Leistungsbauteile je Kanal auf festen Ankerplätzen, alle übrigen Bauteile automatisch
    kollisionsfrei nahe ihren Verbindungspartnern
  - Platinenumriss, Befestigungslöcher M3, Kupferflächen, Netzklassen
Routing: Freerouting (DSN-Export perinode24.dsn) oder manuell.

Aufruf:  kicad-cli sch export netlist --format kicadsexpr -o /tmp/p24.net perinode24.kicad_sch
         python3 tools/gen_pcb.py /tmp/p24.net
"""
import math, os, sys
import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, find, find1

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FPLIB = "/usr/share/kicad/footprints"
MM = pcbnew.FromMM

# ------------------------------------------------------------ Geometrie
W, H = 200.0, 131.0                 # Platinengröße
OX, OY = 30.0, 30.0                 # Lage auf dem Zeichenblatt
CELL_X0, CELL_W, CELL_H = 30.0, 52.0, 48.0
MID_Y0, MID_Y1 = CELL_H, H - CELL_H # Mittelstreifen (ESP32, Hilfsversorgungen)
RIGHT_X = CELL_X0 + 3 * CELL_W      # 171: rechter Rand (USB, Antenne)

def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))

# ------------------------------------------------------------ Netzliste
def read_netlist(path):
    n = parse(open(path).read())
    comps = {}
    for c in find(find1(n, "components"), "comp"):
        ref = find1(c, "ref")[1]
        fields = {f[1][1]: (f[2] if len(f) > 2 else "") for f in find(find1(c, "fields") or [], "field")}
        sp = find1(c, "sheetpath")
        comps[ref] = dict(value=find1(c, "value")[1], fp=find1(c, "footprint")[1], fields=fields,
                          path=find1(sp, "tstamps")[1] + find1(c, "tstamps")[1],
                          sheet=find1(sp, "names")[1])
    pinnet = {}
    for ne in find(find1(n, "nets"), "net"):
        name = find1(ne, "name")[1]
        for nd in find(ne, "node"):
            pinnet[(find1(nd, "ref")[1], find1(nd, "pin")[1])] = name
    return comps, pinnet

# ------------------------------------------------------------ Ankerplätze
# Kanalzelle 47 x 44 mm, Ursprung oben links, Akkubuchse an der Oberkante (obere Reihe).
# Für die untere Reihe wird die Zelle um 180° gedreht (Buchse an der Unterkante).
CH_ANCHOR = {   # Suffix (Ref ohne Kanalziffer) : (x, y, Drehung)
    "J01": (8.0, 5.6, 180),      # Akku + DS18B20 (Steckseite zur Kante)
    "F01": (19.0, 3.6, 0),       # PTC 1812
    "D04": (19.0, 8.6, 0),       # TVS
    "Q01": (25.0, 3.4, 0),       # Verpolschutz-P-FET
    "D03": (25.0, 7.6, 0),       # Z-Diode G-S
    "R11": (28.5, 6.0, 90),
    "R10": (32.5, 3.4, 0),       # Shunt 1206
    "D02": (40.0, 3.6, 180),     # Rückspeisesperre SS34
    "L01": (37.0, 15.5, 0),      # Speicherdrossel 13,5 x 12,5
    "C07": (44.6, 22.5, 90),     # Ausgangskondensatoren am Drosselausgang
    "C08": (44.6, 26.2, 90),
    "D01": (28.0, 26.0, 90),     # Freilaufdiode direkt an PH
    "U01": (22.0, 27.0, 0),      # TPS54160A
    "C01": (22.0, 33.2, 0),      # Eingangskondensator 1210 direkt an VIN/GND
    "C02": (17.0, 31.0, 90),
    "C03": (26.0, 21.5, 0),      # Bootstrap
    "U02": (8.0, 16.0, 0),       # INA226
    "U03": (14.0, 21.5, 0),      # INA181
    "U04": (8.0, 31.0, 0),       # TLV9062
}

ROOT_ANCHOR = {
    # Eingänge links (Steckseite zur linken Kante)
    "J1": (5.6, 17.0, 270), "F1": (15.0, 9.0, 0), "D1": (15.0, 13.5, 0), "U1": (15.0, 19.0, 0),
    "Q1": (24.0, 16.0, 0), "C1": (15.0, 23.0, 0),
    "J2": (5.6, H - 17.0, 270), "F2": (15.0, H - 9.0, 0), "D2": (15.0, H - 13.5, 0), "U2": (15.0, H - 19.0, 0),
    "Q2": (24.0, H - 16.0, 0), "C2": (15.0, H - 23.0, 0),
    "C3": (15.0, H / 2, 90), "C4": (24.0, 50.0, 90),
    # 5 V / 3,3 V im Mittelstreifen links
    "U3": (40.0, 52.0, 0), "L1": (48.0, 52.0, 0), "D3": (40.0, 57.5, 0), "C6": (35.0, 52.0, 90),
    "U4": (60.0, 52.0, 0), "D4": (66.0, 72.0, 0),
    # ESP32: Antenne zur rechten Kante
    "U5": (W - 13.5, H / 2, 270),
    "SW1": (140.0, 78.0, 0), "SW2": (148.0, 78.0, 0),
    "J3": (110.0, 78.5, 0),
    # USB-C an der Oberkante rechts
    "J4": (W - 7.0, 5.2, 180), "U6": (W - 7.0, 13.0, 0),
}
CH_REGION = lambda k: ((CELL_X0 + (k - 1) * CELL_W, 0.0) if k <= 3 else (CELL_X0 + (k - 4) * CELL_W, H - CELL_H))
ROOT_REGIONS = [  # (x0, y0, x1, y1) – Reihenfolge = Suchreihenfolge
    (1.0, 1.0, CELL_X0 - 0.5, H - 1.0),                 # linker Streifen
    (CELL_X0, MID_Y0 + 0.5, RIGHT_X - 0.5, MID_Y1 - 0.5),  # Mittelstreifen
    (RIGHT_X + 0.5, 1.0, W - 1.0, 36.0),                # rechts oben (USB)
]
HOLES = [(3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5), (W - 3.5, 100.0)]

GLOBAL_POWER = {"GND", "+24V", "+5V", "+3V3"}
# Bauteile ohne Signalnetz (Abblockkondensatoren usw.) -> neben dieses Bauteil
NEAR_ROOT = {"C12": "U5", "C13": "U5", "R8": "U5", "R9": "U5", "R10": "U5", "C10": "U4", "C11": "U4",
             "R5": "U4", "C8": "L1", "C9": "L1", "C5": "U5", "R1": "U5", "R2": "U5"}
NEAR_CH = {"C10": "U02", "C11": "U03", "C15": "U04", "C02": "U01"}

# ------------------------------------------------------------ Platzierer
class Placer:
    def __init__(self):
        self.rects = []                         # belegte Rechtecke (x0,y0,x1,y1) in Platinen-mm
    @staticmethod
    def fp_rect(fp, clr=0.7):
        if fp.GetReference().startswith("U") and "ESP32" in fp.GetValue():
            # nur Modulkörper (die Antennen-Sperrfläche wird separat freigehalten)
            bb = pcbnew.BOX2I()
            for p in fp.Pads():
                bb.Merge(p.GetBoundingBox())
            c = fp.GetPosition()
            x0, y0 = pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY
            x1, y1 = pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY
            return (x0 - clr, y0 - clr, x1 + clr, y1 + clr)
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
        return (pcbnew.ToMM(bb.GetLeft()) - OX - clr, pcbnew.ToMM(bb.GetTop()) - OY - clr,
                pcbnew.ToMM(bb.GetRight()) - OX + clr, pcbnew.ToMM(bb.GetBottom()) - OY + clr)
    def free(self, r, region):
        if r[0] < region[0] or r[1] < region[1] or r[2] > region[2] or r[3] > region[3]:
            return False
        for o in self.rects:
            if r[0] < o[2] and r[2] > o[0] and r[1] < o[3] and r[3] > o[1]:
                return False
        return True
    def put(self, fp, x, y, rot):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))
        self.rects.append(self.fp_rect(fp, 0.0))
    def search(self, fp, tx, ty, regions, step=0.5):
        cands = []
        for region in regions:
            nx = int((region[2] - region[0]) / step) + 1
            ny = int((region[3] - region[1]) / step) + 1
            cands += [((region[0] + i * step - tx) ** 2 + (region[1] + j * step - ty) ** 2,
                       region[0] + i * step, region[1] + j * step, region) for i in range(nx) for j in range(ny)]
        cands.sort(key=lambda c: c[0])
        for _, x, y, region in cands:
            for rot in (0, 90):
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(P(x, y))
                if self.free(self.fp_rect(fp), region):
                    self.put(fp, x, y, rot)
                    return
        raise RuntimeError(f"Kein Platz für {fp.GetReference()}")

# ------------------------------------------------------------ Aufbau
def main(netpath):
    comps, pinnet = read_netlist(netpath)
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    # JLCPCB-taugliche Grundregeln (4 Lagen)
    ds.m_TrackMinWidth = MM(0.15); ds.m_MinClearance = MM(0.15)
    ds.m_ViasMinSize = MM(0.45); ds.m_MinThroughDrill = MM(0.2)
    ds.m_HoleToHoleMin = MM(0.5); ds.m_CopperEdgeClearance = MM(0.3)

    nets = {}
    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    fps = {}
    for ref, c in sorted(comps.items()):
        lib, name = c["fp"].split(":")
        fp = pcbnew.FootprintLoad(f"{FPLIB}/{lib}.pretty", name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH(c["path"]))
        for k in ("LCSC", "MPN"):
            if c["fields"].get(k):
                fp.SetProperty(k, c["fields"][k])
        for pad in fp.Pads():
            n = pinnet.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(net(n))
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        fp.Reference().SetTextThickness(MM(0.12))
        fp.Value().SetVisible(False)
        if ref[0] in "RCDLF" and not ref.startswith("L"):
            fp.Reference().SetLayer(pcbnew.F_Fab)   # kleine Passive: Bezeichner nur in der Bestückungszeichnung
        board.Add(fp)
        fps[ref] = fp

    pl = Placer()
    # Befestigungslöcher
    for i, (x, y) in enumerate(HOLES, 1):
        h = pcbnew.FootprintLoad(f"{FPLIB}/MountingHole.pretty", "MountingHole_3.2mm_M3_Pad_Via")
        h.SetReference(f"H{i}"); h.Value().SetVisible(False); h.Reference().SetVisible(False)
        h.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_3.2mm_M3_Pad_Via"))
        for pad in h.Pads():
            pad.SetNet(net("GND"))
        board.Add(h)
        pl.put(h, x, y, 0)
    # Antennenbereich ESP32 freihalten (rechter Rand, Mittelstreifen)
    pl.rects.append((RIGHT_X - 2, MID_Y0 - 4, W, MID_Y1 + 4))

    # --- Kanäle: Anker
    def cell_xy(k, x, y, rot):
        x0, y0 = CH_REGION(k)
        if k <= 3:
            return x0 + x, y0 + y, rot
        return x0 + CELL_W - x, y0 + CELL_H - y, (rot + 180) % 360
    for k in range(1, 7):
        for suf, (x, y, rot) in CH_ANCHOR.items():
            ref = f"{suf[0]}{k}{suf[1:]}"
            if ref in fps:
                pl.put(fps[ref], *cell_xy(k, x, y, rot))
    for ref, (x, y, rot) in ROOT_ANCHOR.items():
        pl.put(fps[ref], x, y, rot)

    # --- übrige Bauteile: nahe der Verbindungspartner
    placed = {r for r in fps if any(r == f"{s[0]}{k}{s[1:]}" for k in range(1, 7) for s in CH_ANCHOR) or r in ROOT_ANCHOR}
    def partners(ref):
        mynets = {pinnet[(ref, p.GetNumber())] for p in fps[ref].Pads() if (ref, p.GetNumber()) in pinnet}
        sig = {n for n in mynets if n not in GLOBAL_POWER}
        pts = []
        for p in placed:
            for pad in fps[p].Pads():
                if pinnet.get((p, pad.GetNumber())) in (sig or mynets):
                    pos = pad.GetPosition()
                    pts.append((pcbnew.ToMM(pos.x) - OX, pcbnew.ToMM(pos.y) - OY))
        return pts
    todo = [r for r in fps if r not in placed]
    while todo:
        todo.sort(key=lambda r: (r not in NEAR_ROOT, -len(partners(r))))
        ref = todo.pop(0)
        k = int(ref[1]) if comps[ref]["sheet"].startswith("/Ladekanal") else 0
        hint = NEAR_ROOT.get(ref) if not k else (lambda h: h and f"{h[0]}{k}{h[1:]}")(NEAR_CH.get(ref[0] + ref[2:]))
        if hint:
            pos = fps[hint].GetPosition()
            pts = [(pcbnew.ToMM(pos.x) - OX, pcbnew.ToMM(pos.y) - OY)]
        else:
            pts = partners(ref)
        if k:
            x0, y0 = CH_REGION(k)
            regions = [(x0 + 0.5, y0 + 0.5, x0 + CELL_W - 0.5, y0 + CELL_H - 0.5)]
            cx, cy = x0 + CELL_W / 2, y0 + CELL_H / 2
        else:
            regions = ROOT_REGIONS
            cx, cy = 100.0, 62.5
        tx = sum(p[0] for p in pts) / len(pts) if pts else cx
        ty = sum(p[1] for p in pts) / len(pts) if pts else cy
        pl.search(fps[ref], tx, ty, regions)
        placed.add(ref)

    # --- Umriss (abgerundete Ecken)
    r = 3.0
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
    def arc(c, start, ang):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(*c)); s.SetStart(P(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc((W - r, r), (W - r, 0), 90); arc((W - r, H - r), (W, H - r), 90)
    arc((r, H - r), (r, H), 90); arc((r, r), (0, r), 90)

    # --- Kupferflächen
    def zone(layer, netname, prio=0, pts=None):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net(netname))
        z.SetAssignedPriority(prio)
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)  # SMD-Pads voll, THT mit Thermal
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.5))
        ol = z.Outline(); ol.NewOutline()
        for x, y in (pts or [(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]):
            ol.Append(MM(OX + x), MM(OY + y))
        board.Add(z)
        return z
    zone(pcbnew.In1_Cu, "GND")
    zone(pcbnew.B_Cu, "GND")
    zone(pcbnew.F_Cu, "GND")
    # Antennen-Sperrfläche (zusätzlich zu der im ESP32-Footprint) über alle Lagen
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True); ka.SetDoNotAllowCopperPour(True); ka.SetDoNotAllowTracks(True)
    ka.SetDoNotAllowVias(True); ka.SetDoNotAllowPads(False); ka.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    ka.SetLayerSet(ls)
    ol = ka.Outline(); ol.NewOutline()
    for x, y in [(W - 7.5, MID_Y0 - 3), (W, MID_Y0 - 3), (W, MID_Y1 + 3), (W - 7.5, MID_Y1 + 3)]:
        ol.Append(MM(OX + x), MM(OY + y))
    board.Add(ka)

    # --- Beschriftung
    def txt(s, x, y, size=1.5, layer=pcbnew.F_SilkS):
        t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetPosition(P(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(size * 0.15)); board.Add(t)
    txt("Perinode24 Lader 6x 12V/2,4Ah  v1.0", 110, 50, 1.6)
    for k in range(1, 7):
        x0, y0 = CH_REGION(k)
        txt(f"AKKU {k}", x0 + (24 if k <= 3 else CELL_W - 24), y0 + (9.5 if k <= 3 else CELL_H - 9.5), 1.4)
    txt("24V DC", 10, 1.8, 1.2); txt("24V PSU", 10, H - 1.8, 1.2); txt("USB", W - 13, 10, 1.0)

    fn = os.path.join(OUT, "perinode24.kicad_pcb")
    board.SetFileName(fn)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    pcbnew.SaveBoard(fn, board)
    b2 = pcbnew.LoadBoard(fn)            # Füllen auf geladenem Board (frisches BOARD-Objekt stürzt in KiCad 7 ab)
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    pcbnew.SaveBoard(fn, b2)
    print("Footprints:", len(fps), "| Netze:", len(nets), "->", fn)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/p24.net")
