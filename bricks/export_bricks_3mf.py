"""One Bambu Studio project 3MF per brick type (15 files).

The config template ships in bricks/bambu_template (P2S / 0.20mm / Generic PLA
/ Textured PEI). Override it with the BAMBU_TEMPLATE env var if you use a
different printer or profile — see bricks/bambu_template/README.md.
"""
import bpy
import os
import json
import math
import tempfile
import uuid
import zipfile
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
SRC = str(ROOT / "bricks.blend")
TEMPLATE_DIR = os.environ.get("BAMBU_TEMPLATE", str(ROOT / "bambu_template"))
OUT = str(ROOT / "exports")
TMP = tempfile.mkdtemp(prefix="bricks_3mf_")
BED = float(os.environ.get("BED_SIZE", "256"))
os.makedirs(OUT, exist_ok=True)

UNITS = ["brick_1x1", "brick_1x2", "brick_1x4", "brick_2x2", "brick_2x4", "brick_2x6",
         "slope_1x1_30", "slope_1x2_30", "slope_2x2_45", "slope_2x2_double_45",
         "arch_1x4", "window_frame_1x2x2", "window_pane_1x2",
         "round_brick_1x1", "round_brick_2x2", "round_plate_1x1", "round_plate_2x2",
         "plate_1x1", "plate_1x2", "plate_1x4", "plate_2x2", "plate_2x4", "plate_2x6",
         "plate_4x4", "plate_4x8", "plate_8x8", "plate_6x12",
         "tile_1x1", "tile_1x2", "tile_2x2", "tile_2x4", "jumper_1x2"]

bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene

# ---------------- geometry ----------------
def geom(name):
    o = bpy.data.objects[name]
    me = o.data
    mw = o.matrix_world
    bb = [mw @ Vector(c) for c in o.bound_box]
    cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
    cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
    czi = (min(v.z for v in bb) + max(v.z for v in bb)) / 2
    h = max(v.z for v in bb) - min(v.z for v in bb)
    dims = (max(v.x for v in bb) - min(v.x for v in bb),
            max(v.y for v in bb) - min(v.y for v in bb))
    me.calc_loop_triangles()
    verts = [tuple(round(c, 5) for c in (mw @ v.co - Vector((cx, cy, czi)))) for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    return verts, tris, h, dims


GEOM = {n: geom(n) for n in UNITS}

# ---------------- thumbnails ----------------
def place_object(o, x, y):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
    cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
    mz = min(v.z for v in bb)
    o.location = o.location + Vector((x - cx, y - cy, -mz))


def shrink_png(src, dst, size=128):
    """Cross-platform 512 -> 128 downscale (no sips/ImageMagick needed)."""
    img = bpy.data.images.load(src)
    img.scale(size, size)
    img.filepath_raw = dst
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def render_thumb(path, name):
    for n in UNITS:
        bpy.data.objects[n].hide_render = (n != name)
    place_object(bpy.data.objects[name], BED / 2, BED / 2)
    bpy.context.view_layer.update()
    scale = max(max(GEOM[name][3]) * 2.6, 70)
    cam_data = bpy.data.cameras.new("thumbcam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scale
    cam_data.clip_end = 5000
    cam = bpy.data.objects.new("thumbcam", cam_data)
    cam.location = (BED / 2, BED / 2, 400)
    cam.rotation_euler = (0, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -0.2
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.cameras.remove(cam_data)


# ---------------- template pieces ----------------
with open(os.path.join(TEMPLATE_DIR, "[Content_Types].xml"), "rb") as f:
    T_CONTENT_TYPES = f.read()
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

NS_MODEL = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
            'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
            'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
            'requiredextensions="p"')

written = []

for name in UNITS:
    verts, tris, h, dims = GEOM[name]
    face_count = len(tris)

    # thumbnail 512 + 128
    png512 = os.path.join(TMP, f"{name}_512.png")
    png128 = os.path.join(TMP, f"{name}_128.png")
    render_thumb(png512, name)
    shrink_png(png512, png128)

    vx = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in verts)
    tx = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris)
    object_model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" {NS_MODEL}>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <resources>\n'
        f'  <object id="1" p:UUID="{uuid.uuid4()}" type="model">\n'
        f'   <mesh><vertices>{vx}</vertices><triangles>{tx}</triangles></mesh>\n'
        '  </object>\n </resources>\n <build/>\n</model>\n'
    )

    zoff = round(h / 2, 5)
    main_model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" {NS_MODEL}>\n'
        ' <metadata name="Application">BambuStudio-02.08.02.61</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <metadata name="CreationDate">2026-10-18</metadata>\n'
        f' <metadata name="Title">{name}</metadata>\n'
        ' <resources>\n'
        f'  <object id="2" p:UUID="{uuid.uuid4()}" type="model">\n'
        '   <components>\n'
        f'    <component p:path="/3D/Objects/object_1.model" objectid="1" '
        f'p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
        '   </components>\n  </object>\n </resources>\n'
        f' <build p:UUID="{uuid.uuid4()}">\n'
        f'  <item objectid="2" p:UUID="{uuid.uuid4()}" '
        f'transform="1 0 0 0 1 0 0 0 1 {BED/2} {BED/2} {zoff}" printable="1"/>\n'
        ' </build>\n</model>\n'
    )

    model_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/Objects/object_1.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        "</Relationships>\n"
    )

    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        '  <object id="2">\n'
        f'    <metadata key="name" value="{name}.stl"/>\n'
        '    <metadata key="extruder" value="1"/>\n'
        f'    <metadata face_count="{face_count}"/>\n'
        f'    <part id="1" subtype="normal_part" uuid="{uuid.uuid4()}">\n'
        f'      <metadata key="name" value="{name}.stl"/>\n'
        '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
        f'      <metadata key="source_file" value="{name}.stl"/>\n'
        '      <metadata key="source_object_id" value="0"/>\n'
        '      <metadata key="source_volume_id" value="0"/>\n'
        '      <metadata key="source_offset_x" value="0"/>\n'
        '      <metadata key="source_offset_y" value="0"/>\n'
        '      <metadata key="source_offset_z" value="0"/>\n'
        f'      <mesh_stat face_count="{face_count}" edges_fixed="0" degenerate_facets="0" '
        'facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
        '    </part>\n  </object>\n'
        '  <plate>\n'
        '    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
        '    <metadata key="filament_maps" value="1 1 1 1"/>\n'
        '    <metadata key="filament_volume_maps" value="0 0 0 0"/>\n'
        '    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>\n'
        '    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>\n'
        '    <metadata key="top_file" value="Metadata/top_1.png"/>\n'
        '    <metadata key="pick_file" value="Metadata/pick_1.png"/>\n'
        '    <model_instance>\n'
        '      <metadata key="object_id" value="2"/>\n'
        '      <metadata key="instance_id" value="0"/>\n'
        '      <metadata key="identify_id" value="78"/>\n'
        '    </model_instance>\n'
        '  </plate>\n'
        '  <assemble>\n'
        f'   <assemble_item object_id="2" instance_id="0" transform="1 0 0 0 1 0 0 0 1 0 0 {zoff}" offset="0 0 0" />\n'
        '   <assemble_item object_id="2" volume_id="0" transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n'
        '  </assemble>\n</config>\n'
    )

    halfx, halfy = max(dims) / 2, max(dims) / 2
    bbox = [round(BED / 2 - halfx, 2), round(BED / 2 - halfy, 2),
            round(BED / 2 + halfx, 2), round(BED / 2 + halfy, 2)]
    plate = json.dumps({
        "bbox_all": bbox,
        "bbox_objects": [{"area": round((bbox[2] - bbox[0]) ** 2, 2), "bbox": bbox,
                          "id": 90, "layer_height": 0.2, "name": f"{name}.stl"}],
        "bed_type": "textured_plate", "filament_colors": [], "filament_ids": [],
        "first_extruder": 0, "first_layer_time": 30.0, "is_seq_print": False,
        "nozzle_diameter": 0.4, "version": 2,
    })

    path = os.path.join(OUT, f"{name}.3mf")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", T_CONTENT_TYPES)
        z.writestr("_rels/.rels", T_RELS)
        z.writestr("3D/3dmodel.model", main_model)
        z.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        z.writestr("3D/Objects/object_1.model", object_model)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/plate_1.json", plate)
        z.write(png512, "Metadata/plate_1.png")
        z.write(png512, "Metadata/plate_no_light_1.png")
        z.write(png512, "Metadata/top_1.png")
        z.write(png512, "Metadata/pick_1.png")
        z.write(png128, "Metadata/plate_1_small.png")
        z.writestr("Metadata/project_settings.config", T_PROJECT)
        z.writestr("Metadata/slice_info.config", T_SLICE)
        z.writestr("Metadata/cut_information.xml", T_CUT)
        z.writestr("Metadata/filament_sequence.json", T_FILSEQ)
    print(f"written {name}.3mf  {os.path.getsize(path)} bytes")
    written.append(path)

# ---------------- validate ----------------
import xml.etree.ElementTree as ET
ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
ok = True
for path in written:
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("3D/3dmodel.model"))
            ET.fromstring(z.read("Metadata/model_settings.config"))
            json.loads(z.read("Metadata/plate_1.json"))
            cfg = json.loads(z.read("Metadata/project_settings.config"))
            pngs = [n for n in z.namelist() if n.endswith(".png")]
        objs = root.findall(".//m:object", ns)
        good = (len(objs) == 1 and cfg.get("printer_model") == "Bambu Lab P2S" and len(pngs) == 5)
        ok &= good
        print(f"validate {os.path.basename(path)}: 1 object, P2S config, {len(pngs)} pngs -> {'OK' if good else 'FAIL'}")
    except Exception as e:
        ok = False
        print("FAIL", path, e)
print("ALL OK" if ok else "SOME FAILED")
print("DONE")
