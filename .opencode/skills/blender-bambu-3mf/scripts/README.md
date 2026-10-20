# printpack.py

Reference multi-plate packer/writer. It is the exact module used by
`examples/warship` and `examples/cottage`.

## Required "kit" interface

`write_project(kit, out_path, title)` expects an object with:

| attribute | meaning |
|---|---|
| `kit.tpl[unit]` | Blender object used as the mesh template (`.data` is read) |
| `kit.log` | list of placements: `{unit, rot, color, zl, obj}` |
| `kit.parts` | list of placed Blender objects (used for thumbnails) |
| `kit.scene` | the Blender scene to render thumbnails in |

`unit` must be a key of the local `GEOM` cache; footprints/rotations come from
the mesh bounding box, so any brick set works as long as the templates exist.

## Environment

- `BAMBU_TEMPLATE` (default `bricks/bambu_template`)
- `BED_SIZE` (default `256`) — must match the template's printable area

## Behaviour

- one plate per colour, shelf-packed with 6 mm gaps and 12 mm margins
- plates are placed on Bambu's global grid (`stride = BED_SIZE * 1.2`)
- writes per-plate thumbnails (512/128) with Blender's own image scaling
- validates: object count, plate count, bed bounds, minimum gap
