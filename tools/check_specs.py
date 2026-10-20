"""Validate bricks/bricks.json against the actual geometry in bricks.blend.

Measurements are taken from the mesh, so this catches drift between the
documented specs and the generated units.

Run:  blender -b -P tools/check_specs.py
"""
import bpy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "bricks" / "bricks.json").read_text())

bpy.ops.wm.open_mainfile(filepath=str(ROOT / "bricks" / "bricks.blend"))

def verts(name):
    return [v.co.copy() for v in bpy.data.objects[name].data.vertices]

def median(vals):
    vals = sorted(vals)
    return vals[len(vals) // 2] if vals else 0.0

def rads(vs, cx, cy, lo, hi, zmax):
    out = []
    for v in vs:
        r = math.hypot(v.x - cx, v.y - cy)
        if lo < r < hi and v.z < zmax:
            out.append(r)
    return out

ok_all = True
for name, spec in SPEC["units"].items():
    if name not in bpy.data.objects:
        print(f"{name:16s} MISSING in bricks.blend")
        ok_all = False
        continue
    vs = verts(name)
    xs = [v.x for v in vs]; ys = [v.y for v in vs]; zs = [v.z for v in vs]
    dx = max(xs) - min(xs); dy = max(ys) - min(ys); dz = max(zs) - min(zs)
    exp_dx = spec["nx"] * SPEC["constants"]["pitch_mm"] - SPEC["constants"]["gap_mm"]
    exp_dy = spec["ny"] * SPEC["constants"]["pitch_mm"] - SPEC["constants"]["gap_mm"]
    # slope loses 0.05 mm in Y because of its raked plane
    tol_y = 0.06 if name.startswith("slope") else 0.02
    dims_ok = abs(dx - exp_dx) < 0.02 and abs(dy - exp_dy) < tol_y and abs(dz - spec["total_height_mm"]) < 0.02

    top = [v for v in vs if abs(v.z - max(zs)) < 0.01]
    studs = len(top) // 48 if spec["studs"] else 0
    studs_ok = studs == spec["studs"]

    kind = spec["clutch"]["kind"]
    nominal = spec["clutch"]["size_mm"]
    if kind == "cavity":
        half = max(abs(v.x) for v in vs if -3 < v.x < 3 and v.z < -0.5)
        measured = 2 * half
    elif kind == "bore":
        measured = 2 * median([r for r in (math.hypot(v.x, v.y) for v in vs) if 1.9 < r < 2.5])
    elif kind in ("tube_bore", "pocket"):
        cx = -(spec["nx"] - 1) * 4.0
        cy = (spec["ny"] - 1) * 4.0 if name.startswith("slope") else -(spec["ny"] - 1) * 4.0
        hi, zmax = (2.6, 2.0) if kind == "tube_bore" else (2.4, 0.5)
        measured = 2 * median(rads(vs, cx, cy, 2.0, hi, zmax))
    else:
        measured = 0.0
    clutch_ok = abs(measured - nominal) < 0.04
    ok = dims_ok and studs_ok and clutch_ok
    ok_all &= ok
    print(f"{name:16s} {dx:5.2f}x{dy:5.2f}x{dz:5.2f}  studs {studs:2d}/{spec['studs']:<2d}  "
          f"{kind} {measured:.2f}/{nominal:.2f}  {'OK' if ok else '!! MISMATCH'}")

print("SPECS " + ("PASSED" if ok_all else "FAILED"))
