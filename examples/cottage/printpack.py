"""Pack a toy's bricks onto Bambu plates (one plate per color) and write a
multi-plate Bambu Studio project 3MF (P2S / 0.20mm / PLA / Textured PEI).
Parts from the same color stay on the same plate when they fit; every part is
separated by GAP mm so they never touch.
"""
import bpy
import os
import json
import tempfile
import uuid
import math
import zipfile
from pathlib import Path
from mathutils import Vector, Matrix

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = os.environ.get("BAMBU_TEMPLATE", str(REPO / "bricks" / "bambu_template"))
BED = float(os.environ.get("BED_SIZE", "256"))
MARGIN = 12.0
GAP = 6.0
TMP = tempfile.mkdtemp(prefix="toy_plates_")

CN = {"black": "黑", "gray": "灰", "yellow": "黄", "red": "红",
      "orange": "橙", "green": "绿", "coffee": "咖啡"}

# Bambu arranges all plates in one global grid (see PartPlate.cpp):
# stride = bed * (1 + LOGICAL_PART_PLATE_GAP), columns = ceil-ish sqrt(count).
PLATE_GAP_RATIO = 0.2


def _cols(n):
    v = math.sqrt(n)
    r = int(math.floor(v + 0.5))
    return r + 1 if v > r else r


def _origin(plate_index, n_plates):
    cols = _cols(n_plates)
    row, col = divmod(plate_index, cols)
    stride = BED * (1.0 + PLATE_GAP_RATIO)
    return col * stride, -row * stride

GEOM = {}


def geometry(kit, unit, rot):
    key = (unit, rot)
    if key in GEOM:
        return GEOM[key]
    me = kit.tpl[unit].data
    me.calc_loop_triangles()
    co = [v.co for v in me.vertices]
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    ctr = (mn + mx) / 2
    R = Matrix.Rotation(math.radians(rot), 3, "Z")
    verts = [tuple(round(x, 5) for x in (R @ (c - ctr))) for c in co]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    h, dx, dy = mx.z - mn.z, mx.x - mn.x, mx.y - mn.y
    if rot % 180 == 90:
        dx, dy = dy, dx
    GEOM[key] = (verts, tris, h, dx, dy)
    return GEOM[key]


def _pack(kit, entries):
    """Shelf-pack entries; returns (placed, rest). placed: dict with x, y centre."""
    usable = BED - 2 * MARGIN
    order = sorted(entries, key=lambda e: -max(geometry(kit, *_gz(e))[3],
                                               geometry(kit, *_gz(e))[4]))
    x = y = row_h = 0.0
    placed, rest = [], []
    overflow = False
    for e in order:
        unit, rot = _gz(e)
        _, _, h, dx, dy = geometry(kit, unit, rot)
        if overflow:
            rest.append(e)
            continue
        if x + dx > usable + 1e-6 and x > 0:
            y += row_h + GAP
            x = row_h = 0.0
        if y + dy > usable + 1e-6:
            overflow = True
            rest.append(e)
            continue
        placed.append({"entry": e, "x": MARGIN + x + dx / 2,
                       "y": MARGIN + y + dy / 2, "w": dx, "d": dy, "h": h})
        x += dx + GAP
        row_h = max(row_h, dy)
    if placed:
        mnx = min(p["x"] - p["w"] / 2 for p in placed)
        mxx = max(p["x"] + p["w"] / 2 for p in placed)
        mny = min(p["y"] - p["d"] / 2 for p in placed)
        mxy = max(p["y"] + p["d"] / 2 for p in placed)
        sx = BED / 2 - (mnx + mxx) / 2
        sy = BED / 2 - (mny + mxy) / 2
        for p in placed:
            p["x"] += sx
            p["y"] += sy
    return placed, rest


def _gz(e):
    return (e["unit"], e["rot"])


def plan(kit):
    groups = {}
    for e in kit.log:
        groups.setdefault(e["color"], []).append(e)
    plates = []
    for color, entries in groups.items():
        remaining = entries
        while remaining:
            placed, remaining = _pack(kit, remaining)
            plates.append({"color": color, "items": placed})
    plates.sort(key=lambda p: (-len(p["items"]), p["color"]))
    return plates


def shrink_png(src, dst, size=128):
    img = bpy.data.images.load(src)
    img.scale(size, size)
    img.filepath_raw = dst
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def _thumb(kit, plate, path512):
    old_res = (kit.scene.render.resolution_x, kit.scene.render.resolution_y)
    kit.scene.render.resolution_x = kit.scene.render.resolution_y = 512
    for o in kit.parts:
        o.hide_render = True
    dups = []
    for p in plate["items"]:
        src = p["entry"]["obj"]
        o2 = src.copy()
        o2.data = src.data
        o2.hide_render = False
        kit.scene.collection.objects.link(o2)
        o2.matrix_world = Matrix.Identity(4)
        bpy.context.view_layer.update()
        bb = [o2.matrix_world @ Vector(c) for c in o2.bound_box]
        cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
        cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
        mnz = min(v.z for v in bb)
        o2.location = Vector((p["x"] - cx, p["y"] - cy, -mnz))
        dups.append(o2)
    bpy.context.view_layer.update()
    mnx = min(p["x"] - p["w"] / 2 for p in plate["items"])
    mxx = max(p["x"] + p["w"] / 2 for p in plate["items"])
    mny = min(p["y"] - p["d"] / 2 for p in plate["items"])
    mxy = max(p["y"] + p["d"] / 2 for p in plate["items"])
    cx, cy = (mnx + mxx) / 2, (mny + mxy) / 2
    cam = bpy.data.cameras.new("pcam")
    cam.type = "ORTHO"
    cam.ortho_scale = max(mxx - mnx, mxy - mny, 40) * 1.2
    cam.clip_end = 5000
    co = bpy.data.objects.new("pcam", cam)
    co.location = (cx, cy, 500)
    co.rotation_euler = (0, 0, 0)
    kit.scene.collection.objects.link(co)
    kit.scene.camera = co
    kit.scene.render.filepath = path512
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(co, do_unlink=True)
    bpy.data.cameras.remove(cam)
    for o2 in dups:
        bpy.data.objects.remove(o2, do_unlink=True)
    for o in kit.parts:
        o.hide_render = False
    kit.scene.render.resolution_x, kit.scene.render.resolution_y = old_res


NS_MODEL = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
            'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
            'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
            'requiredextensions="p"')


def write_project(kit, out_path, title):
    os.makedirs(TMP, exist_ok=True)
    plates = plan(kit)
    for pi, plate in enumerate(plates):
        ox, oy = _origin(pi, len(plates))
        for p in plate["items"]:
            p["x"] += ox
            p["y"] += oy
            p["ox"], p["oy"] = ox, oy

    # ---- per-plate thumbnails ----
    thumbs = []
    for pi, plate in enumerate(plates, start=1):
        p512 = os.path.join(TMP, f"plate_{pi}_512.png")
        p128 = os.path.join(TMP, f"plate_{pi}_128.png")
        _thumb(kit, plate, p512)
        shrink_png(p512, p128)
        thumbs.append((p512, p128))
        print(f"plate {pi}: {plate['color']} {len(plate['items'])} parts, thumbnail ok")

    with open(os.path.join(TEMPLATE_DIR, "[Content_Types].xml"), "rb") as f:
        T_CT = f.read()
    with open(os.path.join(TEMPLATE_DIR, "_rels/.rels"), "rb") as f:
        T_RELS = f.read()
    with open(os.path.join(TEMPLATE_DIR, "Metadata/project_settings.config"), "rb") as f:
        T_PROJECT = f.read()
    with open(os.path.join(TEMPLATE_DIR, "Metadata/slice_info.config"), "rb") as f:
        T_SLICE = f.read()
    with open(os.path.join(TEMPLATE_DIR, "Metadata/filament_sequence.json"), "rb") as f:
        T_FILSEQ = f.read()
    with open(os.path.join(TEMPLATE_DIR, "Metadata/cut_information.xml"), "rb") as f:
        T_CUT = f.read()

    objs_main, items, obj_cfg, rels, asm = [], [], [], [], []
    plate_blocks, plate_jsons = [], []
    idx = 0
    plate_of = {}
    obj_geom = {}
    for pi, plate in enumerate(plates, start=1):
        inst = []
        entries = []
        for p in plate["items"]:
            idx += 1
            e = p["entry"]
            unit, rot = e["unit"], e["rot"]
            verts, tris, h, dx, dy = geometry(kit, unit, rot)
            part_id = 2 * idx - 1
            oid = 2 * idx
            vx = "".join(f'<vertex x="{a:.5f}" y="{b:.5f}" z="{c:.5f}"/>'
                         for a, b, c in verts)
            tx = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                         for a, b, c in tris)
            obj_geom[idx] = (unit, verts, tris, h)
            rels.append(f' <Relationship Target="/3D/Objects/object_{idx}.model" '
                        f'Id="rel-{idx}" '
                        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
            objs_main.append(
                f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n'
                "   <components>\n"
                f'    <component p:path="/3D/Objects/object_{idx}.model" '
                f'objectid="{part_id}" p:UUID="{uuid.uuid4()}" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
                "   </components>\n  </object>")
            zoff = round(h / 2, 5)
            items.append(f'  <item objectid="{oid}" p:UUID="{uuid.uuid4()}" '
                         f'transform="1 0 0 0 1 0 0 0 1 {round(p["x"], 4)} '
                         f'{round(p["y"], 4)} {zoff}" printable="1"/>')
            obj_cfg.append(
                f'  <object id="{oid}">\n'
                f'    <metadata key="name" value="{unit}.stl"/>\n'
                '    <metadata key="extruder" value="1"/>\n'
                f'    <metadata face_count="{len(tris)}"/>\n'
                f'    <part id="{part_id}" subtype="normal_part" uuid="{uuid.uuid4()}">\n'
                f'      <metadata key="name" value="{unit}.stl"/>\n'
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                f'      <metadata key="source_file" value="{unit}.stl"/>\n'
                '      <metadata key="source_object_id" value="0"/>\n'
                '      <metadata key="source_volume_id" value="0"/>\n'
                '      <metadata key="source_offset_x" value="0"/>\n'
                '      <metadata key="source_offset_y" value="0"/>\n'
                '      <metadata key="source_offset_z" value="0"/>\n'
                f'      <mesh_stat face_count="{len(tris)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" '
                'backwards_edges="0"/>\n'
                '    </part>\n  </object>')
            inst.append("    <model_instance>\n"
                        f'      <metadata key="object_id" value="{oid}"/>\n'
                        '      <metadata key="instance_id" value="0"/>\n'
                        f'      <metadata key="identify_id" value="{78 + idx}"/>\n'
                        "    </model_instance>")
            asm.append(f'   <assemble_item object_id="{oid}" instance_id="0" '
                       f'transform="1 0 0 0 1 0 0 0 1 0 0 {zoff}" offset="0 0 0" />\n'
                       f'   <assemble_item object_id="{oid}" volume_id="0" '
                       'transform="1 0 0 0 1 0 0 0 1 0 0 0" />')
            plate_of[idx] = pi
            entries.append({"id": 90 + idx, "name": f"{unit}.stl",
                            "bbox": [round(p["x"] - dx / 2, 2), round(p["y"] - dy / 2, 2),
                                     round(p["x"] + dx / 2, 2), round(p["y"] + dy / 2, 2)],
                            "area": round(dx * dy, 2)})
        plate_blocks.append(
            "  <plate>\n"
            f'    <metadata key="plater_id" value="{pi}"/>\n'
            f'    <metadata key="plater_name" value="{plate["color"]}"/>\n'
            '    <metadata key="locked" value="false"/>\n'
            '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
            '    <metadata key="filament_maps" value="1 1 1 1"/>\n'
            '    <metadata key="filament_volume_maps" value="0 0 0 0"/>\n'
            f'    <metadata key="thumbnail_file" value="Metadata/plate_{pi}.png"/>\n'
            f'    <metadata key="thumbnail_no_light_file" '
            f'value="Metadata/plate_no_light_{pi}.png"/>\n'
            f'    <metadata key="top_file" value="Metadata/top_{pi}.png"/>\n'
            f'    <metadata key="pick_file" value="Metadata/pick_{pi}.png"/>\n'
            + "\n".join(inst) + "\n  </plate>")
        bbox = [round(min(e["bbox"][0] for e in entries), 2),
                round(min(e["bbox"][1] for e in entries), 2),
                round(max(e["bbox"][2] for e in entries), 2),
                round(max(e["bbox"][3] for e in entries), 2)]
        plate_jsons.append(json.dumps({
            "bbox_all": bbox,
            "bbox_objects": [{"area": e["area"], "bbox": e["bbox"], "id": e["id"],
                              "layer_height": 0.2, "name": e["name"]} for e in entries],
            "bed_type": "textured_plate", "filament_colors": [], "filament_ids": [],
            "first_extruder": 0, "first_layer_time": 25.0, "is_seq_print": False,
            "nozzle_diameter": 0.4, "version": 2,
        }))

    main_model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" {NS_MODEL}>\n'
        ' <metadata name="Application">BambuStudio-02.08.02.61</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <metadata name="CreationDate">2026-10-18</metadata>\n'
        f' <metadata name="Title">{title}</metadata>\n'
        " <resources>\n" + "\n".join(objs_main) + "\n </resources>\n"
        f' <build p:UUID="{uuid.uuid4()}">\n' + "\n".join(items) +
        "\n </build>\n</model>\n")
    model_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships">\n' + "\n".join(rels) + "\n</Relationships>\n")
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        + "\n".join(obj_cfg) + "\n" + "\n".join(plate_blocks) + "\n"
        "  <assemble>\n" + "\n".join(asm) + "\n  </assemble>\n</config>\n")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", T_CT)
        z.writestr("_rels/.rels", T_RELS)
        z.writestr("3D/3dmodel.model", main_model)
        z.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        for i in range(1, idx + 1):
            unit, verts, tris, h = obj_geom[i]
            vx = "".join(f'<vertex x="{a:.5f}" y="{b:.5f}" z="{c:.5f}"/>'
                         for a, b, c in verts)
            tx = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                         for a, b, c in tris)
            z.writestr(f"3D/Objects/object_{i}.model",
                       '<?xml version="1.0" encoding="UTF-8"?>\n'
                       f'<model unit="millimeter" xml:lang="en-US" {NS_MODEL}>\n'
                       ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
                       f' <resources><object id="{2 * i - 1}" p:UUID="{uuid.uuid4()}" '
                       'type="model">'
                       f'<mesh><vertices>{vx}</vertices><triangles>{tx}</triangles></mesh>'
                       '</object></resources>\n <build/>\n</model>\n')
        z.writestr("Metadata/model_settings.config", model_settings)
        for pi, pj in enumerate(plate_jsons, start=1):
            z.writestr(f"Metadata/plate_{pi}.json", pj)
            p512, p128 = thumbs[pi - 1]
            z.write(p512, f"Metadata/plate_{pi}.png")
            z.write(p512, f"Metadata/plate_no_light_{pi}.png")
            z.write(p512, f"Metadata/top_{pi}.png")
            z.write(p512, f"Metadata/pick_{pi}.png")
            z.write(p128, f"Metadata/plate_{pi}_small.png")
        z.writestr("Metadata/project_settings.config", T_PROJECT)
        z.writestr("Metadata/slice_info.config", T_SLICE)
        z.writestr("Metadata/cut_information.xml", T_CUT)
        z.writestr("Metadata/filament_sequence.json", T_FILSEQ)
    print(f"written {os.path.basename(out_path)}  {os.path.getsize(out_path)} bytes, "
          f"{len(plates)} plates, {idx} parts")

    # ---------------- validate ----------------
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    with zipfile.ZipFile(out_path) as z:
        root = ET.fromstring(z.read("3D/3dmodel.model"))
        cfg = json.loads(z.read("Metadata/project_settings.config"))
        names = z.namelist()
        objs = root.findall(".//m:object", ns)
        cfgroot = ET.fromstring(z.read("Metadata/model_settings.config"))
        plate_nodes = cfgroot.findall("plate")
        insts = [[mi.find("metadata").get("value")
                  for mi in pl.findall("model_instance")] for pl in plate_nodes]
    print(f"validate: {len(objs)} objects, {len(plate_nodes)} plates, "
          f"P2S={cfg.get('printer_model') == 'Bambu Lab P2S'}, "
          f"object files={sum(1 for n in names if n.startswith('3D/Objects/'))}")
    ok = len(objs) == idx and len(plate_nodes) == len(plates)
    # spacing + bed bounds check
    for plate in plates:
        ox, oy = plate["items"][0]["ox"], plate["items"][0]["oy"]
        pts = [(p["x"] - p["w"] / 2, p["y"] - p["d"] / 2,
                p["x"] + p["w"] / 2, p["y"] + p["d"] / 2) for p in plate["items"]]
        for a in pts:
            if a[0] < ox or a[1] < oy or a[2] > ox + BED or a[3] > oy + BED:
                ok = False
                print("  FAIL: part outside its plate bed")
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                a, b = pts[i], pts[j]
                dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
                dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
                gap = math.hypot(dx, dy)
                if gap < GAP - 0.05:
                    ok = False
                    print(f"  FAIL: gap {gap:.2f} < {GAP}")
    print("PRINT PACK OK" if ok else "PRINT PACK FAILED")
    return plates


def write_print_plan(path, title_cn, plates):
    lines = [f"# {title_cn} · 打印计划", "",
             f"共 **{len(plates)} 盘**（每色一盘；同盘内零件间距 ≥ {GAP:.0f}mm，不粘连；"
             f"四周留边 {MARGIN:.0f}mm）", "",
             "| 盘 | 颜色 | 件数 | 明细 |", "|---|---|---|---|"]
    for pi, plate in enumerate(plates, start=1):
        units = {}
        for p in plate["items"]:
            u = p["entry"]["unit"]
            units[u] = units.get(u, 0) + 1
        detail = "、".join(f"{u}×{n}" for u, n in sorted(units.items()))
        lines.append(f"| {pi} | {CN[plate['color']]} | {len(plate['items'])} | {detail} |")
    lines += ["", "打开 3MF 后按盘号顺序打印，每盘换对应颜色耗材即可。", ""]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print("written", os.path.basename(path))
