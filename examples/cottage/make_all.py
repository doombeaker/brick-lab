"""Build the cottage, render views + layer-by-layer instructions, write BOM and
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
k.render(os.path.join(D, "renders", "cottage_iso.png"), (1.0, -1.25, 0.8))
k.render(os.path.join(D, "renders", "cottage_front.png"), (0.0, -1.0, 0.32))
k.render(os.path.join(D, "renders", "cottage_side.png"), (1.0, 0.05, 0.28))
k.step_renders(os.path.join(D, "renders", "steps"))

k.bom_markdown(os.path.join(D, "BOM.md"), "小屋")
plates = printpack.write_project(k, os.path.join(D, "cottage_print.3mf"), "cottage")
printpack.write_print_plan(os.path.join(D, "PRINT.md"), "小屋", plates)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, "cottage.blend"))
print("saved cottage.blend")
