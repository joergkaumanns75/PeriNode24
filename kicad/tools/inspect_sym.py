import sys, glob
sys.path.insert(0, __import__('os').path.dirname(__file__))
from sexp import parse, find, find1
LIB = "/usr/share/kicad/symbols"
_cache = {}
def lib(name):
    if name not in _cache:
        _cache[name] = parse(open(f"{LIB}/{name}.kicad_sym").read())
    return _cache[name]
def get(libid):
    l, n = libid.split(":")
    for s in find(lib(l), "symbol"):
        if s[1] == n:
            return s
    raise KeyError(libid)
def pins(sym):
    out = []
    def walk(e):
        for x in e:
            if isinstance(x, list) and x:
                if x[0] == "pin":
                    at = find1(x, "at"); nm = find1(x, "name"); nu = find1(x, "number"); ln = find1(x, "length")
                    out.append((nu[1], nm[1], str(x[1]), float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, float(ln[1])))
                else:
                    walk(x)
    walk(sym)
    return out
if __name__ == "__main__":
    for a in sys.argv[1:]:
        s = get(a)
        ext = find1(s, "extends")
        props = {p[1]: p[2] for p in find(s, "property")}
        print("==", a, "extends", ext[1] if ext else "-", "| FP:", props.get("Footprint"))
        for p in sorted(pins(s), key=lambda p: (len(p[0]), p[0])):
            print("  ", p)
