"""Kleiner A*-Labyrinth-Router für die letzten offenen Verbindungen (F.Cu/B.Cu mit Vias).
Belegung je Rasterpunkt über KiCads Kollisionsprüfung (GetEffectiveShape/Collide)."""
import heapq, math, re, sys
import pcbnew
import postroute
postroute.STUB_W = postroute.M(0.25)     # schmalere Bahnen passen zwischen 0,5-mm-Pins
from postroute import World, unconnected, M, V, VIA_D, CLR
STUB_W = postroute.STUB_W

STEP = M(0.1)
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
VIA_COST = 40

def route(w, net, starts, goals, margin=4.0):
    xs = [p.x for p in starts + goals]; ys = [p.y for p in starts + goals]
    x0, y0 = min(xs) - M(margin), min(ys) - M(margin)
    nx = int((max(xs) + M(margin) - x0) / STEP) + 1
    ny = int((max(ys) + M(margin) - y0) / STEP) + 1
    win = pcbnew.BOX2I(V(x0, y0), V(nx * STEP, ny * STEP))
    local = {l: [(n, s) for n, s in w.items[l] if n != net and s.BBox().Intersects(win)] for l in LAYERS}
    cache = {}
    def free(i, j, li):
        k = (i, j, li)
        if k not in cache:
            p = V(x0 + i * STEP, y0 + j * STEP)
            c = pcbnew.SHAPE_CIRCLE(p, STUB_W // 2)
            cache[k] = w.in_board(p, STUB_W // 2) and not any(s.Collide(c, CLR) for n, s in local[LAYERS[li]])
        return cache[k]
    vcache = {}
    def via(i, j):
        if (i, j) not in vcache:
            vcache[(i, j)] = w.via_ok(V(x0 + i * STEP, y0 + j * STEP), net)
        return vcache[(i, j)]
    def idx(p):
        return (round((p.x - x0) / STEP), round((p.y - y0) / STEP))
    goalset = {idx(g) for g in goals}
    gi = [idx(g) for g in goals]
    h = lambda i, j: min(math.hypot(i - a, j - b) for a, b in gi)
    pq, came, cost = [], {}, {}
    for s in starts:
        i, j = idx(s)
        st = (i, j, 0)
        cost[st] = 0; came[st] = None
        heapq.heappush(pq, (h(i, j), 0, st))
    moves = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    end = None
    n_exp = 0
    while pq and n_exp < 400000:
        f, g, cur = heapq.heappop(pq)
        if g > cost.get(cur, 1e18):
            continue
        n_exp += 1
        i, j, li = cur
        if li == 0 and (i, j) in goalset:
            end = cur; break
        nb = []
        for di, dj, c in moves:
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and ((a, b) in goalset and li == 0 or free(a, b, li)):
                nb.append(((a, b, li), c))
        if len(LAYERS) > 1 and via(i, j):
            nb.append(((i, j, 1 - li), VIA_COST))
        for nxt, c in nb:
            ng = g + c
            if ng < cost.get(nxt, 1e18):
                cost[nxt] = ng; came[nxt] = cur
                heapq.heappush(pq, (ng + h(nxt[0], nxt[1]), ng, nxt))
    if not end:
        return None
    path = []
    while end:
        path.append(end); end = came[end]
    path.reverse()
    return [(V(x0 + i * STEP, y0 + j * STEP), li) for i, j, li in path]

def commit(w, net, path):
    # Punkte zu Segmenten zusammenfassen (Richtungswechsel / Lagenwechsel)
    segs, vias = [], []
    start = path[0]
    prev = path[0]
    prevdir = None
    for k in range(1, len(path)):
        p, l = path[k]
        if l != prev[1]:
            if start[0] != prev[0]:
                segs.append((start[0], prev[0], LAYERS[prev[1]]))
            vias.append(prev[0]); start = (p, l); prev = (p, l); prevdir = None
            continue
        d = (p.x - prev[0].x, p.y - prev[0].y)
        if prevdir is not None and d != prevdir:
            segs.append((start[0], prev[0], LAYERS[prev[1]])); start = prev
        prevdir = d; prev = (p, l)
    if start[0] != prev[0]:
        segs.append((start[0], prev[0], LAYERS[prev[1]]))
    for a, c, l in segs:
        w.put_seg(a, c, l, net)
    for p in vias:
        w.put_via(p, net)
    return len(segs), len(vias)

def anchors(b, net, layer=pcbnew.F_Cu):
    pts = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net and p.IsOnLayer(layer):
                pts.append(p.GetPosition())
    for t in b.GetTracks():
        if t.GetNetname() == net:
            if t.GetClass() == "PCB_VIA":
                pts.append(t.GetPosition())
            elif t.GetLayer() == layer:
                pts += [t.GetStart(), t.GetEnd()]
    return pts

def main(pcb, rpt):
    b = pcbnew.LoadBoard(pcb)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    w = World(b)
    ok = 0
    for ls in unconnected(rpt):
        if len(ls) < 2:
            continue
        ms = [re.search(r"@\(([-\d.]+) mm, ([-\d.]+) mm\): (\w+).*?\[([^\]]+)\]", l) for l in ls[:2]]
        if not all(ms):
            continue
        net = ms[0].group(4)
        pa = V(M(float(ms[0].group(1))), M(float(ms[0].group(2))))
        pc = V(M(float(ms[1].group(1))), M(float(ms[1].group(2))))
        if net == "GND":
            # Ziel: beliebiges GND-Via/-Pad in der Nähe (nicht das eigene Pad)
            src = pa if ms[0].group(3) == "Pad" else pc
            goals = [p for p in anchors(b, "GND") if 0 < (p - src).EuclideanNorm() < M(8) and (p - src).EuclideanNorm() > M(0.4)]
            starts = [src]
        else:
            pts = anchors(b, net)
            starts = [p for p in pts if (p - pa).EuclideanNorm() < M(0.8)] or [pa]
            goals = [p for p in pts if (p - pc).EuclideanNorm() < M(0.8)] or [pc]
        if not goals:
            print("kein Ziel:", net); continue
        path = route(w, net, starts, goals)
        if path:
            s, v = commit(w, net, path); ok += 1
            print(f"geroutet: {net}  ({s} Segmente, {v} Vias)")
        else:
            print("kein Weg:", net)
    pcbnew.SaveBoard(pcb, b)
    print("Labyrinth-Router: verbunden", ok)

if __name__ == "__main__":
    main(*sys.argv[1:3])
