# Bambu Studio 3MF 工程格式（多盘）

一个可被 Bambu Studio 打开并切片的工程 3MF 至少包含：

```
[Content_Types].xml
_rels/.rels
3D/3dmodel.model
3D/_rels/3dmodel.model.rels
3D/Objects/object_1.model      (每个零件一个文件)
Metadata/model_settings.config
Metadata/project_settings.config   (打印机/工艺/耗材配置)
Metadata/slice_info.config
Metadata/filament_sequence.json
Metadata/cut_information.xml
Metadata/plate_1.json
Metadata/plate_1.png   plate_no_light_1.png   top_1.png   pick_1.png
Metadata/plate_1_small.png
```

`[Content_Types].xml` 用 `<Default Extension="model" .../>`，因此多零件不需要逐个登记。
`3D/_rels/3dmodel.model.rels` 要为每个 object 文件加一条 `Relationship`。

## ID 约定

第 i 个零件（从 1 开始）：

| 位置 | ID |
|---|---|
| `3D/Objects/object_i.model` 内部 `<object id>` | `2i-1` |
| `3dmodel.model` 里包装对象 `<object id>` | `2i` |
| 包装对象 `<component objectid>` | `2i-1` |
| `model_settings.config` `<object id>` | `2i` |
| `<part id>` | `2i-1` |
| `model_instance` 里 `object_id` | `2i` |

`instance_id` 同一对象多实例时从 0 递增；`identify_id` 全局唯一（本仓库用 `78 + i`）。
ID 重复会导致零件被合并或丢失。

## 多盘：全局坐标系与网格

Bambu 的盘不是独立坐标系。加载时逐个实例判断包围盒与哪个盘的矩形相交
（`PartPlateList::reload_all_objects`）。盘按网格排布：

```
stride = BED_SIZE * (1 + 0.2)          # LOGICAL_PART_PLATE_GAP = 1/5
cols   = ceil-ish sqrt(N)              # compute_colum_count
origin(p) = ( (p % cols) * stride, -(p // cols) * stride )
盘 p 的床范围: [origin.x, origin.x + BED] × [origin.y, origin.y + BED]
```

`cols` 的精确规则：`v = sqrt(N); r = round(v); cols = r+1 if v > r else r`。
例：3 盘 → 2 列（盘 1 `(0,0)`，盘 2 `(307.2,0)`，盘 3 `(0,-307.2)`，床 256）；
7 盘 → 3 列。

要点：

- 把所有零件按上面的 `origin` 平移后再写入 build item，**不要**每盘都居中。
- 盘内排布照常以局部床中心 `BED/2` 为基准，然后整体加 `origin`。
- 全局 Y 为负是正常的（第二行盘在下方）。
- 打印时 Bambu 会按盘裁切，盘与盘之间的零件坐标可以重叠，但同一盘内不能。
- 盘名可写颜色：`<metadata key="plater_name" value="gray"/>`，界面会显示。

## model_settings.config 关键结构

```xml
<config>
  <object id="2">
    <metadata key="name" value="brick_2x6.stl"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="7794"/>
    <part id="1" subtype="normal_part" uuid="...">
      <metadata key="name" value="brick_2x6.stl"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="source_file" value="brick_2x6.stl"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="0"/>
      <metadata key="source_offset_y" value="0"/>
      <metadata key="source_offset_z" value="0"/>
      <mesh_stat face_count="7794" edges_fixed="0" degenerate_facets="0"
                 facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>

  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value="gray"/>
    <metadata key="locked" value="false"/>
    <metadata key="filament_map_mode" value="Auto For Flush"/>
    <metadata key="filament_maps" value="1 1 1 1"/>
    <metadata key="filament_volume_maps" value="0 0 0 0"/>
    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>
    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>
    <metadata key="top_file" value="Metadata/top_1.png"/>
    <metadata key="pick_file" value="Metadata/pick_1.png"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="79"/>
    </model_instance>
  </plate>

  <assemble>
    <assemble_item object_id="2" instance_id="0"
                   transform="1 0 0 0 1 0 0 0 1 0 0 5.7" offset="0 0 0"/>
    <assemble_item object_id="2" volume_id="0"
                   transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
  </assemble>
</config>
```

`<plate>` 块的数量 = 盘数；每个盘块列出属于它的实例。Bambu 重导出时会保留
盘名与缩略图，但不会写 `plate_N.json`（那是 UI 缓存，可写可不写）。

## 3dmodel.model（主模型）

```xml
<model unit="millimeter" ... requiredextensions="p">
  <resources>
    <object id="2" p:UUID="..." type="model">
      <components>
        <component p:path="/3D/Objects/object_1.model" objectid="1"
                   p:UUID="..." transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
      </components>
    </object>
  </resources>
  <build>
    <item objectid="2" transform="1 0 0 0 1 0 0 0 1 130.5 128 5.7" printable="1"/>
  </build>
</model>
```

`3D/Objects/object_1.model` 内的网格应以原点为中心（x/y 居中，z 半高），
build item 的 `z` 偏移 = 高度/2；旋转必须烘焙进顶点，`transform` 只做平移。

## 缩略图

每个盘需要：

| 文件 | 用途 |
|---|---|
| `Metadata/plate_N.png` | 盘缩略图（512 方图，俯视） |
| `Metadata/plate_no_light_N.png` | 无光照版（可同名复制） |
| `Metadata/top_N.png` | 俯视图（可同名复制） |
| `Metadata/pick_N.png` | 拾取掩码（可同名复制） |
| `Metadata/plate_N_small.png` | 128 方图 |

少一张就会出现空白盘预览。渲染方法见 `pipeline.md`。俯视正交相机放在
`(cx, cy, 500)`，`rotation_euler=(0,0,0)`，`ortho_scale = max(w,d)*1.2`。

## 配置模板

`bricks/bambu_template/` 只保留打包必需文件（不含 3D 与图片）：

- 换打印机/工艺：按 `bricks/bambu_template/README.md` 重新生成
- 模板与 `BED_SIZE` 必须匹配，否则盘网格与可打印区域不一致
