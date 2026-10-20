"""Build the warship, render views + layer-by-layer instructions, write BOM and
a multi-plate print project (one Bambu plate per colour)."""
import bpy
import os
import sys

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
from brickkit import BrickKit
import design
import printpack

os.makedirs(os.path.join(D, "renders"), exist_ok=True)
k = BrickKit()
design.build(k)
k.report()

k.studio()
k.render(os.path.join(D, "renders", "warship_iso.png"), (1.05, -1.25, 0.72))
k.render(os.path.join(D, "renders", "warship_front.png"), (0.0, -1.0, 0.30))
k.render(os.path.join(D, "renders", "warship_side.png"), (1.0, 0.10, 0.24))
k.step_renders(os.path.join(D, "renders", "steps"))

k.bom_markdown(os.path.join(D, "BOM.md"), "战舰")
plates = printpack.write_project(k, os.path.join(D, "warship_print.3mf"), "warship")
printpack.write_print_plan(os.path.join(D, "PRINT.md"), "战舰", plates)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, "warship.blend"))
print("saved warship.blend")
