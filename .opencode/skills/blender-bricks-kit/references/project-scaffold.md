# 项目脚手架与层级数学

`examples/warship` 和 `examples/cottage` 使用同一套结构，复制即可建新项目。

```
examples/<name>/
  design.py      # 只写 k.place(...) 的模型定义
  brickkit.py    # 网格放置 / 校验 / 渲染 / BOM（复制自其它示例）
  printpack.py   # 多盘 3MF 打包（复制自其它示例）
  make_all.py    # 入口：build + renders + steps + BOM + 3MF
  BOM.md         # 生成物：按颜色/砖型清单
  PRINT.md       # 生成物：分盘打印计划
  <name>.blend   # 生成物：场景
  renders/       # 生成物：总览图 + steps/step_NN.png
  <name>_print.3mf  # 生成物：打印工程
```

## 层级数学（最容易错的地方）

- 场景单位 mm；一层 = 3.2 mm。
- `zl` 是**起始层索引**：
  - 板 / 光面：占 1 层，`zl` 到 `zl`
  - 砖 / 斜面 / 圆柱：占 3 层，`zl` 到 `zl+2`
- 叠放 = 下一块 `zl = 上一块 zl + 3`（砖上砖）或 `+1`（砖上板）。
  例：地面砖 `zl=0`，第二层砖 `zl=3`，甲板板 `zl=6`，甲板上的砖 `zl=7`。
- 写错会出现 `collision at (x,y,z)`，这是保护机制，不要绕过。

## 格坐标

`k.place(unit, gx, gy, zl, color, rot=0)`

- `gx, gy` 是 stud 单元格索引（可为负），不是毫米。
- 外形尺寸 = `nx*8-0.2` × `ny*8-0.2`；砖中心在 `gx*8 + nx*4`。
- `rot=90/270` 时 footprint 交换（2x6 → 6x2）。

## brickkit 提供的功能

| 方法 | 说明 |
|---|---|
| `place(...)` | 放置 + 碰撞/支撑检查 + BOM 计数 |
| `studio()` | 地面、世界光、太阳光、EEVEE、曝光 |
| `render(path, direction)` | 正交等轴测总览 |
| `step_renders(dir)` | 每层一张：白色=已完成，彩色=本层 |
| `bom_markdown(path, title)` | 按颜色 + 按砖型清单 |
| `report()` | 控制台打印总数与 BOM |

模板网格来自 `bricks/bricks.blend`（`BRICKS_BLEND` 可覆盖），所以尺寸永远与
基础砖一致。

## make_all.py 的顺序

1. `BrickKit()` → `design.build(k)` → `k.report()`
2. `k.studio()` + 三个总览渲染
3. `k.step_renders(...)` 分层说明图
4. `k.bom_markdown(...)`
5. `printpack.write_project(...)` → 打印 3MF（按颜色分盘）
6. `printpack.write_print_plan(...)`
7. 保存 `.blend`

## 校验

```bash
# 单项目：尺寸/凸点/配合
blender -b --factory-startup -P tools/check_specs.py

# 跨项目：.blend 网格多集一致 + 3MF 零件指纹 + BOM 数量
blender -b --factory-startup -P tools/check_consistency.py
```

`check_consistency.py` 会把每个 3MF 零件匹配到 `(砖型, 旋转)`，因此能抓到
"用了旧 geometry" 或"改了砖但忘了重新生成示例"。

## 设计提示

- 先画侧视/俯视草图，再转成格坐标；尽量用大件减少拼缝。
- 每层砖尽量错缝（相邻层砖缝不重合），结构更稳。
- 承重/拿取位置用 2xN 砖；1x1/圆砖只做细节。
- 先用 `step_renders` 检查每层是否可实际放进去（有没有被上层挡住）。
