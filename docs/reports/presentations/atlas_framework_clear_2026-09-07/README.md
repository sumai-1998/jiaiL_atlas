> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../presentations/atlas_framework_clear_2026-09-07/README.md)。本目录未复制视频或大型资产。

# Atlas：从整体到细节 · 讲解版

这版以“讲得顺”为目标重做，保留原技术假设，但将内容改为 **20 页主讲 + 6 页技术附录**。旧目录的 PPTX、PDF 和 `diagrams/` 下所有旧 SVG 均不覆盖。

## 先打开哪个文件

- [PPTX：完整讲解版，含逐页演讲者备注](../../../../presentations/atlas_framework_clear_2026-09-07/Atlas_从整体到细节_讲解版_2026-09-07.pptx)
- [PDF：只含 20 页主讲，适合直接讲](../../../../presentations/atlas_framework_clear_2026-09-07/Atlas_主讲20页_2026-09-07.pdf)
- [PDF：完整 26 页，含技术附录](../../../../presentations/atlas_framework_clear_2026-09-07/Atlas_从整体到细节_讲解版_2026-09-07.pdf)
- [逐页讲稿：开场句、展开讲、过渡句](../../../../presentations/atlas_framework_clear_2026-09-07/逐页讲稿.md)
- [简明系统总图 SVG](../../../../presentations/atlas_framework_clear_2026-09-07/Atlas_系统总图_简明版.svg)
- [简明开源组装图 SVG](../../../../presentations/atlas_framework_clear_2026-09-07/Atlas_开源组装图_简明版.svg)

## 怎么讲

建议主讲约 25 分钟。不要先解释所有项目，也不必逐项念参考文献。

| 页码 | 讲述任务 | 建议用时 |
|---|---|---|
| 01–03 | 定义目标：为什么需要一个可回看的世界 | 2 分钟 |
| 04–06 | 展示总图，区分官网信息与工程假设，说明初始化 | 5 分钟 |
| 07–12 | 沿“①渲染 → ②生成 → ③重建 → ④融合”逐步展开 | 8 分钟 |
| 13–16 | 在相同框架上放入开源组件，并展示已完成测试 | 5 分钟 |
| 17–20 | 明确待接接口、验收顺序与 4D 扩展，收束结论 | 5 分钟 |
| A1–A6 | 按问题跳转，不作为主讲的连续内容 | 问答时使用 |

讲述时反复回到一句话：**生成的新内容，要写回同一个世界，成为下一轮的约束。**

需要解释模块时，用对应页的输入、输出和作用；需要回答实现问题时，再跳到附录。每页备注已有可以直接接到下一页的过渡句。

## 相对旧版的主要调整

1. 第 4 页就给完整闭环，不等讲完模型术语和项目清单才给总图。
2. 一套固定名称、颜色和顺序贯穿总览、模块细节、开源组装与总结。
3. 主讲去掉密集备选清单、命令、张量格式和大段条件说明；这些转到附录和备注。
4. 用本地实际图像、预测深度和 GS 重渲染说明当前成果，避免纯文字描述安装状态。
5. 单独说明 WorldWarp 已有局部几何与 GS，MapAnything + GaME 不是它的完整生成替代品。
6. 保留原始 Spatia 候选路线；本次首次闭环联调优先使用已运行的 WorldWarp，明确这是本地 MVP 的实施顺序调整。
7. 明确区分“已跑通一次多帧几何写回”和“跨轮恢复同一地图、接回生成器”。后者仍待实现。

## 技术与证据边界

这份演示基于用户的系统综合假设、既有开源调研、2026-09-07 的本地状态记录，以及本次重新读取的 [Atlas 官网](https://www.worldlabs.ai/blog/atlas)。它是一套与已披露能力相容的功能分解与复现方案，不声称还原了官方未公开的 GS 内环、完整融合算法或网络拆分。

“先固定时间换视角，再固定视角推进时间”作为工程调度方式保留；不把它写成已证实的空间与动态表示完全解耦。

已安装和验证的几何主链是 MapAnything + GaME；没有在本次整理演示文稿时继续安装其他模型、修改 ML 环境或执行新的 GPU 实验。所有实测数值来自已有记录，属于低分辨率、小样本安装验证，不是项目间质量 / 速度排名。

### 本地证据索引

- [系统综合图 v2](../../../../diagrams/atlas_architecture_synthesis_v2.svg)：用户认可的功能假设基准。
- [原开源组装图](../../../../diagrams/atlas_open_source_assembly.svg) 与 [调研清单](../../archive/ATLAS_OPEN_SOURCE_ASSEMBLY_2026-09-06.md)：原候选角色与研究路线。
- [GEOMETRY_SETUP.md](../../archive/GEOMETRY_SETUP.md)：环境、权重、许可证、使用入口、相机约定、验证范围。
- [安装清单](../../../../setup_logs/geometry_install/manifest.json)：锁定版本与验收记录。
- [MapAnything 测试报告](../../../../geometry_outputs/install_smoke_2026-09-07/mapanything_default/report.json)：3 帧输入，84,245 个聚合点。
- [GaME 测试报告](../../../../geometry_outputs/install_smoke_2026-09-07/game_worldwarp/report.json)：18,991 个 GS，场景重载与渲染通过。
- [WorldWarp 本地记录](../../archive/WORLDWARP_SETUP.md)；源码 `WorldWarp/pose_control.py:1249` 的 `run_inference_chunk`，以及 `WorldWarp/src/ttt3r/ttt3r.py:1573` / `:1787` 的 GS 初始化与新建 warper：当前逐段局部 GS 的依据。
- [几何推理包装器](../../../../scripts/infer_geometry.py) 与 [GaME 适配器](../../../../scripts/fuse_geometry_game.py)：当前 RGB 入口、默认帧数、场景创建与导出方式。
- [相机适配器](../../../../scripts/game_camera_adapter.py)：完整 K 的投影约定；传入 GaME 前须将 OpenCV c2w 求逆为 w2c。

### 实测图片说明

第 7、9、16 页使用 `geometry_outputs/install_smoke_2026-09-07/` 的既有结果：

- `assets/input_rgb.png`：`mapanything_default/posed_rgbd.npz` 的第 0 帧 RGB，也就是 WorldWarp 既有生成视频中选出的输入图像之一。
- `assets/predicted_depth.png`：同一 NPZ 的第 0 帧 z-depth，按有效像素的 2–98 百分位归一化着色；仅作预测几何可视化，无效区域为灰色。
- `assets/gs_render.png`：`game_worldwarp/render_000.png` 的副本，为同一输入相机的 GS 重渲染。不是 Atlas 输出，也不是专门的新视角泛化测试。

展示的 RGB 与深度为同一帧中间结果；重渲染分辨率更低。图像数量是 3、点数是 84,245、GS 数是 18,991，分别对应三个不同统计量。第二轮渲染图再重建的既有验证创建了新场景，未验证跨轮同一地图融合。

## 附录 A3：可复制的运行示例

以下是使用说明，不是本次新执行的实验。输入目录需替换；输出目录应使用未占用的新名字。GPU 编号应先检查当前空闲情况，再通过 `CUDA_VISIBLE_DEVICES` 选择，不能假定过去的测试卡仍空闲。

```bash
cd /data4/sumai/GIL_ATLAS

./run_mapanything.sh \
  --images /path/to/images \
  --source-kind generated \
  --output geometry_outputs/my_scene/geometry \
  --max-views 3

./run_game.sh \
  --rgbd geometry_outputs/my_scene/geometry/posed_rgbd.npz \
  --output geometry_outputs/my_scene/gs \
  --max-views 3 \
  --max-width 224 \
  --iterations 20
```

`--source-kind` 按真实来源选 `generated`、`rendered` 或 `observed`。这里两步都取 3 帧只是为了匹配小测试；MapAnything 默认最多取 8 帧，GaME 默认取 3 帧。输入不要求固定 3 帧，但当前包装器没有无限流和跨调用地图恢复能力。GaME 原生每个关键帧还会执行 50 次 warmup，`--iterations 20` 并非总优化步数。

## 文件可编辑性与验证

PPTX 的文字、框、箭头和表格均为原生可编辑对象；实际 RGB / 深度 / 渲染图作为图片嵌入。每页带中文演讲者备注。

PDF 和 SVG 来自同一套布局数据，正文为矢量文字与线框。**当前环境没有 PowerPoint / LibreOffice；PDF 与预览不是由 Office 实际渲染导出。** 已进行文字框高度与宽度检查、字体缺字检查、对象越界检查、PPTX XML 结构检查、页数 / 备注检查，并查看全部页面联系表。Office 中的最终字体效果取决于是否安装 `Noto Sans CJK SC`，个别字体替换可能改变视觉。

每页 SVG / PNG / PDF 位于 `previews/`；联系表为 `contact_sheet_01.png` 至 `04.png`。结构检查结果见 [validation.json](../../../../presentations/atlas_framework_clear_2026-09-07/validation.json)，保护的旧文件 SHA-256、来源和页序见 [manifest.json](../../../../presentations/atlas_framework_clear_2026-09-07/manifest.json)。

### 重新生成本版

只在当前新目录生成演示文件，不写入旧版目录：

```bash
/home/sumai/.local/bin/uv run \
  --with python-pptx --with pillow --with cairosvg --with pypdf --with numpy \
  python /data4/sumai/GIL_ATLAS/presentations/atlas_framework_clear_2026-09-07/build_deck.py
```

布局依赖使用独立的 uv 临时环境，不改变 WorldWarp、MapAnything 或 GaME 的 Conda 环境。
