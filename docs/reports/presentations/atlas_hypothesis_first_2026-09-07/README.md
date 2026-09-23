> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../presentations/atlas_hypothesis_first_2026-09-07/README.md)。本目录未复制视频或大型资产。

# Atlas：以我的架构假设为主线

这版按用户要求重新确定主线：**先展示认可的原系统架构图，按该假设讲完整，再展示对应的原开源组装图，最后细分部件与项目。**

原系统架构不再被四步简图替代。四步图只在后面的工程实现部分解释“渲染、生成、重建、融合”这一局部子链路。

## 文件入口

- [PPTX：25 页主讲 + 8 页附录](../../../../presentations/atlas_hypothesis_first_2026-09-07/Atlas_以我的架构假设为主线_2026-09-07.pptx)
- [PDF：仅 25 页主讲](../../../../presentations/atlas_hypothesis_first_2026-09-07/Atlas_原架构主线_主讲25页_2026-09-07.pdf)
- [PDF：完整 33 页](../../../../presentations/atlas_hypothesis_first_2026-09-07/Atlas_以我的架构假设为主线_2026-09-07.pdf)
- [逐页讲稿](../../../../presentations/atlas_hypothesis_first_2026-09-07/逐页讲稿.md)
- [三个项目的详细说明](../../../../presentations/atlas_hypothesis_first_2026-09-07/三个项目_当前能力与替换范围.md)
- [原系统架构 SVG 的原样副本](../../../../presentations/atlas_hypothesis_first_2026-09-07/atlas_architecture_synthesis_v2.svg)
- [原开源组装 SVG 的原样副本](../../../../presentations/atlas_hypothesis_first_2026-09-07/atlas_open_source_assembly.svg)

## 这次恢复了什么

1. **第 2 页是完整系统原图**，来源为 `diagrams/atlas_architecture_synthesis_v2.svg`，不是只写一个路径或把原图移到附录。
2. **第 3–7 页先解释用户假设**，包括多模态初始化、首帧参考、首帧 GS 渲染、新相机粗渲染、历史 RGB-D、统一世界模型、两条回写和 4D 时空控制。
3. **第 8 页是完整开源组装原图**，来源为 `diagrams/atlas_open_source_assembly.svg`；HY-World 2.0、Spatia、掩码、动态重建和外围模块都没有被删除。
4. 先在第 9–10 页建立原架构与开源实现的对应，再进入部件细节。明确“统一 RGB-D 模型”是原假设层，“生成器 + 几何预测器”是复现层的功能拆分。
5. WorldWarp、MapAnything、GaME 的详细输入输出、替换范围、本地进展与限制全部保留，放在第 17–21 页及附录。
6. 结尾回到原架构说明下一步，并提供第 2 页 / 第 8 页的回看入口。

## 主讲顺序

| 页码 | 讲什么 | 与原图的关系 |
|---|---|---|
| 01 | 从自己的系统假设出发 | 说明讲述主线 |
| 02 | 完整系统原图 | 原始 SVG 原样展示 |
| 03 | 完整假设的大字讲解版 | 保留初始化、上下文、持久世界、统一模型、融合、4D |
| 04 | 初始化世界与参考记忆 | 原图上层 |
| 05 | 小幅换相机与三组图像条件 | 原图中层的条件生成 |
| 06 | 新内容写回世界与历史 | 原图中层的两条反馈 |
| 07 | 固定 t 换 C / 固定 C 推进 t | 原图下层的 4D 分支 |
| 08 | 完整原开源组装图 | 原始 SVG 原样展示 |
| 09–10 | 功能一一对应与实现拆分 | 不让项目选型反向改写系统假设 |
| 11–15 | 渲染、生成、几何、融合、双路记忆 | 按已解释的架构逐个细分 |
| 16 | 本地静态核心子链路 | 仅是原图中层的实现路径 |
| 17–21 | 三个项目的能力、输入输出与替换关系 | WorldWarp、MapAnything、GaME 各自归位 |
| 22–24 | 本地实测、缺失接口、验收顺序 | 区分设计与已完成工作 |
| 25 | 回到完整系统假设 | 固定时间，两轮共享世界，再扩展动态 |
| A1–A8 | 按问题查看技术细节 | 模型机制、格式、命令、备选、4D、能力边界与来源 |

建议主讲约 30 分钟。第 2、8 页用来展示全貌和指认区域，不要求现场逐字读完；后续大字页逐层展开，保持整体与细节的对应关系。讲稿采用适合用户本人讲述的第一人称。

## 保留的假设，而不是替用户重设架构

原系统假设的完整内容是：

- 输入支持单图、多图、文本及其他多模态条件。
- 先通过 Marble 式能力生成与输入一致的局部区域，得到初始 GS 与参考。
- 移动目标相机，从已有 GS 得到大部分内容仍保留的粗图；同时保留首帧参考和首帧 GS 渲染，再结合历史、相机与时间。
- 统一世界模型按 AR 方式组织生成，综合版保留新 RGB 与深度输出。
- 新几何对齐旧世界并更新 GS；新帧与相机同时进入历史；下一轮复用更新世界。
- 4D 保留固定时间换相机、固定相机推进时间两类操作，以及静态背景与动态层。

该功能架构是用户假设与此前官网信息的综合推演，不把未披露的持久 GS 内部算法当成官方事实。本次整理重点是忠实呈现与讲解，没有再次改变这套假设，也没有开展一轮新的开源选型。

原开源图的日期 / 版本标签按原文件保留，属于原调研快照。实际安装与验证仍以 [WorldWarp 部署记录](../../archive/WORLDWARP_SETUP.md)、[几何链路记录](../../archive/GEOMETRY_SETUP.md) 为准；当前没有因为放回原图就声称 HY、Spatia、SAM 或动态分支已安装联调。

## 原图嵌入与文件保护

两张图都按完整比例放入 PPT 第 2 页和第 8 页，保留全图内容。PPTX 包内嵌入的 SVG 字节与 `diagrams/` 的源文件一致，并带高分辨率 PNG 回退，兼容不支持 SVG 的阅读器。不是仅将原图截图后丢掉矢量源。

PDF 中原图同样以矢量方式绘制。为适应宽屏版面，完整竖向原图会缩放展示；原尺寸 SVG 同时放在本目录，便于独立打开阅读。

后续讲解页的文字、框、箭头和表格为 PPTX 原生可编辑对象；原图作为完整矢量对象保留。原图内容没有被本地进度标签覆盖，相关解释放在旁边或后续页。

全部旧版 PPTX、PDF、讲稿和 `diagrams/` 中的 SVG 均不覆盖。保护文件 SHA-256 和两张原图在 PPTX 包内的 SHA-256 见 [manifest.json](../../../../presentations/atlas_hypothesis_first_2026-09-07/manifest.json)，结构校验见 [validation.json](../../../../presentations/atlas_hypothesis_first_2026-09-07/validation.json)。

## 渲染与校验说明

PDF / PNG / SVG 与 PPTX 使用相同的布局源；当前没有 Office / LibreOffice，**PDF 不是用 Office 实际渲染导出**。PPT 字体为 Noto Sans CJK SC，其他电脑上的字体替换可能改变外观。

校验包括页数、备注、页序、文本溢出、缺字、越界、XML、原图嵌入一致性与旧文件哈希。逐页预览和联系表在 `previews/`。

## 本版运行说明与构建

本轮仅改演示与讲稿，没有改 WorldWarp、MapAnything、GaME 源码、Conda、权重或 GPU 运行状态。三个项目的实际启动方式仍见部署记录；附录中的示例折行用于展示，完整可复制命令见 [上一项目详解版 README](../../../../presentations/atlas_framework_projects_2026-09-07/README.md)。

重新构建只写本目录，复用之前的本地布局定义但不会运行其输出入口：

```bash
/home/sumai/.local/bin/uv run \
  --with python-pptx --with pillow --with cairosvg --with pypdf --with numpy \
  python /data4/sumai/GIL_ATLAS/presentations/atlas_hypothesis_first_2026-09-07/build_deck.py
```
