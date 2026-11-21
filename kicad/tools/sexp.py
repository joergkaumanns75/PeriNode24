"""Minimaler S-Expression-Parser/Writer für KiCad-Dateien."""
import re

class Sym(str):
    pass

_tok = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')

def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = _tok.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        lp, rp, s, atom = m.groups()
        if lp:
            stack.append(cur); cur = []
        elif rp:
            done = cur; cur = stack.pop(); cur.append(done)
        elif s is not None:
            cur.append(s[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(atom))
    return cur[0] if len(cur) == 1 else cur

def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

def dump(e, ind=0):
    if isinstance(e, list):
        if not e:
            return "()"
        simple = all(not isinstance(x, list) for x in e)
        if simple:
            return "(" + " ".join(dump(x) for x in e) + ")"
        out = "(" + dump(e[0])
        for x in e[1:]:
            if isinstance(x, list):
                out += "\n" + "  " * (ind + 1) + dump(x, ind + 1)
            else:
                out += " " + dump(x)
        return out + ")"
    if isinstance(e, Sym):
        return str(e)
    if isinstance(e, (int, float)):
        return fmt(e)
    return q(e)

def fmt(v):
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"

def find(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]

def find1(e, key):
    r = find(e, key)
    return r[0] if r else None
