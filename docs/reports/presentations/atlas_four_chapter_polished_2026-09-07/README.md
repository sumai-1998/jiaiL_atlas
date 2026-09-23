> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../presentations/atlas_four_chapter_polished_2026-09-07/README.md)。本目录未复制视频或大型资产。

# Atlas：四章递进讲解版

按「总体架构 → 功能拆解 → 开源替代与复现路线 → 本地 WorldWarp」重排与润色。主讲 26 页，技术附录 8 页；共 34 页，每页有演讲者备注与过渡句。

## 打开哪份

- [完整 PPTX](../../../../presentations/atlas_four_chapter_polished_2026-09-07/Atlas_总体架构_功能拆解_开源复现_WorldWarp实证_2026-09-07.pptx)：可编辑框图、表格与正文；第 24 页内嵌真实教室视频。
- [主讲 PDF：26 页](../../../../presentations/atlas_four_chapter_polished_2026-09-07/Atlas_四章主讲26页_2026-09-07.pdf)：按顺序讲到结论，不含附录。
- [完整 PDF：34 页](../../../../presentations/atlas_four_chapter_polished_2026-09-07/Atlas_总体架构_功能拆解_开源复现_WorldWarp实证_2026-09-07.pdf)：包含技术问答材料。
- [逐页讲稿](../../../../presentations/atlas_four_chapter_polished_2026-09-07/逐页讲稿.md)：每页按「开场句、展开讲、过渡句」组织。
- [WorldWarp 本地部署与演示说明](../../../../presentations/atlas_four_chapter_polished_2026-09-07/WorldWarp_本地部署与演示.md)：启动方式、精确案例入口、输出与复现记录。
- [单独播放教室视频](../../../../presentations/atlas_four_chapter_polished_2026-09-07/assets/WorldWarp_classroom_4chunks_10.7s.mp4)：321 帧、10.7 秒，已复制到本目录。

目录与文件名保留开始制作时的 2026-09-07 日期；跨午夜后的交付检查于 2026-09-08 完成。

## 按这个顺序讲

| 章节 | 页码 | 要回答的问题 |
|---|---|---|
| 01 总体架构 | 1–3 | 系统整体是什么？初始化、空间闭环与 4D 怎么放在一起？ |
| 02 功能拆解 | 4–9 | 初始化、渲染、生成、融合、双路记忆与时空控制各自收什么、出什么？ |
| 03 开源替代与复现路线 | 10–21 | 哪些项目承担这些功能？怎样组合、接接口、分阶段验收？ |
| 04 本地 WorldWarp | 22–26 | 本地部署了什么、怎么运行、实际生成了什么、接回总架构还要做什么？ |
| 附录 | 27–34 | AR / 扩散、数据格式、命令、备用项目、4D、替代矩阵、帧数与证据 |

建议主讲约 30 分钟：总体架构 4 分钟，功能拆解 7 分钟，开源与路线 13 分钟，本地 WorldWarp 6 分钟。附录按问题跳转，不必逐页讲。

第 2 页完整保留原系统图，第 3 页用大字简图读一遍闭环。第 10 页完整保留原开源组装图，后面再展开替代关系。两张原 SVG 未裁减内容，既嵌入 PPTX，也随文件独立提供：

- [系统综合图 v2](../../../../presentations/atlas_four_chapter_polished_2026-09-07/atlas_architecture_synthesis_v2.svg)
- [开源组装原图](../../../../presentations/atlas_four_chapter_polished_2026-09-07/atlas_open_source_assembly.svg)

第三章的 WorldWarp 页面只讲其功能、替代位置与接口。环境、权重、运行、视频和本地资产集中在第四章，避免打断架构主线。每个项目统一按「能力 → 替代位置 → 接入边界」讲。

## 这版的事实与设计口径

系统层仍是用户的综合架构假设；官网披露、工程推演、开源候选和本地已验证进度分开表述。本次主要整理既有调研和本地证据，没有新增一轮全量开源选型或宣称所有候选均已安装。

本地进度更新采用已有的 9 月 7 日教室四段报告：480×608、30 fps、321 帧、10.7 秒。本轮只读取、检查并复制该视频，没有重新执行 GPU 生成，也没有改动项目源码、Conda 或权重。

MapAnything + GaME 已验证的是小样本几何子链路；「跨轮写回同一张地图并接回生成器」仍是下一阶段工作。WorldWarp 的逐段局部 GS 不直接等价于永久全局地图。

## 附录 A3：可复制的几何子链路命令

以下仅供运行参考，本轮未执行。先选择空闲 GPU，替换真实图片路径，并使用新的输出目录。`my_scene_new` 是示例名称，执行前确认不存在。

```bash
cd /data4/sumai/GIL_ATLAS

./run_mapanything.sh \
  --images /path/to/images \
  --source-kind generated \
  --output geometry_outputs/my_scene_new/geometry \
  --max-views 3

./run_game.sh \
  --rgbd geometry_outputs/my_scene_new/geometry/posed_rgbd.npz \
  --output geometry_outputs/my_scene_new/gs \
  --max-views 3 \
  --max-width 224 \
  --iterations 20
```

`--source-kind` 按真实来源选择 `generated`、`rendered` 或 `observed`；它记录来源，不是生成算法开关。两个 `--max-views` 一起设置。GaME 会筛选关键帧，并执行每帧原生 50 次 warmup；三帧、224 宽度和 20 次额外迭代是安装验证级配置，不是质量推荐值。

## 证据索引

| 内容 | 原始依据 |
|---|---|
| 综合系统假设 | [系统原图](../../../../diagrams/atlas_architecture_synthesis_v2.svg) |
| 原始项目组装方案 | [开源调研](../../archive/ATLAS_OPEN_SOURCE_ASSEMBLY_2026-09-06.md)、[组装原图](../../../../diagrams/atlas_open_source_assembly.svg) |
| WorldWarp 环境、权重与早期验收 | [部署记录](../../archive/WORLDWARP_SETUP.md)、[启动脚本](../../../../run_worldwarp.sh) |
| WorldWarp 单段内部流程 | [pose_control.py](../../../../WorldWarp/pose_control.py)：`WanVideoGenerator._load_models`、`run_inference_chunk` |
| 连续相机与四段案例 | [旋转脚本](../../../../scripts/generate_worldwarp_rotation.py)、[分段轨迹](../../../../WorldWarp/chunk_trajectory.py) |
| 四段参数与实际结果 | [案例说明](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/README.md)、[生成报告](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/report.json)、[检查记录](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/inspection/validation.json) |
| MapAnything / GaME 本地验收 | [GEOMETRY_SETUP.md](../../archive/GEOMETRY_SETUP.md) |
| MapAnything 当前输入输出 | [infer_geometry.py](../../../../scripts/infer_geometry.py)：`main` |
| GaME 当前掩码、相机与状态处理 | [fuse_geometry_game.py](../../../../scripts/fuse_geometry_game.py)：`main` |

本目录中的 [manifest.json](../../../../presentations/atlas_four_chapter_polished_2026-09-07/manifest.json) 记录逐页来源、案例报告、视频元数据以及受保护旧文件的 SHA-256。官网与各项目的外部链接也保留在逐页备注中。

## 排版、媒体与保存验证

已核对 34 页顺序与备注、26 / 34 页 PDF、文字框溢出、缺字、对象越界、PPTX XML 和重复 ZIP 条目；原 SVG 与内嵌 SVG 字节一致，原 MP4 与内嵌视频字节一致。受保护的旧 PPTX / PDF / SVG 和本地实验文件没有改动。详见 [validation.json](../../../../presentations/atlas_four_chapter_polished_2026-09-07/validation.json)。

框图、表格、箭头与正文采用 PPTX 原生对象；完整原 SVG 附带 PNG 兼容回退，原图内部不会自动拆成单独的 PPT 形状。字体为 Noto Sans CJK SC，接收端字体替换可能改变排版。

PDF / SVG / PNG 和 PPTX 共用布局数据。当前机器没有 Office / LibreOffice，因此 PDF **不是 Office 实际渲染导出**；已检查静态预览，但未在 Office 中测试内嵌视频播放。PDF 显示视频中间帧；客户端若不支持播放，请直接打开随附 MP4。

## 重建本版本

构建器只复用历史布局源，所有输出重定向到本目录；不会运行历史版本的保存入口。构建依赖通过隔离的 uv 环境提供，不修改 ML Conda。

```bash
/home/sumai/.local/bin/uv run \
  --with python-pptx --with pillow --with cairosvg --with pypdf --with numpy \
  python /data4/sumai/GIL_ATLAS/presentations/atlas_four_chapter_polished_2026-09-07/build_deck.py
```
