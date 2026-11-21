"""Füllt die Zonen, exportiert DSN (Freerouting) und schreibt einen DRC-Bericht."""
import sys, pcbnew
fn = sys.argv[1]
b = pcbnew.LoadBoard(fn)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(fn, b)
pcbnew.ExportSpecctraDSN(b, fn.replace(".kicad_pcb", ".dsn"))
pcbnew.WriteDRCReport(b, sys.argv[2], pcbnew.EDA_UNITS_MILLIMETRES, True)
