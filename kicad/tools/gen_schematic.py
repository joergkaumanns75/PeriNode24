#!/usr/bin/env python3
"""
Erzeugt das KiCad-Projekt "perinode24" (KiCad 7-Format, öffnet auch in 8/9):
  - perinode24.kicad_sch        Hauptblatt: Einspeisung 24 V DC / Netzteil, 5 V, 3,3 V, ESP32-S3, USB
  - kanal1..6.kicad_sch         je ein Ladekanal (TPS54160A, CC/CV-Regelung, INA226, Schutz)
  - perinode24.kicad_sym        Projektsymbole (TPS54160A, N-MOSFET SO-8)
  - bom_jlcpcb.csv              Stückliste im JLCPCB-Format mit LCSC-Nummern

Verbindungen werden über Netzlabels an kurzen Pin-Stichleitungen hergestellt.
"""
import copy, csv, json, os, sys, uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from sexp import Sym as S, dump, find, find1
from inspect_sym import get as libget

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT = "perinode24"
NS = uuid.UUID("5b0c1f7e-6a43-4f6e-9d55-0a1b2c3d4e5f")
_ucount = [0]
def U():
    _ucount[0] += 1
    return str(uuid.uuid5(NS, str(_ucount[0])))

POWER_NETS = {"GND": "power:GND", "+24V": "power:+24V", "+5V": "power:+5V", "+3V3": "power:+3V3"}
GLOBAL_NETS = {"SDA", "SCL", "ONEWIRE"} | {f"{p}{k}" for p in ("VSET", "ISET", "EN") for k in range(1, 7)}

# ---------------------------------------------------------------- Bauteile / LCSC
# key -> (Wert, Footprint, LCSC, Hersteller-Teilenummer, geprüft)
P = {
 "R10k":  ("10k",   "Resistor_SMD:R_0603_1608Metric", "C25804", "0603WAF1002T5E", True),
 "R100k": ("100k",  "Resistor_SMD:R_0603_1608Metric", "C25803", "0603WAF1003T5E", True),
 "R200k": ("200k",  "Resistor_SMD:R_0603_1608Metric", "C25811", "0603WAF2003T5E", True),
 "R11k8": ("11.8k", "Resistor_SMD:R_0603_1608Metric", "C325665", "RMC060311.8K1%N", True),
 "R18k":  ("18k",   "Resistor_SMD:R_0603_1608Metric", "C25810", "0603WAF1802T5E", True),
 "R330k": ("330k",  "Resistor_SMD:R_0603_1608Metric", "C23137", "0603WAF3303T5E", True),
 "R390k": ("390k",  "Resistor_SMD:R_0603_1608Metric", "C23150", "0603WAF3903T5E", True),
 "R1k":   ("1k",    "Resistor_SMD:R_0603_1608Metric", "C21190", "0603WAF1001T5E", True),
 "R2k2":  ("2.2k",  "Resistor_SMD:R_0603_1608Metric", "C4190",  "0603WAF2201T5E", True),
 "R4k7":  ("4.7k",  "Resistor_SMD:R_0603_1608Metric", "C23162", "0603WAF4701T5E", True),
 "R5k1":  ("5.1k",  "Resistor_SMD:R_0603_1608Metric", "C23186", "0603WAF5101T5E", True),
 "Rsh":   ("50mR 1W", "Resistor_SMD:R_1206_3216Metric", "C912768", "RLM12FTCMR050", True),
 "C100n": ("100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", "CC0603KRX7R9BB104", True),
 "C1u":   ("1uF",   "Capacitor_SMD:C_0603_1608Metric", "C15849", "CL10A105KB8NNNC", True),
 "C10n":  ("10nF",  "Capacitor_SMD:C_0603_1608Metric", "C57112", "0603B103K500NT", True),
 "C15n":  ("15nF",  "Capacitor_SMD:C_0603_1608Metric", "C296018", "0603B153K500CT", True),
 "C47p":  ("47pF",  "Capacitor_SMD:C_0603_1608Metric", "C1671",  "0603CG470J500NT", False),
 "C10u":  ("10uF 25V", "Capacitor_SMD:C_0805_2012Metric", "C15850", "CL21A106KAYNNNE", True),
 "C2u2":  ("2.2uF 100V", "Capacitor_SMD:C_1210_3225Metric", "C55151", "CL32B225KCJSNNE", True),
 "C470u": ("470uF 50V", "Capacitor_SMD:CP_Elec_10x12.5", "C22469994", "EFVM050ADA471M10C0", True),
 "L68u":  ("68uH 3A/4.5A", "Inductor_SMD:L_TaiTech_TMPC1265_13.5x12.5mm", "C526032", "FXL1360-680-M", True),
 "L22u":  ("22uH 1.5A", "Inductor_SMD:L_Bourns_SRN6045TA", "C780213", "SRN6045-220M", True),
 "SS34":  ("SS34",  "Diode_SMD:D_SMA", "C8678",  "SS34", True),
 "SS310": ("SS310", "Diode_SMD:D_SMA", "C15874", "SS310", True),
 "BAT54": ("BAT54WS", "Diode_SMD:D_SOD-323", "C3040452", "BAT54WS", True),
 "Z12":   ("BZT52C12", "Diode_SMD:D_SOD-123", "C2891780", "BZT52C12", True),
 "TVS33": ("SMBJ33A", "Diode_SMD:D_SMB", "C353366", "SMBJ33A", True),
 "TVS18": ("SMAJ18A", "Diode_SMD:D_SMA", "C148219", "SMAJ18A", True),
 "PTC":   ("1.1A PTC", "Fuse:Fuse_1812_4532Metric", "C142746", "1812L110/16DR", True),
 "F5A":   ("5A T", "Fuse:Fuse_Littelfuse-NANO2-451_453", "C66503", "0452005.MRL", True),
 "AO3407": ("AO3407A", "Package_TO_SOT_SMD:SOT-23", "C15155", "AO3407A", True),
 "AO4264": ("AO4264E", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "C334232", "AO4264E", True),
 "TPS54160": ("TPS54160A", "Package_SO:MSOP-10-1EP_3x3mm_P0.5mm_EP1.68x1.88mm_ThermalVias", "C390949", "TPS54160ADGQR", True),
 "INA226": ("INA226", "Package_SO:VSSOP-10_3x3mm_P0.5mm", "C49851", "INA226AIDGSR", True),
 "INA181": ("INA181A2", "Package_TO_SOT_SMD:SOT-23-6", "C2058784", "INA181A2IDBVR", True),
 "TLV9062": ("TLV9062", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "C398355", "TLV9062IDR", True),
 "LM74700": ("LM74700-Q1", "Package_TO_SOT_SMD:SOT-23-6", "C2941042", "LM74700QDBVRQ1", True),
 "LMR16006": ("LMR16006X", "Package_TO_SOT_SMD:TSOT-23-6", "C2070731", "LMR16006XDDCT", True),
 "TLV757": ("TLV75733P", "Package_TO_SOT_SMD:SOT-23-5", "C485517", "TLV75733PDBVR", True),
 "ESP32": ("ESP32-S3-WROOM-1-N8R8", "RF_Module:ESP32-S3-WROOM-1", "C2913201", "ESP32-S3-WROOM-1-N8R8", True),
 "USBLC6": ("USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "C7519", "USBLC6-2SC6", True),
 "USBC": ("USB-C", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "C165948", "TYPE-C-31-M-12", True),
 "PH6":  ("JST PH 6P SMD", "Connector_JST:JST_PH_S6B-PH-SM4-TB_1x06-1MP_P2.00mm_Horizontal", "C265405", "S6B-PH-SM4-TB(LF)(SN)", True),
 "PH4":  ("JST PH 4P SMD", "Connector_JST:JST_PH_S4B-PH-SM4-TB_1x04-1MP_P2.00mm_Horizontal", "C265102", "S4B-PH-SM4-TB(LF)(SN)", True),
 "SW":   ("TS-1187A", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "C318884", "TS-1187A-B-A-B", True),
 "LEDG": ("LED gruen", "LED_SMD:LED_0603_1608Metric", "C72043", "19-217/GHC-YR1S2/3T", True),
 "SH4":  ("Qwiic/OLED", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", "C160404", "SM04B-SRSS-TB(LF)(SN)", True),
}

# ---------------------------------------------------------------- Symbole
def custom_symbols():
    """Projektsymbole TPS54160A und N-MOSFET im SO-8 (S=1..3, G=4, D=5..8)."""
    def pin(typ, x, y, ang, name, num, length=2.54, hidden=False):
        p = [S("pin"), S(typ), S("line"), [S("at"), x, y, ang], [S("length"), length]]
        if hidden:
            p.append(S("hide"))
        p += [[S("name"), name, [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]],
              [S("number"), num, [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]]]
        return p
    def prop(k, v, x, y, hide=False):
        e = [S("effects"), [S("font"), [S("size"), 1.27, 1.27]]]
        if hide:
            e.append(S("hide"))
        return [S("property"), k, v, [S("at"), x, y, 0], e]
    tps = [S("symbol"), "TPS54160A", [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
           prop("Reference", "U", -10.16, 8.89), prop("Value", "TPS54160A", 0, -13.97),
           prop("Footprint", P["TPS54160"][1], 0, -16.51, True),
           prop("Datasheet", "https://www.ti.com/lit/ds/symlink/tps54160a.pdf", 0, -19.05, True),
           prop("Description", "60V 1.5A Step-Down-Wandler, Current-Mode, MSOP-10 PowerPAD", 0, 0, True),
           [S("symbol"), "TPS54160A_0_1",
            [S("rectangle"), [S("start"), -10.16, 7.62], [S("end"), 10.16, -7.62],
             [S("stroke"), [S("width"), 0.254], [S("type"), S("default")]], [S("fill"), [S("type"), S("background")]]]],
           [S("symbol"), "TPS54160A_1_1",
            pin("power_in", -12.7, 5.08, 0, "VIN", "2"),
            pin("input", -12.7, 2.54, 0, "EN", "3"),
            pin("passive", -12.7, 0, 0, "SS/TR", "4"),
            pin("passive", -12.7, -2.54, 0, "RT/CLK", "5"),
            pin("open_collector", -12.7, -5.08, 0, "PWRGD", "6"),
            pin("passive", 12.7, 5.08, 180, "BOOT", "1"),
            pin("output", 12.7, 2.54, 180, "PH", "10"),
            pin("input", 12.7, -2.54, 180, "VSENSE", "7"),
            pin("passive", 12.7, -5.08, 180, "COMP", "8"),
            pin("power_in", -1.27, -10.16, 90, "GND", "9"),
            pin("passive", 1.27, -10.16, 90, "PAD", "11")]]
    # N-MOSFET SO-8: Grafik von Device:Q_NMOS_GDS übernehmen
    base = copy.deepcopy(libget("Device:Q_NMOS_GDS"))
    out = [S("symbol"), "Q_NMOS_SO8", [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
           prop("Reference", "Q", 5.08, 1.27), prop("Value", "Q_NMOS_SO8", 5.08, -1.27),
           prop("Footprint", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 0, -6.35, True),
           prop("Datasheet", "~", 0, -8.89, True),
           prop("Description", "N-Kanal-MOSFET SO-8 (S 1-3, G 4, D 5-8)", 0, 0, True)]
    for sub in find(base, "symbol"):
        sub = copy.deepcopy(sub)
        sub[1] = sub[1].replace("Q_NMOS_GDS_", "Q_NMOS_SO8_")
        newsub = [x for x in sub if not (isinstance(x, list) and x and x[0] == "pin")]
        for p in find(sub, "pin"):
            name = find1(p, "name")[1]
            at = find1(p, "at")
            nums = {"G": ["4"], "D": ["5", "6", "7", "8"], "S": ["1", "2", "3"]}[name]
            for i, n in enumerate(nums):
                newsub.append(pin(str(p[1]), float(at[1]), float(at[2]), float(at[3]), name, n,
                                  float(find1(p, "length")[1]), hidden=i > 0))
        out.append(newsub)
    return {"TPS54160A": tps, "Q_NMOS_SO8": out}

CUSTOM = custom_symbols()

def flatten(libid):
    lib, name = libid.split(":")
    s = copy.deepcopy(CUSTOM[name] if lib == PROJECT else libget(libid))
    ext = find1(s, "extends")
    if ext:
        pname = ext[1]
        parent = flatten(f"{lib}:{pname}")
        new = [x for x in parent if not (isinstance(x, list) and x and x[0] == "property")]
        idx = next(i for i, x in enumerate(new) if isinstance(x, list) and x and x[0] == "symbol")
        new[idx:idx] = find(s, "property")
        for x in new:
            if isinstance(x, list) and x and x[0] == "symbol":
                x[1] = name + x[1][len(pname):]
        s = new
    s[1] = libid
    return s

_symcache = {}
def symdef(libid):
    if libid not in _symcache:
        _symcache[libid] = flatten(libid)
    return _symcache[libid]

def unit_pins(libid, unit):
    out = []
    for sub in find(symdef(libid), "symbol"):
        u = int(sub[1].rsplit("_", 2)[1])
        if u in (0, unit):
            for p in find(sub, "pin"):
                at = find1(p, "at")
                out.append(dict(num=find1(p, "number")[1], name=find1(p, "name")[1], typ=str(p[1]),
                                x=float(at[1]), y=float(at[2]), a=float(at[3]) if len(at) > 3 else 0.0))
    return out

# ---------------------------------------------------------------- Schaltplanblatt
def eff(size=1.27, justify=None, hide=False):
    e = [S("effects"), [S("font"), [S("size"), size, size]]]
    if justify:
        e.append([S("justify")] + [S(j) for j in justify.split()])
    if hide:
        e.append(S("hide"))
    return e

PWR_COUNT = [0]
BOM = []   # (ref, key)

class Sheet:
    def __init__(self, fname, title, path, page_w=420, page_h=297, paper="A3"):
        self.fname, self.title, self.path, self.paper = fname, title, path, paper
        self.min_next = 0.0
        self.uuid = U()
        self.items = []
        self.libids = set()
        self.cx, self.cy, self.rowh = 15.0, 25.0, 0.0
        self.page_w, self.page_h = page_w, page_h
        self.nets = defaultdict(list)

    # --- Grundelemente
    def wire(self, x1, y1, x2, y2):
        self.items.append([S("wire"), [S("pts"), [S("xy"), x1, y1], [S("xy"), x2, y2]],
                           [S("stroke"), [S("width"), 0], [S("type"), S("default")]], [S("uuid"), U()]])

    def text(self, s, x, y, size=2.0):
        self.items.append([S("text"), s, [S("at"), x, y, 0], eff(size, "left bottom"), [S("uuid"), U()]])

    def noconn(self, x, y):
        self.items.append([S("no_connect"), [S("at"), x, y], [S("uuid"), U()]])

    def label(self, net, x, y, d):
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
        if net in POWER_NETS:
            self.power(POWER_NETS[net], x, y, d)
        elif net in GLOBAL_NETS:
            just = "left" if ang in (0, 90) else "right"
            self.items.append([S("global_label"), net, [S("shape"), S("bidirectional")], [S("at"), x, y, ang],
                               [S("fields_autoplaced")], eff(1.27, just), [S("uuid"), U()],
                               [S("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [S("at"), x, y, 0],
                                eff(1.27, just, hide=True)]])
        else:
            just = "left bottom" if ang in (0, 90) else "right bottom"
            self.items.append([S("label"), net, [S("at"), x, y, ang], [S("fields_autoplaced")],
                               eff(1.27, just), [S("uuid"), U()]])

    def power(self, libid, x, y, d=(0, -1), flag=False):
        self.libids.add(libid)
        gnd = libid == "power:GND"
        if flag:
            rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[d]
        elif gnd:
            rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d]
        else:
            rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[d]
        PWR_COUNT[0] += 1
        ref = f"#FLG{PWR_COUNT[0]:03d}" if flag else f"#PWR{PWR_COUNT[0]:03d}"
        val = libid.split(":")[1]
        ty = y + (3.81 if gnd else -3.81) if rot in (0, 180) else y
        self.items.append([S("symbol"), [S("lib_id"), libid], [S("at"), x, y, rot], [S("unit"), 1],
                           [S("in_bom"), S("no")], [S("on_board"), S("yes")], [S("dnp"), S("no")],
                           [S("uuid"), U()],
                           [S("property"), "Reference", ref, [S("at"), x, y, 0], eff(hide=True)],
                           [S("property"), "Value", val, [S("at"), x, ty + (1.5 if gnd else -1.5), 0], eff()],
                           [S("property"), "Footprint", "", [S("at"), x, y, 0], eff(hide=True)],
                           [S("property"), "Datasheet", "", [S("at"), x, y, 0], eff(hide=True)],
                           [S("pin"), "1", [S("uuid"), U()]],
                           [S("instances"), [S("project"), PROJECT,
                                              [S("path"), self.path, [S("reference"), ref], [S("unit"), 1]]]]])

    def pwr_flag(self, net):
        """PWR_FLAG an ein Netz (eigene Stichleitung neben dem aktuellen Cursor)."""
        x, y = self.cx + 5.08, self.cy + 7.62
        self.power("power:PWR_FLAG", x, y, (0, -1), flag=True)
        self.wire(x, y, x, y + 5.08)
        self.label(net, x, y + 5.08, (0, 1))
        self.cx += 15.24
        self.rowh = max(self.rowh, 20)

    # --- Layout
    def newrow(self, title=None):
        self.cx = 15.0
        self.min_next = 0.0
        self.cy += self.rowh + 12.0
        self.rowh = 0.0
        if title:
            self.text(title, self.cx, self.cy - 4.0, 2.2)

    def group(self, title):
        """Neue Gruppe: Titel, ggf. neue Zeile."""
        if self.cx > 15.0:
            self.cx = max(self.cx + 12.0, self.min_next + 8.0)
        if self.cx > self.page_w - 120:
            self.newrow()
        self.text(title, self.cx, self.cy - 4.0, 2.2)
        self.min_next = self.cx + len(title) * 2.0

    # --- Bauteil
    def part(self, libid, ref, key, nets, unit=1, value=None, stub=2.54, record=True):
        self.libids.add(libid)
        pins = unit_pins(libid, unit)
        # Abmessungen (lokal, Schaltplan-Koordinaten, y nach unten)
        xs, ys = [], []
        for p in pins:
            dx, dy = round(-cosd(p["a"])), round(sind(p["a"]))
            net = nets.get(p["num"])
            ext = stub + (len(net) * 1.1 + 2.5 if net and net not in POWER_NETS else (6 if net else 1))
            xs += [p["x"], p["x"] + dx * ext]
            ys += [-p["y"], -p["y"] + dy * ext]
        xmin, xmax = min(xs + [-5]), max(xs + [5])
        ymin, ymax = min(ys + [-5]), max(ys + [5])
        w, h = xmax - xmin, ymax - ymin
        if self.cx + w > self.page_w - 12:
            self.newrow()
        x = snap(self.cx - xmin)
        y = snap(self.cy - ymin)
        self.cx += w + 6.0
        self.rowh = max(self.rowh, h)

        val = value or (P[key][0] if key else libid.split(":")[1])
        fp, lcsc, mpn = (P[key][1], P[key][2], P[key][3]) if key else ("", "", "")
        # Beschriftung
        small = (xmax - xmin) < 20
        if small:
            rpos, vpos, just = (x + 2.54, y - 1.27), (x + 2.54, y + 1.27), "left"
        else:
            bx = min(p["x"] for p in pins) + 2.54
            by = max(p["y"] for p in pins)
            rpos, vpos, just = (x + bx, y - by - 3.0), (x + bx, y - min(p["y"] for p in pins) + 3.0), "left"
        sym = [S("symbol"), [S("lib_id"), libid], [S("at"), x, y, 0], [S("unit"), unit],
               [S("in_bom"), S("yes")], [S("on_board"), S("yes")], [S("dnp"), S("no")], [S("uuid"), U()],
               [S("property"), "Reference", ref, [S("at"), rpos[0], rpos[1], 0], eff(1.27, just)],
               [S("property"), "Value", val, [S("at"), vpos[0], vpos[1], 0], eff(1.27, just)],
               [S("property"), "Footprint", fp, [S("at"), x, y, 0], eff(hide=True)],
               [S("property"), "Datasheet", "~", [S("at"), x, y, 0], eff(hide=True)],
               [S("property"), "LCSC", lcsc, [S("at"), x, y, 0], eff(hide=True)],
               [S("property"), "MPN", mpn, [S("at"), x, y, 0], eff(hide=True)]]
        for p in pins:
            sym.append([S("pin"), p["num"], [S("uuid"), U()]])
        sym.append([S("instances"), [S("project"), PROJECT,
                                     [S("path"), self.path, [S("reference"), ref], [S("unit"), unit]]]])
        self.items.append(sym)
        if record and key and unit == 1:
            BOM.append((ref, key))
        # Stichleitungen + Labels
        done = set()
        for p in pins:
            px, py = snap(x + p["x"]), snap(y - p["y"])
            if (px, py) in done:
                continue
            done.add((px, py))
            net = nets.get(p["num"])
            if net is None:
                if p["typ"] != "no_connect":
                    self.noconn(px, py)
                continue
            d = (round(-cosd(p["a"])), round(sind(p["a"])))
            ex, ey = snap(px + d[0] * stub), snap(py + d[1] * stub)
            self.wire(px, py, ex, ey)
            self.label(net, ex, ey, d)
            self.nets[net].append(f"{ref}.{p['num']}")
        missing = set(nets) - {p["num"] for p in pins}
        if missing:
            raise ValueError(f"{ref}: unbekannte Pins {missing}")

    # Kurzformen für Zweipole
    def R(self, ref, key, a, b):   self.part("Device:R", ref, key, {"1": a, "2": b})
    def C(self, ref, key, a, b):   self.part("Device:C", ref, key, {"1": a, "2": b})
    def CP(self, ref, key, a, b):  self.part("Device:C_Polarized", ref, key, {"1": a, "2": b})
    def L(self, ref, key, a, b):   self.part("Device:L", ref, key, {"1": a, "2": b})
    def D(self, ref, key, k, a):   self.part("Device:D_Schottky", ref, key, {"1": k, "2": a})
    def Z(self, ref, key, k, a):   self.part("Device:D_Zener", ref, key, {"1": k, "2": a})
    def F(self, ref, key, a, b):   self.part("Device:Fuse", ref, key, {"1": a, "2": b})
    def PTC(self, ref, key, a, b): self.part("Device:Polyfuse", ref, key, {"1": a, "2": b})

    def sexp(self, root=False, sheets=()):
        body = [S("kicad_sch"), [S("version"), 20230121], [S("generator"), S("eeschema")],
                [S("uuid"), self.uuid], [S("paper"), self.paper],
                [S("title_block"), [S("title"), self.title], [S("company"), "Perinode24"],
                 [S("comment"), 1, "Ladegeraet 6x 12V/2,4Ah Blei-Gel, ESP32-S3"],
                 [S("comment"), 2, "Generiert mit tools/gen_schematic.py"]],
                [S("lib_symbols")] + [symdef(l) for l in sorted(self.libids)]]
        body += self.items
        body += list(sheets)
        if root:
            body.append([S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]])
        return body

def cosd(a):
    import math
    return math.cos(math.radians(a))
def sind(a):
    import math
    return math.sin(math.radians(a))
def snap(v, g=1.27):
    return round(round(v / g) * g, 4)

# ---------------------------------------------------------------- Hauptblatt
ROOT_UUID = None

def build_root():
    sh = Sheet(f"{PROJECT}.kicad_sch", "Versorgung und Steuerung", "", page_w=594, page_h=420, paper="A2")
    global ROOT_UUID
    ROOT_UUID = sh.uuid
    sh.path = f"/{ROOT_UUID}"
    sh.text("Perinode24 - Ladegeraet fuer 6x 12V/2,4Ah Blei-Gel (IUoU), Steuerung ESP32-S3", 15, 14, 3.0)
    sh.cy = 32

    sh.group("Eingang 24V DC (18-32V) mit Verpolschutz / Ideal-Diode")
    sh.part("Connector_Generic:Conn_01x06", "J1", "PH6", {"1": "VIN_DC", "2": "VIN_DC", "3": "VIN_DC", "4": "GND", "5": "GND", "6": "GND"}, value="24V DC IN (3x+ / 3x-)")
    sh.F("F1", "F5A", "VIN_DC", "VIN_DC_F")
    sh.Z("D1", "TVS33", "VIN_DC_F", "GND")
    sh.part("Power_Management:LM74700", "U1", "LM74700",
            {"1": "VCAP1", "2": "GND", "3": "VIN_DC_F", "4": "+24V", "5": "GATE1", "6": "VIN_DC_F"})
    sh.C("C1", "C100n", "VCAP1", "VIN_DC_F")
    sh.part(f"{PROJECT}:Q_NMOS_SO8", "Q1", "AO4264", {"4": "GATE1", "1": "VIN_DC_F", "5": "+24V"})
    sh.pwr_flag("VIN_DC_F")

    sh.group("Eingang Netzteil 24V (Mean Well LRS-100-24, 230/240V AC extern)")
    sh.part("Connector_Generic:Conn_01x06", "J2", "PH6", {"1": "VIN_PSU", "2": "VIN_PSU", "3": "VIN_PSU", "4": "GND", "5": "GND", "6": "GND"}, value="24V PSU IN (3x+ / 3x-)")
    sh.F("F2", "F5A", "VIN_PSU", "VIN_PSU_F")
    sh.Z("D2", "TVS33", "VIN_PSU_F", "GND")
    sh.part("Power_Management:LM74700", "U2", "LM74700",
            {"1": "VCAP2", "2": "GND", "3": "VIN_PSU_F", "4": "+24V", "5": "GATE2", "6": "VIN_PSU_F"})
    sh.C("C2", "C100n", "VCAP2", "VIN_PSU_F")
    sh.part(f"{PROJECT}:Q_NMOS_SO8", "Q2", "AO4264", {"4": "GATE2", "1": "VIN_PSU_F", "5": "+24V"})
    sh.pwr_flag("VIN_PSU_F")

    sh.newrow()
    sh.group("24V-Bus Pufferung, Busspannungsmessung")
    sh.CP("C3", "C470u", "+24V", "GND")
    sh.C("C4", "C2u2", "+24V", "GND")
    sh.R("R1", "R100k", "+24V", "VBUS_SENSE")
    sh.R("R2", "R10k", "VBUS_SENSE", "GND")
    sh.C("C5", "C100n", "VBUS_SENSE", "GND")
    sh.pwr_flag("+24V")
    sh.pwr_flag("GND")

    sh.group("5V Hilfsversorgung (LMR16006, 0,6A)")
    sh.part("Regulator_Switching:LMR16006YQ", "U3", "LMR16006",
            {"1": "CB5", "2": "GND", "3": "FB5", "4": "+24V", "5": "+24V", "6": "SW5"}, value="LMR16006XDDCT")
    sh.C("C6", "C2u2", "+24V", "GND")
    sh.C("C7", "C100n", "CB5", "SW5")
    sh.D("D3", "SS310", "SW5", "GND")
    sh.L("L1", "L22u", "SW5", "+5V")
    sh.R("R3", "R100k", "+5V", "FB5")
    sh.R("R4", "R18k", "FB5", "GND")
    sh.C("C8", "C10u", "+5V", "GND")
    sh.C("C9", "C10u", "+5V", "GND")

    sh.group("3,3V (TLV75733)")
    sh.part("Regulator_Linear:TLV75733PDBV", "U4", "TLV757",
            {"1": "+5V", "2": "GND", "3": "+5V", "5": "+3V3"})
    sh.C("C10", "C1u", "+5V", "GND")
    sh.C("C11", "C10u", "+3V3", "GND")
    sh.R("R5", "R1k", "+3V3", "LED_PWR")
    sh.part("Device:LED", "D4", "LEDG", {"1": "GND", "2": "LED_PWR"})

    sh.newrow()
    sh.group("ESP32-S3-WROOM-1-N8R8 (IO35-37 durch Octal-PSRAM belegt)")
    esp = {"1": "GND", "40": "GND", "41": "GND", "2": "+3V3", "3": "ESP_EN", "27": "IO0",
           "39": "VBUS_SENSE",                             # IO1  ADC
           "12": "SDA", "17": "SCL", "18": "ONEWIRE",      # IO8 / IO9 / IO10
           "4": "VSET1", "5": "VSET2", "6": "VSET3", "7": "VSET4", "8": "VSET5", "9": "VSET6",
           "10": "ISET1", "11": "ISET2", "23": "ISET3", "31": "ISET4", "32": "ISET5", "33": "ISET6",
           "19": "EN1", "20": "EN2", "21": "EN3", "22": "EN4", "34": "EN5", "35": "EN6",
           "13": "USB_DN", "14": "USB_DP"}                 # IO19 / IO20
    sh.part("RF_Module:ESP32-S3-WROOM-1", "U5", "ESP32", esp)
    sh.C("C12", "C10u", "+3V3", "GND")
    sh.C("C13", "C100n", "+3V3", "GND")
    sh.R("R6", "R10k", "+3V3", "ESP_EN")
    sh.C("C14", "C1u", "ESP_EN", "GND")
    sh.part("Switch:SW_Push", "SW1", "SW", {"1": "ESP_EN", "2": "GND"}, value="RESET")
    sh.R("R7", "R10k", "+3V3", "IO0")
    sh.part("Switch:SW_Push", "SW2", "SW", {"1": "IO0", "2": "GND"}, value="BOOT")

    sh.group("I2C / 1-Wire / Display")
    sh.R("R8", "R2k2", "+3V3", "SDA")
    sh.R("R9", "R2k2", "+3V3", "SCL")
    sh.R("R10", "R4k7", "+3V3", "ONEWIRE")
    sh.part("Connector_Generic:Conn_01x04", "J3", "SH4",
            {"1": "GND", "2": "+3V3", "3": "SDA", "4": "SCL"}, value="Qwiic OLED SSD1306")

    sh.newrow()
    sh.group("USB-C (Programmierung/Diagnose, native USB)")
    sh.part("Connector:USB_C_Receptacle_USB2.0_16P", "J4", "USBC",
            {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "S1": "GND",
             "A4": "USB_VBUS", "A9": "USB_VBUS", "B4": "USB_VBUS", "B9": "USB_VBUS",
             "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN"})
    sh.R("R11", "R5k1", "CC1", "GND")
    sh.R("R12", "R5k1", "CC2", "GND")
    sh.part("Power_Protection:USBLC6-2SC6", "U6", "USBLC6",
            {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "2": "GND", "5": "USB_VBUS"})
    sh.D("D5", "SS34", "+5V", "USB_VBUS")
    sh.pwr_flag("USB_VBUS")
    sh.pwr_flag("+5V")

    sh.newrow()
    sh.text("Hinweise:", 15, sh.cy, 2.2)
    notes = [
        "- 230/240V AC nur ueber zertifiziertes Netzteil (Mean Well LRS-100-24 bzw. HDR-100-24N) an J2 - keine Netzspannung auf dieser Platine.",
        "- J1 und J2 duerfen gleichzeitig angeschlossen sein (Ideal-Dioden-ODER U1/U2).",
        "- INA226-Adressen: Kanal1 0x40, K2 0x41, K3 0x42, K4 0x43, K5 0x44, K6 0x45 (A0/A1-Beschaltung in den Kanalblaettern).",
        "- GPIO: VSET1-6 = IO4,5,6,7,15,16 (LEDC) | ISET1-6 = IO17,18,21,38,39,40 (Sigma-Delta) | EN1-6 = IO11,12,13,14,41,42",
        "- I2C SDA IO8 / SCL IO9 | 1-Wire IO10 | Busspannung IO1 (Teiler 100k/10k) | USB IO19/IO20",
    ]
    for i, n in enumerate(notes):
        sh.text(n, 15, sh.cy + 6 + i * 5, 1.6)
    sh.cy += 6 + len(notes) * 5
    sh.rowh = 0
    return sh

# ---------------------------------------------------------------- Ladekanal
ADDR = {1: ("GND", "GND"), 2: ("GND", "+3V3"), 3: ("GND", "SDA"),
        4: ("GND", "SCL"), 5: ("+3V3", "GND"), 6: ("+3V3", "+3V3")}   # (A1, A0)

def build_channel(k, sheet_uuid):
    sh = Sheet(f"kanal{k}.kicad_sch", f"Ladekanal {k}", f"/{ROOT_UUID}/{sheet_uuid}")
    n = k * 100
    r = lambda i: f"R{n + i}"
    c = lambda i: f"C{n + i}"
    sh.text(f"Ladekanal {k}: IUoU 0,6A / 14,4V / Erhaltung 13,65V (Sollwerte vom ESP32-S3)", 15, 14, 3.0)
    sh.cy = 32

    sh.group("Step-Down 24V -> 12,9...14,8V (TPS54160A, 300kHz)")
    sh.part(f"{PROJECT}:TPS54160A", f"U{n+1}", "TPS54160",
            {"2": "+24V", "3": "EN_N", "4": "SS", "5": "RT", "6": None,
             "1": "BOOT", "10": "SW", "7": "FB", "8": "COMP", "9": "GND", "11": "GND"})
    sh.C(c(1), "C2u2", "+24V", "GND")
    sh.C(c(2), "C100n", "+24V", "GND")
    sh.C(c(3), "C100n", "BOOT", "SW")
    sh.C(c(4), "C10n", "SS", "GND")
    sh.R(r(1), "R390k", "RT", "GND")
    sh.R(r(2), "R18k", "COMP", "COMPX")
    sh.C(c(5), "C15n", "COMPX", "GND")
    sh.C(c(6), "C47p", "COMP", "GND")
    sh.D(f"D{n+1}", "SS310", "SW", "GND")
    sh.L(f"L{n+1}", "L68u", "SW", "VO")
    sh.C(c(7), "C10u", "VO", "GND")
    sh.C(c(8), "C10u", "VO", "GND")

    sh.newrow()
    sh.group("Freigabe (Default AUS) - INA226-ALERT schaltet hart ab")
    sh.R(r(3), "R10k", f"EN{k}", "EN_N")
    sh.R(r(4), "R100k", "EN_N", "GND")

    sh.group("Spannungsregelung: Teiler + Sollwert-Einspeisung VSET")
    sh.R(r(5), "R200k", "BATI", "FB")
    sh.R(r(6), "R11k8", "FB", "GND")
    sh.R(r(7), "R100k", f"VSET{k}", "GND")
    sh.R(r(8), "R10k", f"VSET{k}", "VSF")
    sh.C(c(9), "C1u", "VSF", "GND")
    sh.R(r(9), "R330k", "VSF", "FB")

    sh.newrow()
    sh.group("Rueckspeisesperre, Shunt 50mR, Verpolschutz, Ausgang")
    sh.D(f"D{n+2}", "SS34", "SNP", "VO")
    sh.R(r(10), "Rsh", "SNP", "BATI")
    sh.part("Transistor_FET:AO3401A", f"Q{n+1}", "AO3407", {"1": "GATE", "2": "BATI", "3": "BATP"}, value="AO3407A")
    sh.R(r(11), "R10k", "GATE", "GND")
    sh.Z(f"D{n+3}", "Z12", "BATI", "GATE")
    sh.PTC(f"F{n+1}", "PTC", "BATP", "BAT+")
    sh.Z(f"D{n+4}", "TVS18", "BATP", "GND")
    sh.part("Connector_Generic:Conn_01x04", f"J{n+1}", "PH4",
            {"1": "BAT+", "2": "GND", "3": "ONEWIRE", "4": "+3V3"}, value=f"AKKU {k} + DS18B20")

    sh.newrow()
    a1, a0 = ADDR[k]
    sh.group(f"Messung INA226 (Adresse 0x{0x3F + k:02X})")
    sh.part("Sensor_Energy:INA226", f"U{n+2}", "INA226",
            {"1": a1, "2": a0, "3": "EN_N", "4": "SDA", "5": "SCL", "6": "+3V3", "7": "GND",
             "8": "BATI", "9": "BATI", "10": "SNP"})
    sh.C(c(10), "C100n", "+3V3", "GND")

    sh.group("Analoger Stromregler (2,5V/A, Integrator -> FB)")
    sh.part("Amplifier_Current:INA181", f"U{n+3}", "INA181",
            {"1": "ISN", "2": "GND", "3": "SNP", "4": "BATI", "5": "GND", "6": "+5V"}, value="INA181A2")
    sh.C(c(11), "C100n", "+5V", "GND")
    sh.R(r(12), "R1k", "ISN", "ISNF")
    sh.C(c(12), "C100n", "ISNF", "GND")
    sh.R(r(13), "R100k", f"ISET{k}", "GND")
    sh.R(r(14), "R10k", f"ISET{k}", "ISF")
    sh.C(c(13), "C1u", "ISF", "GND")
    sh.R(r(15), "R100k", "ISF", "OAN")
    sh.C(c(14), "C100n", "OAN", "OAOUT")
    sh.part("Amplifier_Operational:TLV9062", f"U{n+4}", "TLV9062",
            {"1": "OAOUT", "2": "OAN", "3": "ISNF"}, unit=1)
    sh.part("Amplifier_Operational:TLV9062", f"U{n+4}", "TLV9062",
            {"7": "OBOUT", "6": "OBOUT", "5": "GND"}, unit=2, record=False)
    sh.part("Amplifier_Operational:TLV9062", f"U{n+4}", "TLV9062",
            {"8": "+5V", "4": "GND"}, unit=3, record=False)
    sh.C(c(15), "C100n", "+5V", "GND")
    sh.D(f"D{n+5}", "BAT54", "OAD", "OAOUT")
    sh.R(r(16), "R100k", "OAD", "FB")

    sh.newrow()
    notes = [
        "Uout = 14,83V - 0,588 * U(VSET)   (U(VSET) = 0...3,3V  ->  14,83...12,89V; Feinabgleich per Firmware ueber INA226)",
        "I-Grenze: U(ISET) = 2,5V/A * I   (0,6A -> 1,5V) | Integrator 100k/100nF; bei I > Isoll speist U*4 ueber D/R in FB ein",
        "RT 390k -> 316kHz (RT=206033/f^1.0888) | Komp. 18k/15nF/47pF nach SLVSB56C 9.2.2.10: fc ca. 10kHz (zul. 4,1...15,9kHz bei 0,6A, Cout eff. 8uF)",
        "Q1 + D3: Verpolschutz Akku; F1 1,1A PTC; D4 TVS. EN_N: 100k Pull-down -> Kanal nach Reset AUS",
    ]
    for i, t in enumerate(notes):
        sh.text(t, 15, sh.cy + i * 5, 1.6)
    return sh

# ---------------------------------------------------------------- Ausgabe
def sheet_symbol(x, y, name, fname, page, su):
    w, h = 40.64, 15.24
    return [S("sheet"), [S("at"), x, y], [S("size"), w, h], [S("fields_autoplaced")],
            [S("stroke"), [S("width"), 0.1524], [S("type"), S("solid")]],
            [S("fill"), [S("color"), 0, 0, 0, 0.0]], [S("uuid"), su],
            [S("property"), "Sheetname", name, [S("at"), x, y - 0.7112, 0], eff(1.27, "left bottom")],
            [S("property"), "Sheetfile", fname, [S("at"), x, y + h + 0.5888, 0], eff(1.27, "left top")],
            [S("instances"), [S("project"), PROJECT, [S("path"), f"/{ROOT_UUID}", [S("page"), str(page)]]]]]

def write(path, sexp):
    with open(path, "w") as f:
        f.write(dump(sexp) + "\n")

def main():
    root = build_root()
    sheets, chans = [], []
    root.text("Ladekanaele (Hierarchieblaetter, Doppelklick zum Oeffnen):", 15, root.cy + 8, 2.2)
    for k in range(1, 7):
        su = U()
        ch = build_channel(k, su)
        chans.append(ch)
        sx = 15 + (k - 1) * 45
        sheets.append(sheet_symbol(sx, root.cy + 12, f"Ladekanal {k}", ch.fname, k + 1, su))
    write(os.path.join(OUT, root.fname), root.sexp(root=True, sheets=sheets))
    for ch in chans:
        write(os.path.join(OUT, ch.fname), ch.sexp())

    # Projektsymbol-Bibliothek
    lib = [S("kicad_symbol_lib"), [S("version"), 20220914], [S("generator"), S("kicad_symbol_editor")]]
    lib += [copy.deepcopy(CUSTOM[n]) for n in ("TPS54160A", "Q_NMOS_SO8")]
    write(os.path.join(OUT, f"{PROJECT}.kicad_sym"), lib)
    with open(os.path.join(OUT, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (lib (name "perinode24")(type "KiCad")(uri "${KIPRJMOD}/perinode24.kicad_sym")'
                '(options "")(descr "Projektsymbole Perinode24"))\n)\n')
    pro = os.path.join(OUT, f"{PROJECT}.kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w") as f:
            json.dump({"meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1},
                       "sheets": [[root.uuid, "Root"]] + [[s[6][1], f"Ladekanal {i+1}"] for i, s in enumerate(sheets)]},
                      f, indent=2)

    # Stückliste (JLCPCB-Format) – TLV9062 nur einmal je Kanal gezählt
    groups = defaultdict(list)
    for ref, key in BOM:
        groups[key].append(ref)
    def refkey(r):
        import re
        m = re.match(r"([A-Z]+)(\d+)", r)
        return (m.group(1), int(m.group(2)))
    with open(os.path.join(OUT, "bom_jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Menge", "LCSC geprueft"])
        for key in sorted(groups, key=lambda k: refkey(sorted(groups[k], key=refkey)[0])):
            val, fp, lcsc, mpn, ok = P[key]
            refs = sorted(groups[key], key=refkey)
            w.writerow([val, ",".join(refs), fp.split(":")[1], lcsc, mpn, len(refs), "ja" if ok else "NEIN"])
    print("Bauteile:", len(BOM), "| Positionen:", len(groups))

if __name__ == "__main__":
    main()
