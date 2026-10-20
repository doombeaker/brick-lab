"""Cross-project consistency check:
1) every mesh inside examples/* toy collections is the same local mesh as the
   corresponding unit in bricks/bricks.blend;
2) every part inside the example print 3MFs matches a (unit, rotation) from
   bricks.blend exactly (vertex set + surface area);
3) part counts agree with each project's BOM.md.
Run:  blender -b -P tools/check_consistency.py
"""
import bpy
import math
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
BRICKS = str(ROOT / "bricks" / "bricks.blend")
TOYS = [("warship", str(ROOT / "examples" / "warship"), "warship_print.3mf"),
        ("cottage", str(ROOT / "examples" / "cottage"), "cottage_print.3mf")]
UNITS = ["brick_1x1", "brick_1x2", "brick_2x2", "brick_2x4", "brick_2x6",
         "slope_2x2_45", "round_brick_1x1", "plate_1x2", "plate_2x2",
         "plate_2x4", "plate_2x6", "plate_4x8", "plate_8x8", "plate_6x12",
         "tile_2x2"]
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def clean(c):
    v = round(float(c), 5)
    return 0.0 if v == 0 else v


def vhash(coords):
    return tuple(sorted(tuple(clean(c) for c in p) for p in coords))


def mesh_sig(obj):
    me = obj.data
    me.calc_loop_triangles()
    verts = [tuple(v.co) for v in me.vertices]
    area = 0.0
    for t in me.loop_triangles:
        a, b, c = (me.vertices[i].co for i in t.vertices)
        area += (b - a).cross(c - a).length / 2.0
    return vhash(verts), round(area, 3), len(me.loop_triangles)


def tri_area(verts, tris):
    area = 0.0
    for a, b, c in tris:
        va, vb, vc = (Vector(verts[i]) for i in (a, b, c))
        area += (vb - va).cross(vc - va).length / 2.0
    return round(area, 3)


# ---------------- reference unit signatures from bricks.blend ----------------
bpy.ops.wm.open_mainfile(filepath=BRICKS)
REF = {}
for n in UNITS:
    o = bpy.data.objects[n]
    h, area, ntri = mesh_sig(o)
    co = [v.co for v in o.data.vertices]
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    ctr = (mn + mx) / 2
    variants = {}
    for rot in (0, 90, 180, 270):
        R = Matrix.Rotation(math.radians(rot), 3, "Z")
        coords = [R @ (c - ctr) for c in co]
        variants[vhash(coords)] = rot
    REF[n] = {"hash": h, "area": area, "tris": ntri, "variants": variants,
              "dims": (round(mx.x - mn.x, 2), round(mx.y - mn.y, 2),
                       round(mx.z - mn.z, 2))}
print(f"[bricks.blend] {len(UNITS)} units fingerprinted")


# ---------------- key clutch parameters (printed for the report) ----------------
def local_verts(n):
    return [v.co for v in bpy.data.objects[n].data.vertices]


def median(vals):
    vals = sorted(vals)
    return vals[len(vals) // 2] if vals else 0.0


def rads(verts, cx, cy, lo, hi, zmax=None):
    out = []
    for v in verts:
        r = math.hypot(v.x - cx, v.y - cy)
        if lo < r < hi and (zmax is None or v.z < zmax):
            out.append(r)
    return out


b1 = local_verts("brick_1x1")
cav1 = max(abs(v.x) for v in b1 if -3 < v.x < 3 and v.z < -2)
b12 = local_verts("brick_1x2")
cav12 = max(abs(v.x) for v in b12 if -3 < v.x < 3 and v.z < -2)
rd = local_verts("round_brick_1x1")
bore_round = median(rads(rd, 0, 0, 1.9, 2.5, 1.0))
sl = local_verts("slope_2x2_45")
bore_slope = median(rads(sl, 4, 4, 2.0, 2.4, 2.0))
tl = local_verts("tile_2x2")
pocket = median(rads(tl, 4, 4, 2.0, 2.4, 0.5))
b22 = local_verts("brick_2x2")
tube_brick = median(rads(b22, 4, 4, 2.2, 2.6, 2.0))
p48 = local_verts("plate_4x8")
tube_plate = median(rads(p48, 4, 4, 2.2, 2.6, 0.5))
print("[clutch params in bricks.blend]")
print(f"  brick_1x1 cavity      {2*cav1:.2f}")
print(f"  brick_1x2 cavity      {2*cav12:.2f}")
print(f"  round_1x1 bore        {2*bore_round:.2f}")
print(f"  slope tube bore       {2*bore_slope:.2f}")
print(f"  tile pocket           {2*pocket:.2f}")
print(f"  brick tube bore       {2*tube_brick:.2f}")
print(f"  plate tube bore       {2*tube_plate:.2f}")

all_ok = True

# ---------------- toy .blend meshes ----------------
for toy, d, _ in TOYS:
    bpy.ops.wm.open_mainfile(filepath=os.path.join(d, f"{toy}.blend"))
    coll = bpy.data.collections.get("Toy")
    counts = {}
    bad = []
    for o in coll.objects:
        base = re.sub(r"\.\d+$", "", o.name)
        if base not in REF:
            bad.append(f"unknown object {o.name}")
            continue
        h, area, ntri = mesh_sig(o)
        if h != REF[base]["hash"] or abs(area - REF[base]["area"]) > 0.01:
            bad.append(f"{o.name} differs from bricks.{base}")
        counts[base] = counts.get(base, 0) + 1
    total = sum(counts.values())
    print(f"\n[{toy}.blend] {total} parts in Toy collection, "
          f"{'all meshes identical to bricks.blend' if not bad else 'MISMATCH'}")
    for b in bad:
        print("   !!", b)
    all_ok &= not bad

    # compare with BOM.md
    bom = {}
    text = open(os.path.join(d, "BOM.md")).read()
    sec = text.split("## 按砖型汇总")[1]
    for line in sec.splitlines():
        m = re.match(r"\|\s*(\w+)\s*\|\s*(\d+)\s*\|", line)
        if m:
            bom[m.group(1)] = int(m.group(2))
    ok = bom == counts
    all_ok &= ok
    print(f"[{toy} BOM.md] {'counts match blend' if ok else 'COUNT MISMATCH'} "
          f"(total {sum(bom.values())})")
    if not ok:
        print("   blend:", counts)
        print("   bom  :", bom)

    # ---------------- toy 3MF parts ----------------
    z = zipfile.ZipFile(os.path.join(d, f"{toy}_print.3mf"))
    mcounts = {}
    unmatched = []
    for n in z.namelist():
        if not re.match(r"3D/Objects/object_\d+\.model$", n):
            continue
        r = ET.fromstring(z.read(n))
        vs = [(float(v.get("x")), float(v.get("y")), float(v.get("z")))
              for v in r.findall(".//m:vertex", NS)]
        tris = [(int(t.get("v1")), int(t.get("v2")), int(t.get("v3")))
                for t in r.findall(".//m:triangle", NS)]
        key = vhash(vs)
        area3 = tri_area(vs, tris)
        hit = None
        for unit, ref in REF.items():
            if key in ref["variants"] and abs(area3 - ref["area"]) <= max(0.05, ref["area"] * 0.002):
                hit = unit
                break
        if hit is None:
            unmatched.append(n)
        else:
            mcounts[hit] = mcounts.get(hit, 0) + 1
    ok = not unmatched and mcounts == counts
    all_ok &= ok
    print(f"[{toy}_print.3mf] {sum(mcounts.values())} parts match bricks geometry "
          f"({'OK' if ok else 'MISMATCH'})")
    if unmatched:
        print("   unmatched object files:", unmatched[:6])
        all_ok = False
    if mcounts != counts:
        print("   3mf per-unit:", mcounts)
        print("   blend per-unit:", counts)

print("\nCONSISTENCY " + ("PASSED" if all_ok else "FAILED"))
