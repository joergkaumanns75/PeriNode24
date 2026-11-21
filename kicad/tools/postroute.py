"""Nacharbeit nach Freerouting – mit KiCads eigener Kollisionsprüfung (GetEffectiveShape/Collide).

  1. +24V-Kupferfläche auf In2 (füllt den Raum zwischen den In2-Signalbahnen)
  2. offene GND-/+24V-Pads: Stichleitung nach außen + Via zur Fläche (GND -> In1, +24V -> In2),
     GND alternativ Stichleitung ins Thermal-Pad desselben Bauteils
  3. übrige offene Verbindungen: gerade / L-förmige Stichleitung auf F.Cu
  4. GND-Flächeninseln auf F.Cu/B.Cu ohne Via -> Via
  5. GND-Stitching-Vias im Raster, Vias ohne Anschluss entfernen
Aufruf: python3 tools/postroute.py board.kicad_pcb drc.rpt [--final]"""
import math, re, sys
import pcbnew

M, ToMM = pcbnew.FromMM, pcbnew.ToMM
V = pcbnew.VECTOR2I
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
CLR = M(0.2)
STUB_W = M(0.3)
VIA_D, VIA_DR = M(0.6), M(0.3)
HOLE_GAP = M(0.5)
EDGE = M(0.35)
PLANE = {"GND": pcbnew.In1_Cu, "+24V": pcbnew.In2_Cu}

class World:
    def __init__(self, b):
        self.b = b
        self.items = {l: [] for l in CU}     # Lage -> [(Netz, SHAPE)]
        self.holes = []                      # (VECTOR2I, Radius)
        for fp in b.GetFootprints():
            for p in fp.Pads():
                for l in CU:
                    if p.IsOnLayer(l) or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                        self.items[l].append((p.GetNetname(), p.GetEffectiveShape(l)))
                if p.GetDrillSize().x > 0:
                    self.holes.append((p.GetPosition(), p.GetDrillSize().x // 2))
        for t in b.GetTracks():
            self.add(t)
        self.areas = [z for z in b.Zones() if z.GetIsRuleArea()]
        for fp in b.GetFootprints():
            self.areas += [z for z in fp.Zones() if z.GetIsRuleArea()]
        e = b.GetBoardEdgesBoundingBox()
        self.edge = (e.GetLeft(), e.GetTop(), e.GetRight(), e.GetBottom())

    def add(self, t):
        if t.GetClass() == "PCB_VIA":
            for l in CU:
                self.items[l].append((t.GetNetname(), t.GetEffectiveShape(l)))
            self.holes.append((t.GetPosition(), t.GetDrillValue() // 2))
        else:
            self.items[t.GetLayer()].append((t.GetNetname(), t.GetEffectiveShape(t.GetLayer())))

    def free(self, shape, layer, net):
        return not any(n != net and s.Collide(shape, CLR) for n, s in self.items[layer])

    def in_board(self, p, r):
        x0, y0, x1, y1 = self.edge
        return x0 + EDGE + r < p.x < x1 - EDGE - r and y0 + EDGE + r < p.y < y1 - EDGE - r

    def via_ok(self, p, net):
        if not self.in_board(p, VIA_D // 2):
            return False
        if any((p - h).EuclideanNorm() - r - VIA_DR // 2 < HOLE_GAP for h, r in self.holes):
            return False
        for z in self.areas:
            if z.GetDoNotAllowVias() and z.Outline().Collide(p, VIA_D // 2 + M(0.05)):
                return False
        c = pcbnew.SHAPE_CIRCLE(p, VIA_D // 2)
        return all(self.free(c, l, net) for l in CU)

    def seg_ok(self, a, c, layer, net):
        if not (self.in_board(a, STUB_W // 2) and self.in_board(c, STUB_W // 2)):
            return False
        return self.free(pcbnew.SHAPE_SEGMENT(a, c, STUB_W), layer, net)

    def put_seg(self, a, c, layer, net):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(a); t.SetEnd(c); t.SetWidth(STUB_W); t.SetLayer(layer); t.SetNet(self.b.FindNet(net))
        self.b.Add(t); self.add(t)

    def put_via(self, p, net):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(p); v.SetWidth(VIA_D); v.SetDrill(VIA_DR); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(self.b.FindNet(net))
        self.b.Add(v); self.add(v)

    def path(self, a, c, layer, net):
        """gerade, L- oder 45°-Verbindung"""
        if self.seg_ok(a, c, layer, net):
            self.put_seg(a, c, layer, net); return True
        d = min(abs(c.x - a.x), abs(c.y - a.y))
        sx, sy = (1 if c.x > a.x else -1), (1 if c.y > a.y else -1)
        for m in (V(a.x, c.y), V(c.x, a.y), V(a.x + sx * d, a.y + sy * d), V(c.x - sx * d, c.y - sy * d)):
            if self.seg_ok(a, m, layer, net) and self.seg_ok(m, c, layer, net):
                self.put_seg(a, m, layer, net); self.put_seg(m, c, layer, net); return True
        return False

def unconnected(rpt):
    out = []
    for blk in open(rpt).read().split("[unconnected_items]")[1:]:
        ls = [l for l in blk.split("\n")[1:4] if "@(" in l]
        out.append(ls)
    return out

def escape_via(w, fp, pad, net):
    """Stichleitung vom Pad nach außen (vom Bauteilmittelpunkt weg) + Via"""
    c, fc = pad.GetPosition(), fp.GetPosition()
    dx, dy = c.x - fc.x, c.y - fc.y
    dirs = []
    if abs(dx) >= abs(dy):
        dirs = [(1 if dx > 0 else -1, 0), (1 if dx > 0 else -1, 1), (1 if dx > 0 else -1, -1), (0, 1), (0, -1)]
    else:
        dirs = [(0, 1 if dy > 0 else -1), (1, 1 if dy > 0 else -1), (-1, 1 if dy > 0 else -1), (1, 0), (-1, 0)]
    for L in [0.8 + 0.2 * k for k in range(12)]:
        for ux, uy in dirs:
            n = math.hypot(ux, uy)
            p = V(int(c.x + M(L) * ux / n), int(c.y + M(L) * uy / n))
            if w.via_ok(p, net) and w.seg_ok(c, p, pcbnew.F_Cu, net):
                w.put_seg(c, p, pcbnew.F_Cu, net); w.put_via(p, net)
                return True
    return False

def into_own_pad(w, fp, pad, net):
    """GND: Stichleitung zum nächstgelegenen Punkt eines anderen GND-Pads desselben Bauteils (Thermal-Pad)"""
    c = pad.GetPosition()
    for p2 in fp.Pads():
        if p2.GetNetname() != net or p2.GetNumber() == pad.GetNumber() or not p2.IsOnLayer(pcbnew.F_Cu):
            continue
        bb = p2.GetBoundingBox()
        q = V(min(max(c.x, bb.GetLeft() + M(0.15)), bb.GetRight() - M(0.15)),
              min(max(c.y, bb.GetTop() + M(0.15)), bb.GetBottom() - M(0.15)))
        if w.seg_ok(c, q, pcbnew.F_Cu, net):
            w.put_seg(c, q, pcbnew.F_Cu, net); return True
    return False

def fix_pads(w, rpt):
    b = w.b
    done, fail = 0, []
    for ls in unconnected(rpt):
        for l in ls:
            m = re.search(r"Pad (\S+) \[([^\]]+)\] of (\S+) on", l)
            if not m or m.group(2) not in PLANE:
                continue
            num, net, ref = m.groups()
            fp = b.FindFootprintByReference(ref)
            pad = next(p for p in fp.Pads() if p.GetNumber() == num)
            ok = (net == "GND" and into_own_pad(w, fp, pad, net)) or escape_via(w, fp, pad, net)
            done += ok
            if not ok:
                fail.append(f"{ref}.{num} {net}")
    return done, fail

def fix_pairs(w, rpt):
    b = w.b
    done, fail = 0, []
    for ls in unconnected(rpt):
        if len(ls) < 2:
            continue
        ms = [re.search(r"@\(([-\d.]+) mm, ([-\d.]+) mm\): (\w+).*?\[([^\]]+)\]", l) for l in ls[:2]]
        if not all(ms) or ms[0].group(4) in ("GND",) or "Zone" in (ms[0].group(3), ms[1].group(3)):
            continue
        net = ms[0].group(4)
        pa = V(M(float(ms[0].group(1))), M(float(ms[0].group(2))))
        pc = V(M(float(ms[1].group(1))), M(float(ms[1].group(2))))
        # Kandidaten: Pad-Mitten und Leiterbahnenden des Netzes nahe den gemeldeten Punkten
        pts = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == net and p.IsOnLayer(pcbnew.F_Cu):
                    pts.append(p.GetPosition())
        for t in b.GetTracks():
            if t.GetNetname() == net and t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.F_Cu:
                pts += [t.GetStart(), t.GetEnd()]
            if t.GetNetname() == net and t.GetClass() == "PCB_VIA":
                pts.append(t.GetPosition())
        A = sorted(pts, key=lambda p: (p - pa).EuclideanNorm())[:5]
        C = sorted(pts, key=lambda p: (p - pc).EuclideanNorm())[:5]
        cands = sorted(((p - q).EuclideanNorm(), p, q) for p in A for q in C if p != q)
        ok = any(d < M(10) and w.path(p, q, pcbnew.F_Cu, net) for d, p, q in cands)
        if not ok:                       # Lagenwechsel: Stich + Via an beiden Enden, Verbindung auf B.Cu/In2
            ok = via_hop(w, A[0], C[0], net)
        if not ok and net in PLANE:      # +24V: beide Enden per Via an die In2-Fläche
            ok = all(escape_point_via(w, p, net) for p in (A[0], C[0]))
        done += ok
        if not ok:
            fail.append(net)
    return done, fail

def via_spots(w, c, net, rmax=3.0):
    """mögliche Via-Positionen nahe Punkt c, mit freier F.Cu-Stichleitung dorthin"""
    out = []
    for L in [0.6 + 0.2 * k for k in range(int((rmax - 0.6) / 0.2) + 1)]:
        for k in range(16):
            a = math.pi * k / 8
            p = V(int(c.x + M(L) * math.cos(a)), int(c.y + M(L) * math.sin(a)))
            if w.via_ok(p, net) and w.seg_ok(c, p, pcbnew.F_Cu, net):
                out.append(p)
        if len(out) >= 6:
            break
    return out

def via_hop(w, a, c, net):
    """a -> Via -> (B.Cu oder In2) -> Via -> c"""
    for va in via_spots(w, a, net):
        for vc in via_spots(w, c, net):
            for layer in (pcbnew.B_Cu, pcbnew.In2_Cu):
                if (va - vc).EuclideanNorm() > M(25):
                    continue
                # Probelauf ohne Einfügen: gerade/L prüfen
                cands = [[va, vc], [va, V(va.x, vc.y), vc], [va, V(vc.x, va.y), vc]]
                for pts in cands:
                    if all(w.seg_ok(p, q, layer, net) for p, q in zip(pts, pts[1:])):
                        # Via-Positionen müssen sich gegenseitig vertragen
                        if (va - vc).EuclideanNorm() < VIA_D + CLR + HOLE_GAP:
                            continue
                        w.put_seg(a, va, pcbnew.F_Cu, net); w.put_via(va, net)
                        w.put_seg(c, vc, pcbnew.F_Cu, net); w.put_via(vc, net)
                        for p, q in zip(pts, pts[1:]):
                            w.put_seg(p, q, layer, net)
                        return True
    return False

def escape_point_via(w, c, net):
    for L in [0.6 + 0.2 * k for k in range(12)]:
        for k in range(8):
            a = math.pi * k / 4
            p = V(int(c.x + M(L) * math.cos(a)), int(c.y + M(L) * math.sin(a)))
            if w.via_ok(p, net) and w.seg_ok(c, p, pcbnew.F_Cu, net):
                w.put_seg(c, p, pcbnew.F_Cu, net); w.put_via(p, net); return True
    return False

def islands(w):
    n = 0
    for z in w.b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND" or z.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for i in range(polys.OutlineCount()):
            ol = polys.Outline(i)
            if any(ol.PointInside(h) for h, r in w.holes):
                continue
            bb = ol.BBox()
            done = False
            y = bb.GetTop() + M(0.4)
            while y < bb.GetBottom() - M(0.4) and not done:
                x = bb.GetLeft() + M(0.4)
                while x < bb.GetRight() - M(0.4):
                    p = V(x, y)
                    if all(ol.PointInside(V(x + dx, y + dy)) for dx, dy in ((0, 0), (M(.35), 0), (-M(.35), 0), (0, M(.35)), (0, -M(.35)))) \
                            and w.via_ok(p, "GND"):
                        w.put_via(p, "GND"); n += 1; done = True; break
                    x += M(0.25)
                y += M(0.25)
    return n

def grid(w, step=5.0):
    zs = {l: [z for z in w.b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND" and z.GetLayer() == l]
          for l in (pcbnew.F_Cu, pcbnew.B_Cu)}
    x0, y0, x1, y1 = w.edge
    n = 0
    y = y0 + M(2.5)
    while y < y1 - M(2):
        x = x0 + M(2.5)
        while x < x1 - M(2):
            p = V(x, y)
            if all(any(z.HitTestFilledArea(l, p, M(0.5)) for z in zs[l]) for l in zs) and \
                    all((p - h).EuclideanNorm() > M(2.5) for h, r in w.holes) and w.via_ok(p, "GND"):
                w.put_via(p, "GND"); n += 1
            x += M(step)
        y += M(step)
    return n

def remove_dangling(b):
    ends = {}
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            for e in (t.GetStart(), t.GetEnd()):
                ends.setdefault((e.x, e.y), set()).add(t.GetLayer())
    n = 0
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() not in PLANE]:
        p = v.GetPosition()
        if len(ends.get((p.x, p.y), set())) < 2:
            b.Remove(v); n += 1
    return n

def add_in2_pour(b):
    if any(z.GetLayer() == pcbnew.In2_Cu and not z.GetIsRuleArea() for z in b.Zones()):
        return
    x0, y0, x1, y1 = (lambda e: (e.GetLeft(), e.GetTop(), e.GetRight(), e.GetBottom()))(b.GetBoardEdgesBoundingBox())
    z = pcbnew.ZONE(b); z.SetLayer(pcbnew.In2_Cu); z.SetNet(b.FindNet("+24V"))
    z.SetLocalClearance(M(0.3)); z.SetMinThickness(M(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline(); ol.NewOutline()
    for x, y in ((x0 + M(.5), y0 + M(.5)), (x1 - M(.5), y0 + M(.5)), (x1 - M(.5), y1 - M(.5)), (x0 + M(.5), y1 - M(.5))):
        ol.Append(int(x), int(y))
    b.Add(z)

def main():
    pcb, rpt = sys.argv[1:3]
    b = pcbnew.LoadBoard(pcb)
    add_in2_pour(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    w = World(b)
    d, f = fix_pads(w, rpt); print(f"Pads an Fläche angebunden: {d}", ("nicht: " + ", ".join(f)) if f else "")
    d, f = fix_pairs(w, rpt); print(f"Lücken geschlossen: {d}", ("nicht: " + ", ".join(f)) if f else "")
    if "--final" in sys.argv:
        print("Vias ohne Anschluss entfernt:", remove_dangling(b))
        pcbnew.SaveBoard(pcb, b)
        b = pcbnew.LoadBoard(pcb); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); w = World(b)
        print("Insel-Vias:", islands(w))
        print("Raster-Stitching-Vias:", grid(w))
    pcbnew.SaveBoard(pcb, b)

if __name__ == "__main__":
    main()
