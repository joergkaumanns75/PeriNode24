"""Spielt eine Freerouting-Session (.ses) in perinode24.kicad_pcb ein (eigener Parser, da
pcbnew.ImportSpecctraSES in KiCad 7 nur mit geöffneter GUI arbeitet), füllt die Zonen und
schreibt einen DRC-Bericht.
Aufruf: python3 tools/import_ses.py perinode24.kicad_pcb route.ses drc.rpt"""
import os, re, subprocess, sys
import pcbnew
sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, find, find1

def apply_ses(b, ses):
    """Ersetzt alle Leiterbahnen/Vias von Board b durch die Routen aus der SES-Datei."""
    s = parse(open(ses).read())
    routes = find1(s, "routes")
    res = find1(routes, "resolution")
    unit, per = str(res[1]), float(res[2])
    scale_nm = {"um": 1000.0, "mm": 1e6, "mil": 25400.0, "inch": 2.54e7}[unit] / per
    keep = set()
    for t in list(b.GetTracks()):
        if t.IsLocked():          # vorverlegte (fixierte) Leiterbahnen/Vias bleiben
            if t.GetClass() == "PCB_VIA":
                keep.add(("v", t.GetPosition().x, t.GetPosition().y))
            else:
                a, c = t.GetStart(), t.GetEnd()
                keep.add(("t", t.GetLayer(), min((a.x, a.y), (c.x, c.y)), max((a.x, a.y), (c.x, c.y))))
            continue
        b.Remove(t)
    layers = {b.GetLayerName(l): l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)}
    def pt(x, y):
        return pcbnew.VECTOR2I(int(round(float(x) * scale_nm)), int(round(-float(y) * scale_nm)))
    n_tr = n_via = 0
    for net in find(find1(routes, "network_out"), "net"):
        ni = b.FindNet(net[1])
        for w in find(net, "wire"):
            path = find1(w, "path")
            layer, width = layers[path[1]], int(round(float(path[2]) * scale_nm))
            coords = path[3:]
            pts = [pt(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
            for a, c in zip(pts, pts[1:]):
                if a == c or ("t", layer, min((a.x, a.y), (c.x, c.y)), max((a.x, a.y), (c.x, c.y))) in keep:
                    continue
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(a); t.SetEnd(c); t.SetWidth(width); t.SetLayer(layer); t.SetNet(ni)
                b.Add(t); n_tr += 1
        for v in find(net, "via"):
            m = re.search(r"_(\d+):(\d+)_um", v[1])
            dia, drill = (int(m.group(1)) * 1000, int(m.group(2)) * 1000) if m else (600000, 300000)
            if ("v", pt(v[2], v[3]).x, pt(v[2], v[3]).y) in keep:
                continue
            via = pcbnew.PCB_VIA(b)
            via.SetPosition(pt(v[2], v[3])); via.SetWidth(dia); via.SetDrill(drill)
            via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(ni)
            b.Add(via); n_via += 1
    return n_tr, n_via

if __name__ == "__main__":
    pcb, ses, rpt = [os.path.abspath(a) for a in sys.argv[1:4]]
    b = pcbnew.LoadBoard(pcb)
    n_tr, n_via = apply_ses(b, ses)
    pcbnew.SaveBoard(pcb, b)
    b = pcbnew.LoadBoard(pcb)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "set_netclasses.py")], check=True)
    b = pcbnew.LoadBoard(pcb)
    pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    print(f"Leiterbahnsegmente: {n_tr}, Vias: {n_via}")
