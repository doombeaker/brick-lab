import bpy
import bmesh
import math
import os
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
BLEND_PATH = str(ROOT / "bricks.blend")
OUT_DIR = str(ROOT / "renders")
EXP_DIR = str(ROOT / "exports")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(EXP_DIR, exist_ok=True)

# LEGO nominal dims (mm). Scene unit = 1 mm.
P = 8.0        # stud pitch
GAP = 0.2      # per-side mold tolerance (7.8mm per stud of width)
WALL = 1.5     # underside wall thickness
STUD_R, STUD_H = 2.4, 1.8
CLUTCH = 0.3          # diametral print clearance: holes stay nominal 4.8, studs shrink
STUD_R_EFF = STUD_R - CLUTCH / 2   # -> OD 4.5 for FDM; use 0.15-0.2 for resin
BRICK_H, PLATE_H = 9.6, 3.2

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def mat(name, rgb, rough=0.35):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = 0.0
    return m


COLORS = {
    "red": mat("red", (0.788, 0.102, 0.035)),
    "blue": mat("blue", (0.0, 0.333, 0.749)),
    "yellow": mat("yellow", (0.949, 0.804, 0.216)),
    "green": mat("green", (0.137, 0.471, 0.255)),
    "orange": mat("orange", (0.996, 0.541, 0.094)),
    "azure": mat("azure", (0.212, 0.682, 0.749)),
    "white": mat("white", (0.957, 0.957, 0.957)),
    "black": mat("black", (0.106, 0.165, 0.204)),
    "purple": mat("purple", (0.35, 0.20, 0.50)),
}

bricks_col = bpy.data.collections.new("Bricks")
scene.collection.children.link(bricks_col)
units = []


def apply_bool(target, cutter, op="DIFFERENCE"):
    mod = target.modifiers.new("b", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def add_profile_wedge(name, x_half, pts_yz, m):
    """Closed prism from a YZ polygon extruded along X (for the slope cavity)."""
    bm = bmesh.new()
    l0 = [bm.verts.new((-x_half, y, z)) for (y, z) in pts_yz]
    l1 = [bm.verts.new((x_half, y, z)) for (y, z) in pts_yz]
    bm.faces.new(l0)
    bm.faces.new(l1)
    n = len(pts_yz)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((l0[i], l0[j], l1[j], l1[i]))
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # manual winding can be inconsistent
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    return o


def add_prism_xz(name, pts_xz, y_half):
    """Closed prism from an XZ polygon extruded along Y (for the roof ridge)."""
    bm = bmesh.new()
    l0 = [bm.verts.new((x, -y_half, z)) for (x, z) in pts_xz]
    l1 = [bm.verts.new((x, y_half, z)) for (x, z) in pts_xz]
    bm.faces.new(l0)
    bm.faces.new(l1)
    n = len(pts_xz)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((l0[i], l0[j], l1[j], l1[i]))
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    return o


def _bevel(body, width=0.15, segments=2):
    b = body.modifiers.new("Bevel", "BEVEL")
    b.width = width
    b.segments = segments
    b.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=b.name)


def _pocket(body, x, y, depth=2.4, zc=0.7):
    """Blind stud pocket in a solid body (tiles, ridge, window frame)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=STUD_R - 0.10, depth=depth,
                                        location=(x, y, zc))
    apply_bool(body, bpy.context.active_object)


def _studs(body, positions, h):
    parts = [body]
    for (xx, yy) in positions:
        # sink 0.1 into the body: a coplanar bottom cap z-fights with the top face
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=STUD_R_EFF, depth=STUD_H + 0.2,
                                            location=(xx, yy, h + STUD_H / 2 - 0.1))
        parts.append(bpy.context.active_object)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()


def finish(body, name, m, h, centered=True):
    # same local frame as make_unit: mesh centred on the origin, object at h/2.
    # Prisms built from absolute vertices (ridge) still need the shift.
    if not centered:
        body.data.transform(Matrix.Translation((0, 0, -h / 2)))
    body.location = (0, 0, h / 2)
    body.name = name
    body.data.materials.clear()
    body.data.materials.append(m)
    for p in body.data.polygons:
        p.material_index = 0
    for c in body.users_collection:
        c.objects.unlink(body)
    bricks_col.objects.link(body)
    units.append(body)
    return body


def make_ridge(name, nx, ny, m):
    """Double convex 45deg roof ridge: ridge line along Y at the brick top,
    faces fall to a 1.7 mm skirt at both eaves. Solid body + blind pockets:
    clutch tubes would break through the sloped walls."""
    w, d = nx * P - GAP, ny * P - GAP
    hx = w / 2
    skirt = BRICK_H - hx          # 45deg face reaches the top after hx of run
    pts = [(-hx, 0.0), (hx, 0.0), (hx, skirt), (0.0, BRICK_H), (-hx, skirt)]
    body = add_prism_xz(name, pts, d / 2)
    # no bevel: the angle-limited bevel would shave the ridge line below 9.6
    for yy in [-(ny - 1) * P / 2 + i * P for i in range(ny)]:
        for xx in [-(nx - 1) * P / 2 + i * P for i in range(nx)]:
            _pocket(body, xx, yy)
    return finish(body, name, m, BRICK_H, centered=False)


def make_arch(name, nx, ny, m, opening=2):
    """Brick arch: semicircular opening `opening` studs wide through the 7.8 mm
    thickness, crown 1.6 mm below the brick top. Solid legs with blind pockets
    (only the end studs sit over material)."""
    w, d = nx * P - GAP, ny * P - GAP
    r = opening * P / 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, BRICK_H / 2))
    body = bpy.context.active_object
    body.name = name
    body.data.transform(Matrix.Diagonal((w, d, BRICK_H, 1.0)))
    _bevel(body)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=r, depth=w + 4,
                                        location=(0, 0, 0),
                                        rotation=(0, math.radians(90), 0))
    apply_bool(body, bpy.context.active_object)
    xs = [-(nx - 1) * P / 2 + i * P for i in range(nx)]
    ys = [-(ny - 1) * P / 2 + i * P for i in range(ny)]
    # leg cavities follow the 1xN brick rule (wall 1.5, 4.45 press-fit cavity,
    # ceiling 8.1) instead of blind pockets: the legs are 1x1 columns and stay
    # clear of the arch tunnel, so the piece grips like brick_1x4
    wall = WALL
    mouth = -0.5
    ch = BRICK_H - wall - mouth
    zc = (BRICK_H - wall + mouth) / 2
    for yy in (ys[0], ys[-1]):      # only the end studs sit over material
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, yy, zc))
        c = bpy.context.active_object
        c.data.transform(Matrix.Diagonal((4.45, 4.45, ch, 1.0)))
        apply_bool(body, c)
    _studs(body, [(xx, yy) for yy in ys for xx in xs], BRICK_H)
    return finish(body, name, m, BRICK_H)


def make_window_frame(name, m):
    """1 x 2 x 2 window frame, 1.5 mm border (same wall as every other unit).
    Opening 12.8 x 15.3 through the 7.8 mm thickness; sill 2.4 leaves 0.5 mm
    over the 1.9 mm blind pockets. The pane rests on the back face and is
    captured by the frame's border, so the frame needs no recess."""
    w, d, h = P - GAP, 2 * P - GAP, 2 * BRICK_H
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2))
    body = bpy.context.active_object
    body.name = name
    body.data.transform(Matrix.Diagonal((w, d, h, 1.0)))
    _bevel(body)
    sill, open_w = 2.4, d - 2 * WALL
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (sill + h - WALL) / 2))
    c = bpy.context.active_object
    c.data.transform(Matrix.Diagonal((w + 4, open_w, (h - WALL) - sill, 1.0)))
    apply_bool(body, c)
    for yy in [-P / 2, P / 2]:
        _pocket(body, 0.0, yy)
    _studs(body, [(0.0, -P / 2), (0.0, P / 2)], h)
    return finish(body, name, m, h)


def make_pane(name, m):
    """0.8 mm boss plugs the frame opening (0.1 clearance per side); a 1.2 mm
    flange rests on the frame's back face. The 1.5 mm frame border captures it
    from the front, i.e. it drops in from behind and cannot fall forward.
    Print flange-down. An insert, not a stacking part."""
    fw, fh, ft = 14.6, 17.1, 1.2      # flange
    bw, bh, bt = 12.6, 15.1, 0.8      # boss -> 12.8 x 15.3 opening minus 0.1/side
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, fh / 2))
    body = bpy.context.active_object
    body.name = name
    body.data.transform(Matrix.Diagonal((ft, fw, fh, 1.0)))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-(ft + bt) / 2, 0, bh / 2 + (fh - bh) / 2))
    c = bpy.context.active_object
    c.data.transform(Matrix.Diagonal((bt, bw, bh, 1.0)))
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True); c.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    return finish(body, name, m, fh)


def make_unit(name, nx, ny, m, h=BRICK_H, studs=True, round_=False, slope=False, hollow=True,
              cavity_tighten=0.0, slope_wall=1.3, pockets=False, stud_positions=None):
    """cavity_tighten: shrink cavity cross-section (per-unit clutch tuning for pieces
    without clutch tubes, e.g. 1x1 whose only grip is the 4 cavity walls).
    slope_wall: slant-face wall thickness; 1.3 leaves room for front-row studs.
    pockets: press-fit stud pockets in a solid bottom (tiles).
    stud_positions: explicit (x, y) stud centres (used by the 1x2 jumper plate)."""
    w, d = nx * P - GAP, ny * P - GAP
    if round_:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=w / 2, depth=h, location=(0, 0, h / 2))
    else:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2))
    body = bpy.context.active_object
    body.name = name
    if not round_:
        body.data.transform(Matrix.Diagonal((w, d, h, 1.0)))

    # bevel FIRST (outer edges only) so cavity mouths / tube rims keep sharp
    # edges for a clean 4.8 clutch entry
    if not round_:
        bev = body.modifiers.new("Bevel", "BEVEL")
        bev.width = 0.15
        bev.segments = 2
        bev.limit_method = "ANGLE"
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.modifier_apply(modifier="Bevel")

    if hollow:
        # plate wall must leave cavity depth >= stud + 0.1 (else studs can't seat)
        wall = min(WALL, h - STUD_H - 0.1) if studs else WALL
        mouth = -0.5                            # cutter dips below bottom to breach mouth bevel
        ch = h - wall - mouth                   # cutter depth
        zc = (h - wall + mouth) / 2             # cutter center: spans mouth .. h-wall
        roof = h - wall                         # cavity ceiling (also tube span)
        if slope:
            # real LEGO slope: cavity runs under the whole footprint up to the
            # inner slope surface (45deg plane offset inward by wall*sqrt2)
            y_back = (d - 2 * wall) / 2
            x_half = (w - 2 * wall) / 2
            K = d / 2 - slope_wall * math.sqrt(2)  # thinner slant wall -> front studs seat
            y_flat = roof - K                   # plane meets cavity ceiling
            y_z0 = min(mouth - K, y_flat)       # plane meets cutter bottom
            pts = [(y_z0, mouth), (y_back, mouth), (y_back, roof), (y_flat, roof)]
            wedge = add_profile_wedge("wedge_cut", x_half, pts, m)
            apply_bool(body, wedge)
            # stud relief: near the front the 45deg slant drops below stud height,
            # so front-row studs can't seat -> punch clearance columns (standard
            # trick for printable slopes; only tiny scallops at the bottom edge)
            if studs:
                for yy in [-(ny - 1) * P / 2 + i * P for i in range(ny)]:
                    if yy - STUD_R + K < STUD_H + 0.1:
                        for xx in [-(nx - 1) * P / 2 + i * P for i in range(nx)]:
                            bpy.ops.mesh.primitive_cylinder_add(
                                vertices=48, radius=STUD_R + 0.2, depth=2.6,
                                location=(xx, yy, 0.8))
                            apply_bool(body, bpy.context.active_object)
                # clutch tubes under the flat-top (back) stud row: without them a
                # slope has zero grip. Press-fit bore (ID 4.4 vs stud 4.5).
                yy = (ny - 1) * P / 2
                for xx in [-(nx - 1) * P / 2 + i * P for i in range(nx)]:
                    bpy.ops.mesh.primitive_cylinder_add(
                        vertices=48, radius=3.2, depth=roof, location=(xx, yy, roof / 2))
                    t = bpy.context.active_object
                    bpy.ops.mesh.primitive_cylinder_add(
                        vertices=48, radius=STUD_R - 0.10, depth=roof + 2,
                        location=(xx, yy, roof / 2))
                    apply_bool(t, bpy.context.active_object)
                    mod = body.modifiers.new("tube", "BOOLEAN")
                    mod.operation = "UNION"
                    mod.solver = "EXACT"
                    mod.object = t
                    bpy.context.view_layer.objects.active = body
                    body.select_set(True)
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    bpy.data.objects.remove(t, do_unlink=True)
        elif round_:
            bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=w / 2 - wall - cavity_tighten / 2,
                                                depth=ch, location=(0, 0, zc))
            apply_bool(body, bpy.context.active_object)
        else:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, zc))
            c = bpy.context.active_object
            c.data.transform(Matrix.Diagonal((w - 2 * wall - cavity_tighten,
                                              d - 2 * wall - cavity_tighten, ch, 1.0)))
            apply_bool(body, c)

        # clutch tubes under every stud position (both dims >= 2), like real LEGO;
        # flush with the bottom face (z 0..roof) so no pads stick out
        if studs and not slope and nx >= 2 and ny >= 2:
            ys_list = [-(ny - 1) * P / 2 + i * P for i in range(ny)]
            xs_list = [-(nx - 1) * P / 2 + i * P for i in range(nx)]
            for yy in ys_list:
                for xx in xs_list:
                    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=3.2, depth=roof,
                                                        location=(xx, yy, roof / 2))
                    t = bpy.context.active_object
                    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=STUD_R, depth=roof + 2,
                                                        location=(xx, yy, roof / 2))
                    apply_bool(t, bpy.context.active_object)   # punch hole: tube ID 4.8
                    mod = body.modifiers.new("tube", "BOOLEAN")
                    mod.operation = "UNION"
                    mod.solver = "EXACT"
                    mod.object = t
                    bpy.context.view_layer.objects.active = body
                    body.select_set(True)
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    bpy.data.objects.remove(t, do_unlink=True)

    if pockets:
        # tiles: solid body, stud pockets in a solid bottom so the tile
        # can actually snap onto other bricks (real LEGO tiles clutch too).
        # ID 4.60 = clearance 0.05/side: shallow blind pockets (1.9mm) grip
        # less than full-height tubes, so keep a light press like slope_2x2_45
        # (verified 'easy push' at the same 4.60 bore)
        for yy in [-(ny - 1) * P / 2 + i * P for i in range(ny)]:
            for xx in [-(nx - 1) * P / 2 + i * P for i in range(nx)]:
                bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=STUD_R - 0.10,
                                                    depth=2.4, location=(xx, yy, 0.7))
                apply_bool(body, bpy.context.active_object)

    if slope:
        # 45-degree slope: top flat (d - h) deep at back, slope down to front-bottom edge
        bpy.ops.mesh.primitive_cube_add(size=30, location=(0, -20, h - 0.49))
        c = bpy.context.active_object
        c.rotation_euler = (math.radians(45), 0, 0)
        apply_bool(body, c)

    if studs:
        xs = [-(nx - 1) * P / 2 + i * P for i in range(nx)]
        if stud_positions is not None:
            stud_xy = list(stud_positions)
        elif slope:
            stud_xy = [(xx, (ny - 1) * P / 2) for xx in xs]
        else:
            stud_xy = [(xx, yy) for yy in [-(ny - 1) * P / 2 + i * P for i in range(ny)]
                       for xx in xs]
        _studs(body, stud_xy, h)

    # boolean/join leave a None slot at index 0 -> everything renders default gray; fix
    body.data.materials.clear()
    body.data.materials.append(m)
    for p2 in body.data.polygons:
        p2.material_index = 0
    for c2 in body.users_collection:
        c2.objects.unlink(body)
    bricks_col.objects.link(body)
    units.append(body)
    return body


def make_cheese(name, nx, ny, m, h=6.4, lip=1.2):
    """Cheese slope (30 deg, 1x1/1x2 x 2/3): plain wedge, no top studs,
    anti-stud recesses 4.8 under each stud position."""
    w, d = nx * P - GAP, ny * P - GAP
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, h / 2))
    body = bpy.context.active_object
    body.name = name
    body.data.transform(Matrix.Diagonal((w, d, h, 1.0)))
    bev = body.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.15
    bev.segments = 2
    bev.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="Bevel")

    # cut everything above the rake plane (front lip -> back top)
    pts = [(-d / 2, lip), (d / 2, h), (d / 2, h + 8), (-d / 2, h + 8)]
    apply_bool(body, add_profile_wedge("cheese_cut", w / 2 + 3, pts, m))

    # anti-stud recesses
    for yy in [-(ny - 1) * P / 2 + i * P for i in range(ny)]:
        for xx in [-(nx - 1) * P / 2 + i * P for i in range(nx)]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=STUD_R, depth=2.3,
                                                location=(xx, yy, 0.65))
            apply_bool(body, bpy.context.active_object)

    body.data.materials.clear()
    body.data.materials.append(m)
    for poly in body.data.polygons:
        poly.material_index = 0
    for c in body.users_collection:
        c.objects.unlink(body)
    bricks_col.objects.link(body)
    units.append(body)
    return body


# ---------------- the set (one of each) ----------------
make_unit("brick_1x1", 1, 1, COLORS["red"], cavity_tighten=0.4)   # press-fit: cavity 4.40 < stud 4.5
make_unit("brick_1x2", 1, 2, COLORS["purple"], cavity_tighten=0.35)  # single-row: cavity 4.45
make_unit("brick_1x4", 1, 4, COLORS["blue"], cavity_tighten=0.35)    # single-row: cavity 4.45
make_unit("brick_2x2", 2, 2, COLORS["blue"])
make_unit("brick_2x4", 2, 4, COLORS["yellow"])
make_unit("brick_2x6", 2, 6, COLORS["green"])
make_unit("slope_2x2_45", 2, 2, COLORS["orange"], slope=True)
make_ridge("slope_2x2_double_45", 2, 2, COLORS["orange"])
make_arch("arch_1x4", 1, 4, COLORS["white"])
make_window_frame("window_frame_1x2x2", COLORS["white"])
make_pane("window_pane_1x2", COLORS["azure"])
make_unit("round_plate_2x2", 2, 2, COLORS["azure"], round_=True, h=PLATE_H, hollow=False,
          pockets=True)   # solid disc + 4 blind pockets (tubes would breach the round wall)
make_cheese("slope_1x1_30", 1, 1, COLORS["orange"])
make_cheese("slope_1x2_30", 1, 2, COLORS["orange"])
make_unit("round_brick_1x1", 1, 1, COLORS["azure"], round_=True, cavity_tighten=0.15)  # bore 4.65 nominal line-to-line
make_unit("round_brick_2x2", 2, 2, COLORS["azure"], round_=True, hollow=False,
          pockets=True)   # solid body + 4 blind pockets (tubes would breach the round wall)
make_unit("round_plate_1x1", 1, 1, COLORS["azure"], round_=True, h=PLATE_H, cavity_tighten=0.4)
make_unit("plate_1x1", 1, 1, COLORS["white"], h=PLATE_H, cavity_tighten=0.4)
make_unit("plate_2x4", 2, 4, COLORS["white"], h=PLATE_H)
make_unit("plate_1x4", 1, 4, COLORS["white"], h=PLATE_H, cavity_tighten=0.4)
make_unit("plate_4x4", 4, 4, COLORS["white"], h=PLATE_H)
make_unit("plate_1x2", 1, 2, COLORS["white"], h=PLATE_H, cavity_tighten=0.4)  # single-row: no tubes, standard 4.80
make_unit("plate_2x2", 2, 2, COLORS["white"], h=PLATE_H)
make_unit("plate_2x6", 2, 6, COLORS["white"], h=PLATE_H)
make_unit("plate_4x8", 4, 8, COLORS["white"], h=PLATE_H)
make_unit("plate_8x8", 8, 8, COLORS["white"], h=PLATE_H)
make_unit("plate_6x12", 6, 12, COLORS["white"], h=PLATE_H)
make_unit("tile_1x1", 1, 1, COLORS["black"], h=PLATE_H, studs=False, hollow=False, pockets=True)
make_unit("tile_1x2", 1, 2, COLORS["black"], h=PLATE_H, studs=False, hollow=False, pockets=True)
make_unit("tile_2x2", 2, 2, COLORS["black"], h=PLATE_H, studs=False, hollow=False, pockets=True)
make_unit("tile_2x4", 2, 4, COLORS["black"], h=PLATE_H, studs=False, hollow=False, pockets=True)
make_unit("jumper_1x2", 1, 2, COLORS["yellow"], h=PLATE_H, cavity_tighten=0.4,
          stud_positions=[(0.0, 0.0)])

# ---------------- layout: two rows on the ground ----------------
def layout_row(objs, y, gap=16.0):
    x = 0.0
    for o in objs:
        w = o.dimensions.x
        o.location.x = x + w / 2
        o.location.y = y          # actually place each row at its y!
        o.location.z = 0.2 - min(v.co.z for v in o.data.vertices)   # sit on the ground
        x += w + gap
    total = x - gap
    for o in objs:
        o.location.x -= total / 2
    return total


row1 = ["brick_1x1", "brick_1x2", "brick_1x4", "brick_2x2", "brick_2x4", "brick_2x6"]
row2 = ["slope_1x1_30", "slope_1x2_30", "slope_2x2_45", "slope_2x2_double_45",
        "arch_1x4", "window_frame_1x2x2", "window_pane_1x2",
        "round_brick_1x1", "round_brick_2x2", "round_plate_1x1", "round_plate_2x2",
        "jumper_1x2"]
row3 = ["plate_1x1", "plate_1x2", "plate_1x4", "plate_2x2", "plate_2x4", "plate_4x4", "plate_2x6"]
row4 = ["plate_4x8", "plate_8x8", "plate_6x12", "tile_1x1", "tile_1x2", "tile_2x2", "tile_2x4"]
t1 = layout_row([bpy.data.objects[n] for n in row1], y=140.0)
t2 = layout_row([bpy.data.objects[n] for n in row2], y=80.0)
t3 = layout_row([bpy.data.objects[n] for n in row3], y=5.0)
t4 = layout_row([bpy.data.objects[n] for n in row4], y=-115.0)
print(f"row widths: {t1:.1f} / {t2:.1f} / {t3:.1f} / {t4:.1f} mm")
placed = {n for row in (row1, row2, row3, row4) for n in row}
assert placed == {o.name for o in units}, f"unplaced: {({o.name for o in units} - placed)}"
assert len(placed) == len(units), "duplicate unit in layout rows"
bpy.context.view_layer.update()   # locations just changed: refresh matrix_world

def _bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(p.x for p in pts), max(p.x for p in pts),
            min(p.y for p in pts), max(p.y for p in pts))
for i, a in enumerate(units):
    ax0, ax1, ay0, ay1 = _bbox(a)
    for b in units[i + 1:]:
        bx0, bx1, by0, by1 = _bbox(b)
        if ax0 < bx1 - 0.01 and bx0 < ax1 - 0.01 and ay0 < by1 - 0.01 and by0 < ay1 - 0.01:
            print(f"WARNING: {a.name} overlaps {b.name} in the layout")

print("--- unit sizes (mm) ---")
for o in units:
    dm = o.dimensions
    print(f"{o.name:18s} {dm.x:6.2f} x {dm.y:6.2f} x {dm.z:5.2f}")

# ---------------- ground / world / light ----------------
bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, 0))
g = bpy.context.active_object
g.name = "ground"
gm = bpy.data.materials.new("ground")
gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.45, 0.47, 0.50, 1)
gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
g.data.materials.append(gm)

w = bpy.data.worlds.new("W")
scene.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.93, 0.93, 0.95, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.75
l = bpy.data.lights.new("sun", "SUN")
l.energy = 3.5
l.angle = math.radians(12)
lo = bpy.data.objects.new("sun", l)
lo.rotation_euler = (math.radians(52), 0, math.radians(28))
scene.collection.objects.link(lo)
l2 = bpy.data.lights.new("fill", "SUN")
l2.energy = 1.2
lo2 = bpy.data.objects.new("fill", l2)
lo2.rotation_euler = (math.radians(55), 0, math.radians(-130))
scene.collection.objects.link(lo2)

# ---------------- cameras / render ----------------
row_span = max(t1, t2)


from mathutils import Vector


def ortho_cam(name, direction, scale, target=(0, 0, 5)):
    c = bpy.data.cameras.new(name)
    c.type = "ORTHO"
    c.ortho_scale = scale
    c.clip_end = 10000
    o = bpy.data.objects.new(name, c)
    o.location = (direction[0] * 500, direction[1] * 500, direction[2] * 500 + target[2])
    d = Vector(target) - Vector(o.location)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)
    return o


iso = ortho_cam("cam_iso", (0.01, -0.02, 1.0), 560)
front = ortho_cam("cam_front", (0.0, -1.0, 0.30), 330)

scene.render.engine = "BLENDER_EEVEE"
ee = scene.eevee
if hasattr(ee, "taa_render_samples"):
    ee.taa_render_samples = 64
scene.render.resolution_x = 1400
scene.render.resolution_y = 900
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = -0.1

bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

scene.camera = iso
scene.render.filepath = os.path.join(OUT_DIR, "overview_iso.png")
bpy.ops.render.render(write_still=True)
print("Rendered overview_iso")
scene.camera = front
scene.render.filepath = os.path.join(OUT_DIR, "overview_front.png")
bpy.ops.render.render(write_still=True)
print("Rendered overview_front")

# ---------------- optional mesh exports (off by default: keep the repo to 3MFs) ----------------
if os.environ.get("EXPORT_MESHES") == "1":
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception as e:
        print("gltf addon:", e)

    for o in units:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.wm.stl_export(filepath=os.path.join(EXP_DIR, o.name + ".stl"), export_selected_objects=True)
    print("STLs exported:", len(units))

    bpy.ops.object.select_all(action="DESELECT")
    for o in units:
        o.select_set(True)
    bpy.context.view_layer.objects.active = units[0]
    bpy.ops.export_scene.gltf(filepath=os.path.join(EXP_DIR, "brick_set.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    print("GLB exported")
print("DONE")
