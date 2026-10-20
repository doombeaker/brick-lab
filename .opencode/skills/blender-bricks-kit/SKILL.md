---
name: blender-bricks-kit
description: brick-lab（原 blender-bricks）积木套件的规格与建模流程：15 种砖的尺寸、腔径/过盈、网格与分层放置、基于现有砖创建新模型（战舰、小屋这类项目）。当用户要查砖型尺寸、调整配合松紧、复用积木做新模型或核对规格一致性时使用。
---

# brick-lab 积木套件

一套 8 mm 间距、FDM 可打印的 LEGO 兼容积木：15 种类型，全部由
`bricks/build_bricks.py` 参数化生成，示例项目见 `examples/warship` 与
`examples/cottage`。

## 事实来源（不要凭记忆写尺寸）

| 文件 | 作用 |
|---|---|
| `bricks/bricks.json` | 面向文档/外部工具的规格表（类型、footprint、高度、配合、颜色） |
| `bricks/build_bricks.py` | 真正的几何生成器（布尔、凸点、腔体、离合管） |
| `bricks/bricks.blend` | 生成结果，示例项目直接复用它的网格 |
| `tools/check_specs.py` | 从 blend 实测并与 `bricks.json` 对比，防止规格漂移 |

改参数时必须同时改 `build_bricks.py` 和 `bricks.json`，然后跑：

```bash
blender -b --factory-startup -P bricks/build_bricks.py
blender -b --factory-startup -P bricks/verify_assembly.py
blender -b --factory-startup -P tools/check_specs.py
blender -b --factory-startup -P bricks/export_bricks_3mf.py
```

## 关键常量

| 常量 | 值 | 说明 |
|---|---|---|
| 凸点间距 `PITCH` | 8.0 mm | 真 LEGO 比例 |
| 单侧间隙 `GAP` | 0.2 mm | 每块砖外轮廓比格宽小 0.2（7.8 / 15.8 …） |
| 凸点名义半径 | 2.4 mm | 实际打印半径 2.25 → **OD 4.5** |
| 凸点高度 | 1.8 mm | |
| 砖高 / 板高 | 9.6 / 3.2 mm | 一层砖 = 3 个 3.2 层 |
| 砖壁厚 | 1.5 mm | 板自动减到 1.3，保证凸点能进入 |

## 15 种砖（速查）

砖：`brick_1x1`、`brick_1x2`、`brick_2x2`、`brick_2x4`、`brick_2x6`
斜面：`slope_2x2_45`（单坡，前两钉有让位柱，后两钉下有离合管）
圆柱：`round_brick_1x1`
板：`plate_1x2`、`plate_2x2`、`plate_2x4`、`plate_2x6`、`plate_4x8`、`plate_8x8`、`plate_6x12`
光面：`tile_2x2`（底部 4 个盲腔）

完整尺寸/配合表见 `references/brick-specs.md`。

## 配合（以实打反馈为准）

| 类型 | 参数 | 手感 |
|---|---|---|
| 1x1 方、圆 1x1 | 腔 4.40 | 过盈 0.05/边，卡紧不掉 |
| 1x2 砖 | 腔 4.45 | 过盈 0.025/边 |
| 标准 2xN 砖、所有带管板 | 管孔 4.80 | 标准间隙 0.15/边 |
| 斜面 | 管孔 4.60 | 间隙 0.05/边（小孩可手推） |
| tile | 盲腔 4.46 × 1.9 深 | 轻微过盈 |

调整历史与判断方法见 `references/clutch-tuning.md`。

## 新建一个模型项目

1. 复制脚手架（以战舰为模板）：
   ```bash
   cp -r examples/warship examples/my-model
   rm -rf examples/my-model/renders examples/my-model/*.blend examples/my-model/*.3mf
   ```
2. 改 `design.py`：只写 `k.place(...)` 调用。
3. 改 `make_all.py` 里的标题/输出名。
4. 运行：
   ```bash
   blender -b --factory-startup -P examples/my-model/make_all.py
   ```
   产物：`design` 渲染、分层图、`BOM.md`、`PRINT.md`、打印 3MF。
5. 校验：
   ```bash
   blender -b --factory-startup -P tools/check_consistency.py
   ```

导出环节（多盘 3MF）由 `blender-bambu-3mf` skill 负责，`make_all.py` 已经调用了
其中的 `printpack`。

## 放置 API（`brickkit.py`）

```python
k.place(unit, gx, gy, zl, color, rot=0)
```

- `gx, gy`：砖左下角的**格坐标**（stud 索引），不是毫米
- `zl`：起始层号；1 层 = 3.2 mm，砖占 3 层、板/光面占 1 层
- `rot`：0/90/180/270，footprint 自动交换
- 放置时自动做：碰撞检查、支撑警告、凸点网格占用、BOM 计数
- `k.step_renders(dir)`：逐层说明图（白色=已完成，彩色=本层）
- `k.bom_markdown(path, title)`：按颜色 + 按砖型清单

## 设计约束

- **纯 stud-up**：只能从上方扣；没有侧面凸点，做不了正面五官/侧向连接
- 斜面只有后排 2 个凸点可用；tile 顶部无凸点
- 1 格宽的件放不下离合管（管 OD 6.4 > 内腔），只能靠收紧腔体
- 大板（4x8 以上）建议做底座；单块最长为 `plate_6x12`（95.8 × 47.8 mm）
- 每个项目 ≤ 50 块是舒适上限（打印盘数与拼装时间）

## 参考

- `references/brick-specs.md` — 15 种砖完整参数表
- `references/clutch-tuning.md` — 配合调整历史、FDM 收缩经验
- `references/project-scaffold.md` — 脚手架文件、层级数学、校验流程
