> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../presentations/atlas_framework_reproduction_2026-09-06/README.md)。本目录未复制视频或大型资产。

# Atlas：框架解析与复现路径

研究快照：2026-09-06。40 页，16:9，适合技术团队评审与复现立项讲解。

## 交付内容

- `Atlas_框架解析与复现路径_2026-09-06.pptx`：正文文字、表格和流程框图为 PowerPoint 原生可编辑元素；包含逐页讲者备注、可点击来源。
- 同名 `.pdf`：便于直接阅读与分享，网页来源可点击。
- `讲解备注.md`：逐页技术讲解和对应来源。
- `build_deck.py`：生成源码。
- `manifest.json`：页标题、参考来源与原 SVG 的 SHA-256。
- `validation.json`：结构检查结果。
- `previews/contact_sheet_*.png`：全篇排版缩略图；每页另有 SVG / PNG / PDF。

## 内容结构

1. 第 1–5 页：核心判断、官方框架锚点、AR / diffusion / 时间和统一模型内部机制。
2. 第 6–16 页：初始化、双状态、三图条件、GS 渲染、生成 / 融合与 4D 分支。
3. 第 17–27 页：开源组装、项目映射、Spatia / HY / MapAnything / GaME 接口、替代与外围部件、四个 adapter 和部署。
4. 第 28–35 页：训练适配、本地基线、阶段路线、MVP 验收、评测、消融与立项结论。
5. 第 36–40 页：调度伪代码、两张原图、完整一手来源索引。

## 使用与版本边界

系统闭环沿用用户认可的综合架构 v2，明确为官网已知信息与用户假设的综合实现设计。公开模型与工具的组合不是 Atlas 源码还原，也不是本目录新完成的跨项目 GPU 集成。WorldWarp 样例取自此前已有验收视频，本次没有重新运行推理。

两张源 SVG 以原始矢量数据和 PNG 回退嵌入 PPTX 附录。现代 Office 可使用 SVG；不支持 SVG 的阅读器仍可显示回退图片。正文图形可直接编辑。字体为 Noto Sans CJK SC；缺少该字体的设备可能自动替换中文字体，可优先阅读 PDF 以保持版式。

PDF / 预览由同一套版面绘制指令输出，不是 Microsoft Office 的实机渲染。已检查文字尺寸、形状边界、OOXML、重新打开 PPTX、页数、备注、来源链接及渲染预览；未声称在 PowerPoint 客户端逐页打开验收。

原目录中的所有 SVG、调研文件、WorldWarp 代码、环境与既有输出保持不变。这里仅新增演示文稿及其生成、检查文件。

## 重新生成

在 `/data4/sumai/GIL_ATLAS` 下运行：

```bash
uv run --with python-pptx --with pillow --with cairosvg --with pypdf python presentations/atlas_framework_reproduction_2026-09-06/build_deck.py
```

生成器使用本地 Noto CJK 字体、`ffmpeg` 抽取既有视频帧、`pdfunite` 合并预览。重新生成只更新本交付目录内的产物，不修改源图。
