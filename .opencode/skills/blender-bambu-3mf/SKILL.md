---
name: blender-bambu-3mf
description: 把 Blender 里的几何导出成 Bambu Studio 可直接打开、切片的 3MF（单件/多盘、缩略图、打印机配置、结构校验）。当用户要求"导出可打印 3MF""生成打印盘/排版""Bambu 打开后某盘是空的/零件缺失/ID 冲突"或需要把 Blender 脚本接进 Bambu 工作流时使用。
---

# Blender → Bambu Studio 3MF

把 Blender 无头脚本产出的网格，打包成 Bambu Studio 能直接打开、切片的工程
3MF。本仓库的参考实现是 `bricks/export_bricks_3mf.py`（单件）和
`examples/*/printpack.py`（多盘、按颜色分盘）。

## 三条铁律

1. **不要从零手写 3MF。** 必须有 `bricks/bambu_template/` 里的配置骨架
   （`[Content_Types].xml`、`_rels/.rels`、`Metadata/project_settings.config` 等），
   否则 Bambu 会拒绝或行为异常。换打印机就换模板，见
   `bricks/bambu_template/README.md`。
2. **多盘不是"每盘独立坐标系"。** Bambu 把所有盘排在同一个全局坐标系里，
   `stride = 可打印床宽 × 1.2`，按 √N 排成网格；加载时按"零件包围盒落在
   哪个盘的矩形内"判定归属。把每盘零件都摆在床中心 = 全落到 1 号盘。
3. **对象 ID 必须唯一且成对。** 第 i 个零件：包装对象 `id = 2i`、
   part `id = 2i-1`、`3D/Objects/object_i.model` 内部 `<object id="2i-1">`。
   重复 ID 会让 Bambu 把多个零件合并成一个。

## 工作流

1. **准备模板**（只需一次）
   - 用 `bricks/bambu_template/`，或自己从 Bambu Studio 存一个空工程按
     `bricks/bambu_template/README.md` 替换。
   - 床尺寸必须与模板一致：`BED_SIZE`（默认 256）。
2. **提取几何**（在 Blender 内运行）
   - `mesh.calc_loop_triangles()`，顶点取 `matrix_world @ v.co`，减去包围盒中心，
     三角面用 `loop_triangles`。
   - 旋转不要靠 3MF transform：把旋转烘焙进顶点（Rz 后写入），build item 只做平移。
   - 平移量 `z = 高度/2`（几何已居中），保证底面在 z=0。
3. **排盘**
   - 按颜色/材料分组；同组用货架算法排：零件间距 `GAP = 6 mm`，四边留
     `MARGIN = 12 mm`。
   - 每盘用 `(plate_index, total_plates)` 算全局原点，把局部坐标平移过去。
   - 公式见 `references/3mf-format.md`。
4. **写 3MF**
   - 必需的包结构、XML 片段、盘块写法见 `references/3mf-format.md`。
   - 每个盘写 5 张缩略图（`plate_N`、`plate_no_light_N`、`top_N`、`pick_N`、
     `plate_N_small`），否则 Bambu 里盘是空白图。
5. **渲染缩略图**
   - 正交俯视相机，512×512；缩略图用 Blender 自带图像缩放生成 128
     （见 `references/pipeline.md`，不要依赖 macOS 的 `sips`）。
6. **校验**
   - 纯 Python：解压 3MF，检查盘数、每盘实例数、对象文件、ID 顺序、床内边界、间距。
   - 有 Bambu Studio 时再跑一次官方 CLI（跨平台可选）：
     ```bash
     BambuStudio --export-3mf /tmp/rt.3mf project.3mf   # 重导出后检查每盘实例数
     BambuStudio --info project.3mf                     # 对象清单
     ```
   - 判定标准：重导出后每盘 `<plate>` 的 `<model_instance>` 数量与预期一致。

## 常用环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `BAMBU_TEMPLATE` | `bricks/bambu_template` | 配置模板目录 |
| `BED_SIZE` | `256` | 可打印床宽/深（mm），决定盘间距 |
| `BRICKS_BLEND` | `bricks/bricks.blend` | 零件源文件（示例项目） |

## 故障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 打开后只有 1 号盘有零件 | 所有零件都在床中心坐标系 | 按盘网格平移（铁律 2） |
| 只剩一个零件 / 两个件合并 | 对象或 part ID 重复 | 用 `2i` / `2i-1` |
| 盘图空白 | 缺 `plate_N` 缩略图或文件名不匹配 | 补 5 张 PNG |
| 导入报模板错误 | 缺 `project_settings.config` 等 | 换完整模板 |
| 布尔验证误报碰撞 | 共面产生零厚度薄片 | 检查交集体高，`< 0.05 mm` 视为贴合 |
| 薄环体积乱跳 | 0.05 mm 级薄环超出布尔精度 | 用探针/几何测量代替体积 |

## 参考

- `references/3mf-format.md` — 包结构、盘网格、ID 约定、XML 片段
- `references/pipeline.md` — Blender 无头脚本、几何提取、缩略图、跨平台注意
- `references/pitfalls.md` — 实际踩坑记录（含症状与修复）
- `scripts/printpack.py` — 可直接复用的多盘打包器（需要 `brickkit` 风格的 kit 对象）
