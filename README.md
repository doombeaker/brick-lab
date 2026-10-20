# brick-lab

Parametric **LEGO-compatible bricks** modelled in Blender, tuned for FDM printing,
plus example models and print-ready Bambu Studio projects.

![brick set](docs/images/bricks.png)

- **15 brick types** on a true 8 mm stud pitch (bricks, slopes, rounds, plates, tiles)
- **Print-ready 3MF** — one Bambu Studio project per brick, with the user's printer,
  process and filament settings baked in
- **Clutch tuning from real prints** — press-fit 1x1 / round, clearance-fit slopes,
  snap pockets on tiles
- **Example builds** with layer-by-layer instructions and per-colour print plates
- **Agent skills** that document the Blender → Bambu 3MF pipeline and the brick spec

## Examples

| Model | Bricks | Plates | |
|---|---|---|---|
| [Warship](examples/warship) | 26 | 3 | ![warship](docs/images/warship.png) |
| [Cottage](examples/cottage) | 24 | 7 | ![cottage](docs/images/cottage.png) |

Each example contains `design.py` (the model), `brickkit.py` (grid placement +
validation + renders), `BOM.md` (piece list) and `PRINT.md` (plate plan).
Assembly instructions are rendered as one image per layer — see
[`docs/images/warship_steps.png`](docs/images/warship_steps.png).

## Requirements

- **Blender 4.2+** (developed on 5.2.1; EEVEE only, no add-ons required)
- Optional: **Bambu Studio 2.x** for slicing and for the extra CLI validation step

## Quick start

```bash
# 0. edit paths in the commands below if your blender binary differs
BLENDER=blender

# 1. build the 15 bricks (writes bricks/bricks.blend + overview renders)
$BLENDER -b --factory-startup -P bricks/build_bricks.py

# 2. mechanical checks (clearance, press-fit, cavity sizes)
$BLENDER -b --factory-startup -P bricks/verify_assembly.py
$BLENDER -b --factory-startup -P tools/check_specs.py

# 3. export one Bambu Studio project per brick -> bricks/exports/*.3mf
$BLENDER -b --factory-startup -P bricks/export_bricks_3mf.py

# 4. rebuild the example models (renders, BOM, print plans, 3MF)
$BLENDER -b --factory-startup -P examples/warship/make_all.py
$BLENDER -b --factory-startup -P examples/cottage/make_all.py

# 5. cross-check bricks + both examples (mesh identity, BOM counts, 3MF parts)
$BLENDER -b --factory-startup -P tools/check_consistency.py
```

Generated files land next to their source: `bricks/exports/*.3mf` (committed),
`examples/*/warship_print.3mf`, renders and `.blend` scenes (ignored by git).

## Brick set

| Type | Footprint (mm) | Clutch |
|---|---|---|
| `brick_1x1` | 7.8 × 7.8 | 4.40 cavity (press-fit) |
| `brick_1x2` | 7.8 × 15.8 | 4.45 cavity (press-fit, no tubes) |
| `brick_2x2` | 15.8 × 15.8 | 4.80 clutch tubes |
| `brick_2x4` | 15.8 × 31.8 | 4.80 clutch tubes |
| `brick_2x6` | 15.8 × 47.8 | 4.80 clutch tubes |
| `slope_2x2_45` | 15.8 × 15.75 | 4.60 tube bore (kid-friendly clearance) |
| `round_brick_1x1` | 7.8 × 7.8 | 4.40 bore (press-fit) |
| `plate_1x2` | 7.8 × 15.8 | 4.80 cavity (no tubes) |
| `plate_2x2` | 15.8 × 15.8 | 4.80 clutch tubes |
| `plate_2x4` | 15.8 × 31.8 | 4.80 clutch tubes |
| `plate_2x6` | 15.8 × 47.8 | 4.80 clutch tubes |
| `plate_4x8` | 31.8 × 63.8 | 4.80 clutch tubes |
| `plate_8x8` | 63.8 × 63.8 | 4.80 clutch tubes |
| `plate_6x12` | 47.8 × 95.8 | 4.80 clutch tubes |
| `tile_2x2` | 15.8 × 15.8 | 4 pockets, 4.46 × 1.9 deep |

Full machine-readable specs: [`bricks/bricks.json`](bricks/bricks.json).
Nominal stud OD is **4.5 mm** (4.8 socket minus 0.3 print clearance); heights are
9.6 mm (brick) and 3.2 mm (plate/tile).

## Printing

- 0.20 mm layer, PLA, textured PEI. All parts are single-piece, no supports.
- One plate per colour (single-extruder friendly). Plates are separated by ≥ 6 mm
  and kept 12 mm from the bed edge.
- Press-fit parts (`brick_1x1`, `brick_1x2`, `round_brick_1x1`, `tile_2x2`) need
  a normal FDM printer; if your holes print undersized, raise the cavity by
  ~0.05 mm (see `bricks.json` and the skill's tuning notes).

### Using a different printer

The shipped `bricks/bambu_template/` targets a **Bambu Lab P2S** (256 × 256 mm).
Replace it with a template exported from your own Bambu Studio project and set
`BED_SIZE` — see [`bricks/bambu_template/README.md`](bricks/bambu_template/README.md).

```bash
BED_SIZE=220 BAMBU_TEMPLATE=/path/to/template \
  $BLENDER -b --factory-startup -P bricks/export_bricks_3mf.py
```

## Repository layout

```
bricks/           generator, specs (bricks.json), template, 15 print-ready 3MFs
examples/warship  destroyer: design, BOM, print plan, instructions
examples/cottage  cottage:   design, BOM, print plan
tools/            spec + cross-project consistency checks
docs/images/      README renders
.opencode/skills/ agent skills (Blender→3MF pipeline, brick spec)
```

## Agent skills

Two skills live in `.opencode/skills/` and are picked up automatically when this
repository is opened as an opencode workspace:

- **`blender-bambu-3mf`** — how to turn Blender geometry into a Bambu Studio 3MF:
  package structure, multi-plate global grid, object IDs, thumbnails, validation,
  and the pitfalls we hit (empty plates, duplicate IDs, coplanar boolean slivers).
- **`blender-bricks-kit`** — the brick catalogue and how to build a new model on
  top of it: grid/layer model, the `brickkit` API, clutch tuning history, and the
  scaffold used by `examples/`.

## License

- Code (scripts, skills): **MIT** — see [LICENSE](LICENSE).
- Brick models, renders and documentation: **CC BY 4.0**.

LEGO® is a trademark of the LEGO Group. This project is not affiliated with or
endorsed by the LEGO Group.
