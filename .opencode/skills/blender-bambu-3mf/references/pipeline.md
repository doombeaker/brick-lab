# 实现管线（Blender 无头 → 3MF）

## 运行方式

```bash
# 所有脚本都在 Blender 内跑；仓库根目录执行
blender -b --factory-startup -P bricks/export_bricks_3mf.py
```

- `-b` 无头，`-P` 执行 Python，`--factory-startup` 避免用户配置干扰。
- 脚本内的路径全部相对 `Path(__file__)`，因此可以在任意工作目录运行。
- 可用环境变量覆盖：`BAMBU_TEMPLATE`、`BED_SIZE`、`BRICKS_BLEND`。
- `blender` 不在 PATH 时：macOS `/Applications/Blender.app/Contents/MacOS/Blender`，
  Linux 通常 `/usr/bin/blender` 或 snap/flatpak 路径。建议在文档里让用户自己设
  `$BLENDER`。

## 几何提取

```python
me = obj.data
me.calc_loop_triangles()
mw = obj.matrix_world

# 1) 世界坐标 -> 以包围盒中心为原点
bb = [mw @ Vector(c) for c in obj.bound_box]
mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
ctr = (mn + mx) / 2

verts = [tuple(round(c, 5) for c in (mw @ v.co - ctr)) for v in me.vertices]
tris  = [tuple(t.vertices) for t in me.loop_triangles]
```

- **旋转烘焙**：如果实例有 Z 旋转，先 `Rz @ (v.co - ctr)` 再写入；build item 里
  只放平移。
- 写 XML 前对浮点做 `round(..., 5)`，文件更小、也便于一致性校验。
- 面法线方向沿用 Blender 的三角化结果即可；Bambu 会自动修复少量法线问题。

## 底部对齐（放置零件）

`obj.location` 是对象原点，不一定在底面中心。跨零件对齐时用世界包围盒：

```python
bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2
cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
mz = min(v.z for v in bb)
o.location += Vector((target_x - cx, target_y - cy, target_z - mz))
```

否则会把零件"沉"进底板，产生假碰撞。

## 材质

布尔/合并后容易出现 `None` 材质槽（索引 0），导致导出或渲染全黑：

```python
o.data.materials.clear()
o.data.materials.append(mat)
for poly in o.data.polygons:
    poly.material_index = 0
```

## 缩略图

渲染：EEVEE、512×512、正交相机俯视（`rotation_euler=(0,0,0)`），
`ortho_scale = max(plate_w, plate_d) * 1.2`。

512 → 128 **不要用系统工具**（`sips` 仅 macOS，ImageMagick 不一定装），
用 Blender 自带图像 API：

```python
def shrink_png(src, dst, size=128):
    img = bpy.data.images.load(src)
    img.scale(size, size)
    img.filepath_raw = dst
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
```

渲染时把其他零件 `hide_render = True`，并**注意 `obj.copy()` 会继承
`hide_render`**，复制出来的缩略图对象要显式设回 `False`。

## 临时文件

用 `tempfile.mkdtemp()`，不要写死 `/tmp/xxx`（跨平台 + 避免残留冲突）。

## 可选校验（Bambu Studio CLI）

```bash
# macOS
BS=/Applications/BambuStudio.app/Contents/MacOS/BambuStudio
# Linux: bambu-studio / Windows: BambuStudio.exe (在安装目录)

"$BS" --export-3mf /tmp/rt.3mf project.3mf   # 重导出
"$BS" --info project.3mf                     # 对象尺寸/面数
```

把重导出文件解开，数每个 `<plate>` 的 `<model_instance>`：
数量与预期一致才算盘归属正确。CLI 不存在时跳过，不影响主流程。

## 体积/速度

- 顶点 5 位小数取整可显著减小文件；15 个砖的 3MF 合计约 2.5 MB。
- 大板（96 mm 级）三角面多，布尔与渲染会慢一些，属正常。
- 缩略图渲染用 EEVEE 64 samples 足够。
