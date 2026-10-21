"""Shared helper: place bricks from blender-bricks on a stud grid, validate,
count, render views/step-by-step instructions and write a BOM.
Geometry is copied from bricks.blend so specs match the printed bricks exactly.
"""
import bpy
import math
import os
from pathlib import Path
from mathutils import Vector, Matrix

REPO = Path(__file__).resolve().parents[2]
SRC_BLEND = os.environ.get("BRICKS_BLEND", str(REPO / "bricks" / "bricks.blend"))
PITCH, LAYER = 8.0, 3.2

FOOT = {  # footprint in studs + height in plate-layers (3 = brick, 1 = plate/tile)
    "brick_1x1": (1, 1, 3),
    "brick_2x2": (2, 2, 3),
    "brick_2x4": (2, 4, 3),
    "brick_2x6": (2, 6, 3),
    "slope_2x2_45": (2, 2, 3),
    "round_brick_1x1": (1, 1, 3),
    "brick_1x4": (1, 4, 3),
    "slope_1x1_30": (1, 1, 2),
    "slope_1x2_30": (1, 2, 2),
    "round_brick_2x2": (2, 2, 3),
    "round_plate_1x1": (1, 1, 1),
    "plate_1x1": (1, 1, 1),
    "plate_1x2": (1, 2, 1),
    "plate_1x4": (1, 4, 1),
    "plate_4x4": (4, 4, 1),
    "tile_1x1": (1, 1, 1),
    "tile_1x2": (1, 2, 1),
    "tile_2x4": (2, 4, 1),
    "jumper_1x2": (1, 2, 1),
    "plate_2x2": (2, 2, 1),
    "plate_2x4": (2, 4, 1),
    "plate_2x6": (2, 6, 1),
    "plate_4x8": (4, 8, 1),
    "plate_8x8": (8, 8, 1),
    "plate_6x12": (6, 12, 1),
    "tile_2x2": (2, 2, 1),
}

PALETTE = {  # user's available PLA: black, gray, yellow, red, orange, green, coffee
    "black": ("14181C", 0.45),
    "gray": ("8C8E92", 0.50),
    "yellow": ("F2CD37", 0.45),
    "red": ("C91A09", 0.45),
    "orange": ("FE8A18", 0.45),
    "green": ("237841", 0.45),
    "coffee": ("4B2E1E", 0.50),
}

CN = {"black": "黑色", "gray": "灰色", "yellow": "黄色", "red": "红色",
      "orange": "橙色", "green": "绿色", "coffee": "咖啡色"}


def hexc(s):
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class BrickKit:
    def __init__(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.coll = bpy.data.collections.new("Toy")
        self.scene.collection.children.link(self.coll)
        self.mats = {}
        for name, (hx, rough) in PALETTE.items():
            m = bpy.data.materials.new("pla_" + name)
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*hexc(hx), 1.0)
            b.inputs["Roughness"].default_value = rough
            self.mats[name] = m
        with bpy.data.libraries.load(SRC_BLEND, link=False) as (src, dst):
            dst.objects = list(FOOT.keys())
        self.tpl = {o.name: o for o in dst.objects if o}
        self.occ = {}
        self.bom = {}
        self.parts = []
        self.log = []          # placement records (unit, color, rot, zl, obj)
        self.count = 0

    def place(self, unit, gx, gy, zl, color, rot=0):
        """gx, gy = lower stud cell; zl = layer index in 3.2mm units."""
        assert unit in FOOT, unit
        nx, ny, h = FOOT[unit]
        if rot % 180 == 90:
            nx, ny = ny, nx
        cells = [(gx + i, gy + j, zl + k)
                 for i in range(nx) for j in range(ny) for k in range(h)]
        for c in cells:
            if c in self.occ:
                raise RuntimeError(f"collision at {c} placing {unit} ({gx},{gy},{zl})")
        if zl > 0:
            below = [(gx + i, gy + j, zl - 1) for i in range(nx) for j in range(ny)]
            sup = sum(1 for c in below if c in self.occ)
            if sup < max(1, len(below) // 4):
                print(f"  WARN low support: {unit} at ({gx},{gy},z{zl}) {sup}/{len(below)}")
        tpl = self.tpl[unit]
        o = tpl.copy()
        o.data = tpl.data.copy()
        o.data.materials.clear()
        o.data.materials.append(self.mats[color])
        self.coll.objects.link(o)
        o.matrix_world = Matrix.Identity(4)
        o.rotation_euler = (0, 0, math.radians(rot))
        bpy.context.view_layer.update()
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
        cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
        mnz = min(v.z for v in bb)
        tx = gx * PITCH + nx * PITCH / 2
        ty = gy * PITCH + ny * PITCH / 2
        o.location = Vector((tx - cx, ty - cy, zl * LAYER - mnz))
        self.occ.update({c: unit for c in cells})
        self.bom[(unit, color)] = self.bom.get((unit, color), 0) + 1
        self.parts.append(o)
        self.log.append({"unit": unit, "color": color, "rot": rot,
                         "zl": zl, "obj": o})
        self.count += 1
        return o

    # ---------------- studio & renders ----------------
    def studio(self):
        bpy.ops.mesh.primitive_plane_add(size=2000, location=(0, 0, -0.05))
        g = bpy.context.active_object
        g.name = "ground"
        gm = bpy.data.materials.new("ground")
        gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.83, 0.85, 1)
        gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
        g.data.materials.append(gm)
        w = bpy.data.worlds.new("W")
        self.scene.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.88, 0.89, 0.92, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.55
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy = 3.0
        so = bpy.data.objects.new("sun", sun)
        so.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
        self.scene.collection.objects.link(so)
        fill = bpy.data.lights.new("fill", "SUN")
        fill.energy = 1.1
        fo = bpy.data.objects.new("fill", fill)
        fo.rotation_euler = (math.radians(60), 0, math.radians(-120))
        self.scene.collection.objects.link(fo)
        self.scene.render.engine = "BLENDER_EEVEE"
        if hasattr(self.scene.eevee, "taa_render_samples"):
            self.scene.eevee.taa_render_samples = 64
        self.scene.render.resolution_x = 1200
        self.scene.render.resolution_y = 900
        self.scene.view_settings.view_transform = "Standard"
        self.scene.view_settings.exposure = -0.25

    def _framing(self):
        pts = []
        for o in self.parts:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        return mn, mx

    def _camera(self, direction, margin):
        mn, mx = self._framing()
        center = (mn + mx) / 2
        dims = mx - mn
        d = Vector(direction).normalized()
        cam = bpy.data.cameras.new("cam")
        cam.type = "ORTHO"
        cam.ortho_scale = max(dims.x, dims.y, dims.z) * margin + 10
        cam.clip_end = 10000
        co = bpy.data.objects.new("cam", cam)
        co.location = center + d * 600
        co.rotation_euler = (center - co.location).to_track_quat("-Z", "Y").to_euler()
        self.scene.collection.objects.link(co)
        self.scene.camera = co
        return co, cam

    def render(self, path, direction=(0.95, -1.25, 0.8)):
        co, cam = self._camera(direction, 1.55)
        self.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(co, do_unlink=True)
        bpy.data.cameras.remove(cam)
        print("rendered", os.path.basename(path))

    def step_renders(self, outdir, direction=(1.0, -1.25, 0.78)):
        """One iso render per build layer: previous layers ghosted, new layer in color."""
        os.makedirs(outdir, exist_ok=True)
        ghost = bpy.data.materials.new("ghost")
        ghost.use_nodes = True
        gb = ghost.node_tree.nodes["Principled BSDF"]
        gb.inputs["Base Color"].default_value = (0.90, 0.91, 0.94, 1)
        gb.inputs["Roughness"].default_value = 0.85
        co, cam = self._camera(direction, 1.55)
        steps = sorted(set(e["zl"] for e in self.log))
        restore = [(e, e["obj"].data.materials[0], e["obj"].hide_render) for e in self.log]
        for si, zl in enumerate(steps, start=1):
            for e in self.log:
                o = e["obj"]
                o.hide_render = e["zl"] > zl
                if o.data.materials:
                    o.data.materials[0] = self.mats[e["color"]] if e["zl"] == zl else ghost
            path = os.path.join(outdir, f"step_{si:02d}.png")
            self.scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            n = sum(1 for e in self.log if e["zl"] == zl)
            print(f"rendered {os.path.basename(path)}  (layer {zl}, {n} bricks)")
        for e, mat, hide in restore:
            o = e["obj"]
            o.hide_render = hide
            if o.data.materials and mat:
                o.data.materials[0] = mat
        bpy.data.objects.remove(co, do_unlink=True)
        bpy.data.cameras.remove(cam)

    # ---------------- BOM ----------------
    def bom_markdown(self, path, title):
        by_color = {}
        for e in self.log:
            by_color.setdefault(e["color"], []).append(e["unit"])
        order = sorted(by_color, key=lambda c: -len(by_color[c]))
        lines = [f"# {title} · 砖块清单", "",
                 f"**总计 {self.count} 块**（上限 50，余 {max(0, 50 - self.count)}）", "",
                 "## 按颜色分组", "",
                 "| 颜色 | 件数 | 明细 |", "|---|---|---|"]
        for c in order:
            units = {}
            for u in by_color[c]:
                units[u] = units.get(u, 0) + 1
            detail = "、".join(f"{u}×{n}" for u, n in sorted(units.items()))
            lines.append(f"| {CN[c]} | {len(by_color[c])} | {detail} |")
        lines += ["", "## 按砖型汇总", "", "| 砖型 | 数量 |", "|---|---|"]
        by_unit = {}
        for (u, c), n in self.bom.items():
            by_unit[u] = by_unit.get(u, 0) + n
        for u, n in sorted(by_unit.items()):
            lines.append(f"| {u} | {n} |")
        lines += ["", f"砖型合计：{len(by_unit)} 种", ""]
        with open(path, "w") as f:
            f.write("\n".join(lines))
        print("written", os.path.basename(path))

    def report(self):
        print(f"TOTAL BRICKS: {self.count}")
        for (unit, color), n in sorted(self.bom.items()):
            print(f"  {unit:18s} x{n:2d}  ({color})")
        print("OK within 50" if self.count <= 50 else "!! OVER 50 LIMIT")
