# Bambu Studio config template

These files are the packaging/config skeleton used when exporting a Bambu
Studio project 3MF. They were extracted from a project saved by **Bambu Studio
02.08** with:

- Printer: **Bambu Lab P2S**
- Process: 0.20 mm Standard @BBL P2S
- Filament: Generic PLA
- Plate: Textured PEI, printable area **256 x 256 mm**

## Using a different printer

1. In Bambu Studio, select your printer / process / filament.
2. Save an **empty** project as `template.3mf`.
3. Unzip it and copy these files into this directory (overwrite):
   - `[Content_Types].xml`
   - `_rels/.rels`
   - `Metadata/project_settings.config`
   - `Metadata/slice_info.config`
   - `Metadata/filament_sequence.json`
   - `Metadata/cut_information.xml`
4. Set the printable bed size when exporting, e.g. `BED_SIZE=220`.

Or keep your template anywhere and point the env var at it:

```bash
BAMBU_TEMPLATE=/path/to/my_template blender -b -P bricks/export_bricks_3mf.py
```

## Note

Plate layout (see `references/3mf-format.md` in the `blender-bambu-3mf` skill)
places plates on a global grid with `stride = bed_size * 1.2`, so `BED_SIZE`
must match the printable area stored in the template.
