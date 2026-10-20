"""Assembly verification v2: bbox-bottom placement (origins sit at body center,
so raw location offsets were sinking bricks into each other -> false collisions)."""
import bpy
import bmesh
import math
import os
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
BLEND = str(ROOT / "bricks.blend")
OUT = str(ROOT / "renders")
BH, PH, P = 9.6, 3.2, 8.0
CLUTCH = 0.3
STUD_OD = 4.8 - CLUTCH   # 4.5

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
_placed = []


def place(name, x, y, z_bottom):
    """Copy brick so its world bbox bottom-center lands at (x, y, z_bottom)."""
    src = bpy.data.objects[name]
    o = src.copy()
    o.data = src.data
    scene.collection.objects.link(o)
    bb = [src.matrix_world @ Vector(c) for c in src.bound_box]
    cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
    cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
    mz = min(v.z for v in bb)
    o.location = src.location + Vector((x - cx, y - cy, z_bottom - mz))
    _placed.append(o)
    return o


def mesh_volume(o):
    if not o.data.vertices:
        return 0.0
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def interference(top, bottom):
    ia = top.copy()
    ia.data = top.data.copy()
    scene.collection.objects.link(ia)
    mod = ia.modifiers.new("i", "BOOLEAN")
    mod.operation = "INTERSECT"
    mod.solver = "EXACT"
    mod.object = bottom
    bpy.context.view_layer.objects.active = ia
    ia.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    v = mesh_volume(ia)
    dz = 0.0
    if ia.data.vertices:
        zs = [(ia.matrix_world @ vv.co).z for vv in ia.data.vertices]
        dz = max(zs) - min(zs)
    bpy.data.objects.remove(ia, do_unlink=True)
    return v, dz


print("--- assembly tests (interference must be ~0) ---")
base = place("brick_2x4", 0, 0, 0)
plate_b = place("plate_2x4", 0, 0, BH)
tests = [
    ("brick_2x4  onto brick_2x4", place("brick_2x4", 0, 8, BH), base),
    ("plate_2x4  onto brick_2x4", place("plate_2x4", 0, 0, BH), base),
    ("brick_2x2  onto plate_2x4", place("brick_2x2", 0, 8, BH + PH), plate_b),
    ("brick_1x1  onto plate_2x4", place("brick_1x1", -4, -12, BH + PH), plate_b),
    ("slope_2x2  onto brick_2x4", place("slope_2x2_45", 0, -4, BH), base),
    ("round_1x1  onto brick_2x4", place("round_brick_1x1", 4, -12, BH), base),
    ("plate_1x2  onto brick_2x4", place("plate_1x2", -4, -8, BH), base),
]
PRESS_FIT = {"brick_1x1  onto plate_2x4", "brick_1x1 onto brick_1x1"}

all_ok = True
for label, top, bottom in tests:
    bpy.context.view_layer.update()
    v, dz = interference(top, bottom)
    if dz < 0.05:            # zero-thickness sheet = coplanar tangency, not overlap
        v = 0.0
    if label in PRESS_FIT:
        ok = 0.0005 < v < 8.0        # small intentional interference = clutch grip
        status = "PRESS-FIT" if ok else ("!! TOO LOOSE" if v <= 0.0005 else "!! TOO TIGHT")
    else:
        ok = v < 0.001
        status = "OK" if ok else "!! COLLISION"
    all_ok &= ok
    print(f"{label:30s} interference = {v:9.4f} mm^3   {status}")

# sanity that the detector works: slam brick 2mm down -> large overlap
bad = place("brick_2x4", 0, 8, BH - 2.0)
bpy.context.view_layer.update()
v, _ = interference(bad, base)
print(f"{'sanity: forced 2mm overlap':30s} interference = {v:9.1f} mm^3   "
      f"{'DETECTOR OK' if v > 100 else '!! detector broken'}")

# side-by-side neighbours
a = place("brick_1x1", 0, 0, 0)
b = place("brick_1x1", 8, 0, 0)
bpy.context.view_layer.update()
v, _ = interference(a, b)
all_ok &= v < 1e-4
print(f"{'brick_1x1 beside brick_1x1':30s} interference = {v:9.4f} mm^3   "
      f"{'OK' if v < 1e-4 else '!! TOUCHING'}")

# --- regressions from real print feedback ---
print("--- regression tests (print feedback) ---")
b22 = place("brick_2x2", 0, -100, 0)
sl = place("slope_2x2_45", 0, -100, BH)      # centred: front row relieved, back row clutched
bpy.context.view_layer.update()
v, _ = interference(sl, b22)
# print feedback: slope was too tight for a child -> clutch is now a clearance fit (ID 4.60)
sme = bpy.data.objects["slope_2x2_45"].data
rr = sorted(math.hypot(vv.co.x - 4, vv.co.y - 4) for vv in sme.vertices
            if vv.co.z < 2.0 and 2.0 < math.hypot(vv.co.x - 4, vv.co.y - 4) < 2.45)
bore = rr[len(rr) // 2] if rr else 0.0
ok = v < 0.001 and 2.26 <= bore <= 2.32
all_ok &= ok
print(f"{'slope_2x2 clutch (clearance)':30s} interference = {v:9.4f} mm^3, bore ID {2*bore:.2f}   "
      f"{'OK' if ok else '!! FAIL'}")

# round 1x1: two print rounds at 4.40/4.45 were both 'very hard' -> bore is now
# nominal line-to-line 4.65 (FDM shrink provides the actual light grip).
# Boolean volume is unreliable at this level -> geometric bore check like slope.
rme = bpy.data.objects["round_brick_1x1"]
robj_loc = rme.location
rbore = [vv.co.z for vv in rme.data.vertices
         if abs(math.hypot(vv.co.x, vv.co.y) - 2.33) < 0.02 and vv.co.z < 0]
ok = len(rbore) >= 32          # the 64-gon bore wall below the stud ring
print(f"{'round_1x1 bore (line-to-line)':30s} bore wall verts={len(rbore)}   "
      f"{'OK' if ok else '!! FAIL'}")
all_ok &= ok

s11 = place("brick_1x1", 60, -100, 0)
t11 = place("brick_1x1", 60, -100, BH)
bpy.context.view_layer.update()
v, _ = interference(t11, s11)
ok = 0.0005 < v < 8.0
all_ok &= ok
print(f"{'brick_1x1 onto brick_1x1':30s} interference = {v:9.4f} mm^3   "
      f"{'PRESS-FIT' if ok else ('!! TOO LOOSE' if v <= 0.0005 else '!! TOO TIGHT')}")

b22b = place("brick_2x2", 30, -100, 0)
tl = place("tile_2x2", 30, -100, BH)
bpy.context.view_layer.update()
# tile: thin 0.05mm ring booleans are numerically noisy -> verify by probing
def probe_void(obj, pt, size=0.4):
    bpy.ops.mesh.primitive_cube_add(size=size, location=pt)
    c = bpy.context.active_object
    m2 = c.modifiers.new("i", "BOOLEAN")
    m2.operation = "INTERSECT"
    m2.solver = "EXACT"
    m2.object = obj
    bpy.context.view_layer.objects.active = c
    c.select_set(True)
    bpy.ops.object.modifier_apply(modifier=m2.name)
    bm2 = bmesh.new()
    bm2.from_mesh(c.data)
    vol2 = bm2.calc_volume(signed=False) if len(bm2.verts) else 0.0
    bm2.free()
    bpy.data.objects.remove(c, do_unlink=True)
    return vol2 < 0.001

mw_t = tl.matrix_world
wall_verts = sum(1 for v in tl.data.vertices
                 if abs(math.hypot((mw_t @ v.co).x - 34, (mw_t @ v.co).y - (-96)) - 2.30) < 0.02)
pockets_void = all(probe_void(tl, (30 + dx, -100 + dy, 10.5)) for dx in (-4, 4) for dy in (-4, 4))
ok = pockets_void and wall_verts >= 30
all_ok &= ok
print(f"{'tile_2x2 on 2x2 (snap pockets)':30s} 4 studs void={pockets_void}, wall r2.30 verts={wall_verts}   "
      f"{'CLEARANCE-FIT' if ok else '!! FAIL'}")

# plates: footprint must be nx*8-0.2 and carry exactly nx*ny studs
PLATE_CHECKS = [("plate_1x2", 1, 2), ("plate_2x2", 2, 2), ("plate_2x4", 2, 4),
                ("plate_2x6", 2, 6), ("plate_4x8", 4, 8), ("plate_8x8", 8, 8),
                ("plate_6x12", 6, 12)]
for nm, nx, ny in PLATE_CHECKS:
    me_ = bpy.data.objects[nm].data
    xs = [v.co.x for v in me_.vertices]
    ys = [v.co.y for v in me_.vertices]
    zs = [v.co.z for v in me_.vertices]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    ztop = max(zs)
    tops = [v.co for v in me_.vertices if abs(v.co.z - ztop) < 0.01]
    studs = len(tops) // 48
    ok = (abs(dx - (nx * 8 - 0.2)) < 0.05 and abs(dy - (ny * 8 - 0.2)) < 0.05
          and studs == nx * ny)
    all_ok &= ok
    print(f"{nm:14s} {dx:5.2f} x {dy:5.2f} mm, studs {studs}/{nx * ny}   {'OK' if ok else '!! FAIL'}")

# single-row parts: 0.025mm/side slivers are below boolean resolution -> measure cavity
for nm, lo, hi in (("brick_1x2", 2.18, 2.235), ("plate_1x2", 2.36, 2.44)):
    me_ = bpy.data.objects[nm].data
    hw = max(abs(v.co.x) for v in me_.vertices if -3.0 < v.co.x < 3.0 and v.co.z < -0.5)
    ok = lo <= hw <= hi
    if nm == "brick_1x2":
        ok = ok and hw < STUD_OD / 2
    all_ok &= ok
    expect = 4.45 if nm == "brick_1x2" else 4.80
    print(f"{nm + ' cavity (single row)':30s} half-width = {hw:8.3f} mm (2x = {2*hw:.2f}, "
          f"expected {expect:.2f})   {'PRESS-FIT' if ok else '!! FAIL'}")

print(f"clearance: stud OD {STUD_OD:.2f} vs cavity/tube ID 4.80 -> play {4.8 - STUD_OD:.2f} mm "
      f"(1x1 cavity tightened to 4.40 -> press-fit -0.05/side)")
print("ALL ASSEMBLY TESTS PASSED" if all_ok else "SOME TESTS FAILED")

# ---------------- renders ----------------
# assembled group (verified pairs only) + free-standing slope for the look
for o in _placed:
    o.hide_render = False
group_members = [
    place("brick_2x4", 0, 0, 0),
    place("plate_2x4", 0, 0, BH),
    place("brick_2x2", 0, 8, BH + PH),
    place("brick_1x1", -4, -12, BH + PH),
    place("slope_2x2_45", -35, 0, 0),
    place("brick_2x2", 35, 0, 0),
    place("round_brick_1x1", 39, -4, BH),
]

cam = bpy.data.cameras.new("cam")
cam.type = "ORTHO"
cam.ortho_scale = 105
cam.clip_end = 5000
co = bpy.data.objects.new("cam", cam)
co.location = (70, -110, 70)
co.rotation_euler = (Vector((0, 0, 6)) - Vector(co.location)).to_track_quat("-Z", "Y").to_euler()
scene.collection.objects.link(co)
scene.camera = co
scene.render.resolution_x = 1000
scene.render.resolution_y = 700
scene.render.filepath = os.path.join(OUT, "assembly.png")
bpy.ops.render.render(write_still=True)
print("Rendered assembly")

# cutaway through assembly: drop everything except group A, cut y<0
keep = set(group_members[:4])
for o in group_members:
    if o not in keep:
        o.hide_render = True
bpy.context.view_layer.update()
bpy.ops.mesh.primitive_cube_add(size=400, location=(0, -200, 5))
half = bpy.context.active_object
for src in group_members[:4]:
    c = src.copy()
    c.data = src.data.copy()
    c.hide_render = False
    scene.collection.objects.link(c)
    mod = c.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = half
    bpy.context.view_layer.objects.active = c
    c.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(half, do_unlink=True)
for src in group_members[:4]:
    src.hide_render = True
scene.render.filepath = os.path.join(OUT, "assembly_cutaway.png")
bpy.ops.render.render(write_still=True)
print("Rendered cutaway")
print("DONE")
