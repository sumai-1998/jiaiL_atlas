> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../presentations/atlas_framework_projects_2026-09-07/README.md)。本目录未复制视频或大型资产。

# Atlas：框架与三个项目详解版

在上一份简明讲解版的基础上，加入 WorldWarp、MapAnything、GaME 的当前能力、输入输出、可替代职责和缺失接口。**24 页主讲 + 8 页附录，共 32 页**。此前两个版本的 PPTX / PDF 与旧 SVG 均保持不变。

## 文件

- [完整 PPTX：可编辑，32 页均有演讲者备注](../../../../presentations/atlas_framework_projects_2026-09-07/Atlas_框架与三个项目详解_2026-09-07.pptx)
- [主讲 PDF：24 页](../../../../presentations/atlas_framework_projects_2026-09-07/Atlas_项目详解_主讲24页_2026-09-07.pdf)
- [完整 PDF：32 页](../../../../presentations/atlas_framework_projects_2026-09-07/Atlas_框架与三个项目详解_2026-09-07.pdf)
- [逐页讲稿](../../../../presentations/atlas_framework_projects_2026-09-07/逐页讲稿.md)
- [三个项目：当前能力与替换范围详解](../../../../presentations/atlas_framework_projects_2026-09-07/三个项目_当前能力与替换范围.md)

## 新增内容在哪里

| 页码 | 内容 |
|---|---|
| 15 | 用户要求的项目 / 输入 / 输出 / 作用对照表 |
| 16 | WorldWarp：当前可用能力、自带几何与局部 GS、能承担的生成职责 |
| 17 | MapAnything：几何输出、可替代的前端、模型与当前 CLI 的区别 |
| 18 | GaME：地图更新、场景状态、原生变化适应与当前静态验证边界 |
| 19 | 原 WorldWarp 与目标组合的模块替换图 |
| A6（30） | 按框架任务列出的替换范围矩阵 |
| A7（31） | 帧数、掩码、相机与跨轮状态限制 |

主讲第 01–14 页保持原来的“总览 → 单轮机制 → 组装总图”顺序；第 15–19 页集中解释三个项目；第 20–24 页回到本地验证、接线任务、验收与 4D 扩展。建议主讲约 30 分钟。

不需要把详细说明逐段念出来：主讲每个项目按“当前能干什么 → 能替代哪里 → 还缺什么”三句话展开，具体参数、源码依据和边界放到备注与附录中回答。

## 关键校准

- WorldWarp 不只是视频模型：它内部已有 TTT3R/CUT3R、局部 GS 优化与渲染。当前每段重建局部缓存，不能直接讲成跨轮永久全局地图。
- MapAnything 是几何预测前端：当前包装器只接 RGB，虽然原模型还支持相机、深度等条件。它导出的聚合点云不是已经训练好的 GS，也不是长期 SLAM 图。
- GaME 是地图后端：原生可恢复场景状态并处理场景变化，但现有 CLI 每次新建场景，当前 mask 为全图静态。三帧安装测试没有覆盖完整场景变化、跨轮续图与连续 4D。
- MapAnything + GaME 更适合替换 / 扩展 WorldWarp 的几何与局部建图部分，不替换它的完整生成模块。接口、坐标与状态仍须适配。

这些结论基于本轮重新读取的本地代码、已有验收记录和官方方法页；本轮没有重新执行 GPU 实验。完整证据和说明见配套详解。

## 可编辑性与校验

框图、表格、箭头和文字为 PPTX 原生对象，实际测试图为图片。全部 32 页含中文讲稿与过渡句。

PDF / SVG / PNG 与 PPTX 使用同一套布局数据；当前环境没有 Office / LibreOffice，**它们不是通过 Office 实际渲染导出的 PDF**。字体使用 Noto Sans CJK SC，接收端字体替换可能改变外观。

校验包括页数、演讲者备注、页序、文字框溢出、缺字、对象越界、PPTX XML 以及旧文件 SHA-256；结果见 [validation.json](../../../../presentations/atlas_framework_projects_2026-09-07/validation.json)。各页预览与联系表在 `previews/`，来源和保护文件清单见 [manifest.json](../../../../presentations/atlas_framework_projects_2026-09-07/manifest.json)。

## 构建

本目录构建器复用上一版已创建的本地布局源，但将所有输出重定向到**本目录**；不会执行上一版的输出入口。构建依赖走独立 uv 环境，不改变三个项目的 Conda。

```bash
/home/sumai/.local/bin/uv run \
  --with python-pptx --with pillow --with cairosvg --with pypdf --with numpy \
  python /data4/sumai/GIL_ATLAS/presentations/atlas_framework_projects_2026-09-07/build_deck.py
```

## 附录 A3 的可复制运行示例

以下仅为说明，未在本轮执行。替换输入路径、使用新的输出目录，并在检查空闲 GPU 后自行设置 `CUDA_VISIBLE_DEVICES`。

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

`--source-kind` 按实际来源选择 `generated`、`rendered` 或 `observed`。两个 `--max-views` 需一起设置；GaME 还会筛选关键帧，并执行每帧原生 50 次 warmup。

WorldWarp 使用 `./run_worldwarp.sh` 启动 GUI，再上传起始图与选择相机轨迹；GPU 和端口应在运行时选择，不能假定既往验收设置仍空闲。完整入口仍见 [WorldWarp 部署记录](../../archive/WORLDWARP_SETUP.md) 与 [几何链路部署记录](../../archive/GEOMETRY_SETUP.md)，本版本未修改这些脚本。
