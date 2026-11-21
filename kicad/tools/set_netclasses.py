"""Schreibt Netzklassen und Regeln in perinode24.kicad_pro (nach jedem Speichern per pcbnew-API
erneut ausführen, da KiCad 7 headless die Projekteinstellungen zurücksetzt)."""
import json, os, sys
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "perinode24.kicad_pro")
j = json.load(open(p))
def cls(name, w, clr=0.2, via=0.6, drill=0.3):
    return {"name": name, "clearance": clr, "track_width": w, "via_diameter": via, "via_drill": drill,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
            "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)"}
pats = [("Power24", "+24V"), ("Power24", "/VIN_*"),
        ("Power", "/Ladekanal*/SW"), ("Power", "/Ladekanal*/VO"), ("Power", "/Ladekanal*/BATP"),
        ("Power", "/Ladekanal*/BAT+"), ("Power", "/SW5"), ("Power", "/USB_VBUS"),
        ("Sense", "/Ladekanal*/SNP"), ("Sense", "/Ladekanal*/BATI"),
        ("Supply", "GND"), ("Supply", "+5V"), ("Supply", "+3V3")]
j["net_settings"] = {"classes": [cls("Default", 0.25), cls("Supply", 0.3), cls("Sense", 0.3), cls("Power", 0.5),
                                 cls("Power24", 0.8)],
                     "meta": {"version": 3}, "net_colors": None, "netclass_assignments": None,
                     "netclass_patterns": [{"netclass": c, "pattern": q} for c, q in pats]}
r = j.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
r.update(min_clearance=0.15, min_track_width=0.12, min_via_diameter=0.45, min_through_hole_diameter=0.2,
         min_copper_edge_clearance=0.2, min_hole_to_hole=0.5, min_via_annular_width=0.1, min_hole_clearance=0.25)
json.dump(j, open(p, "w"), indent=2)
print("Netzklassen geschrieben:", p)
