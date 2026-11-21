"""Ersetzt die (einzige) Netzklasse im KiCad-7-DSN-Export durch die Projekt-Netzklassen
(KiCad 7 exportiert Muster-basierte Netzklassen nicht). Breiten/Abstände in µm."""
import fnmatch, json, re, sys
dsn, pro, out = sys.argv[1:4]
# Netze, die Freerouting ignorieren soll; "GND:U" = GND nur für Pins von Bauteilen U* behalten
skip, keep_prefix = set(), {}
for item in (sys.argv[4].split(",") if len(sys.argv) > 4 else []):
    name, _, pref = item.partition(":")
    (keep_prefix.__setitem__(name, pref) if pref else skip.add(name))
t = open(dsn).read()
ns = json.load(open(pro))["net_settings"]
cls = {c["name"]: c for c in ns["classes"]}
pats = [(p["netclass"], p["pattern"]) for p in ns["netclass_patterns"]]
# alle exportierten Klassen einsammeln (KiCad exportiert je nach Zustand eine oder mehrere)
nets = []
for m in re.finditer(r'\(class (?:"[^"]*"|\S+)(.*?)\(circuit', t, re.S):
    nets += [n for n in re.findall(r'"[^"]*"|[^\s"]+', m.group(1)) if n != '""']
groups = {}
for n in nets:
    name = n.strip('"')
    if name in skip:
        continue
    c = next((c for c, p in pats if fnmatch.fnmatchcase(name, p)), "Default")
    groups.setdefault(c, []).append(n)
start = t.index("(class ")
end = t.index("(wiring")
end = t.rfind(")", 0, end)        # schließende Klammer von (network ...)
via = re.search(r'\(use_via ([^)]*)\)', t).group(1)
blk = ""
for c, ns_ in groups.items():
    w, clr = cls[c]["track_width"] * 1000, cls[c]["clearance"] * 1000
    body = " ".join(ns_)
    blk += f'(class {c} {body}\n      (circuit (use_via {via}))\n      (rule (width {w:.0f}) (clearance {clr + 0.1:.1f}))\n    )\n    '
t = t[:start] + blk + t[end:]
for name, pref in keep_prefix.items():   # Pinliste des Netzes auf Bauteile mit Präfix reduzieren
    def red(m):
        pins = [p for p in m.group(2).split() if p.startswith(pref)]
        return m.group(1) + " ".join(pins) + ")"
    t = re.sub(r'(\(net "?' + re.escape(name) + r'"?\s*\n\s*\(pins )([^)]*)\)', red, t)
for name in skip:   # Netzdefinition entfernen (Pads bleiben als Hindernisse erhalten)
    t = re.sub(r'\n\s*\(net "?' + re.escape(name) + r'"?\s*\n\s*\(pins[^)]*\)\s*\)', '', t)
    # die Fläche (plane) bleibt erhalten: sie hält die Lage für Freerouting als Versorgungslage gesperrt
open(out, "w").write(t)
print({c: len(v) for c, v in groups.items()})
