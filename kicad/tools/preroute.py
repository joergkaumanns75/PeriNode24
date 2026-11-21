"""Vor dem Autorouting: kritische Anschlüsse fein gerasterter ICs selbst verlegen
(Stichleitung + Via zur Fläche), damit der Autorouter sie nicht zubaut.
  TPS54160A (U?01): Pin 2 VIN -> Via (+24V, Fläche In2); Pin 9 GND -> Thermal-Pad
  INA226   (U?02): Pin 7 GND -> Via (GND, In1)
  INA181   (U?03): Pin 2, 5 GND -> Via (GND, In1)
Aufruf: python3 tools/preroute.py board.kicad_pcb"""
import sys
import pcbnew
from postroute import World, escape_via, into_own_pad

TARGETS = [("01", "2"), ("01", "9"), ("02", "7"), ("03", "2"), ("03", "5")]

def main(pcb):
    b = pcbnew.LoadBoard(pcb)
    w = World(b)
    ok, fail = 0, []
    for k in range(1, 7):
        for suf, num in TARGETS:
            ref = f"U{k}{suf}"
            fp = b.FindFootprintByReference(ref)
            pad = next(p for p in fp.Pads() if p.GetNumber() == num)
            net = pad.GetNetname()
            done = (net == "GND" and into_own_pad(w, fp, pad, net)) or escape_via(w, fp, pad, net)
            ok += done
            if not done:
                fail.append(f"{ref}.{num}")
    for t in b.GetTracks():
        t.SetLocked(True)
    pcbnew.SaveBoard(pcb, b)
    print(f"vorverlegt: {ok}", ("nicht: " + ", ".join(fail)) if fail else "")

if __name__ == "__main__":
    main(sys.argv[1])
