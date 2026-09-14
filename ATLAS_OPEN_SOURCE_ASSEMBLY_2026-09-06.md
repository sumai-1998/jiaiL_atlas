# Atlas 综合版：开源组装清单与接口说明

核查日期：2026-09-06。对应 [综合架构 v2](diagrams/atlas_architecture_synthesis_v2.svg)，新图为 [开源组装架构图](diagrams/atlas_open_source_assembly.svg)。

## 建议的组装主线

**HY-World 2.0 初始化 → 持久 GS → gsplat 渲染 → Spatia 生成 RGB → MapAnything 补几何 → GaME 增量更新 → 下一轮。**

Spatia 的参考检索和历史窗口承接“空间上下文”；SAM 3.1 提供实例／前景分割；NoPo4D、ClipGStream 承接动态场景重构；Spark 展示资产。整套系统仍需状态管理和接口适配，但不是从零实现这些模型。

与概念图有一个必要的工程拆分：图里的“统一 RGB-D 世界模型”在组装版中由**视频生成器 + 几何模型**共同承担。这里选 Spatia 的 RGB 生成路径与 MapAnything，而不把 Spatia 误写成原生深度生成模型。[Spatia 推理入口](https://github.com/ZhaoJingjing713/Spatia/blob/f75b10c9bb5f6b0cd779ec8c41ab33dd8382dba3/inference.py)、[MapAnything](https://github.com/facebookresearch/map-anything)

优先时间窗口为 **2025-09-06 至 2026-09-06**。下面区分论文、代码、权重与版本发布时间；不把仓库最近一次提交当成项目首发。gsplat、MuJoCo 是保留的成熟基础设施；GaME 论文较早，但本次可用代码是窗口内发布的。

## 1. 每个部件对应哪些项目

| 综合图部件 | 优先项目及 GitHub | 时间与可用资产 | 组装中的职责 |
|---|---|---|---|
| 文本／单图初始化世界 | [HY-World 2.0](https://github.com/Tencent-Hunyuan/HY-World-2.0) | 2026-04-16 开始发布；05-11 全景、05-18 世界生成推理与相关权重发布 | 用完整 world-generation 流程产生参考视图、相机、点云和 GS；不是只把全景丢进深度模型 |
| 多图／视频初始化 | 同仓库的 **WorldMirror 2.0** | 2026-04-16 代码／权重 | 从已有多视角观测预测深度、相机与 GS；不替代未见区域的生成 |
| 空间上下文／历史参考 | [Spatia](https://github.com/ZhaoJingjing713/Spatia) | 2025-12-17 论文；2026-03 公开权重；推理代码可用 | 复用参考视角检索、历史帧窗口、相机轨迹组织；补入首帧 GS 参考条件 |
| 持久世界状态 | [GaME](https://github.com/VladimirYugay/GaME) 的 GS 地图 + 自写 Session／MapStore | 2026-04-01 代码；论文 2025-06 | 保存 Gaussian 参数、关键帧和局部优化状态；自写跨模型会话、地图版本、动态层注册 |
| GS 条件渲染 | [gsplat](https://github.com/nerfstudio-project/gsplat) | 成熟库，持续维护；不是近一年首发 | 输入 GS、w2c、K，渲染 RGB、期望深度 ED、alpha，再生成控制有效性掩码 |
| 空间引导 AR 生成 | [Spatia](https://github.com/ZhaoJingjing713/Spatia) | 可下载 VACE／control 权重与 AR LoRA | Wan2.2-TI2V-5B + 控制分支 + AR LoRA；接受控制视频、历史视频与参考图，输出 RGB 片段 |
| RGB → 深度／点云／相机 | [MapAnything 1.1](https://github.com/facebookresearch/map-anything) | v1：2025-09-15；v1.1：2026-01-18；代码／权重／训练流程 | 结合输入相机条件估计几何；原 Spatia 已使用它，先保留原生搭配 |
| 几何后端备选 | [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) | 2025-11-14 代码／模型；12 月更新 1.1 与 streaming | 深度、相机、置信度；部分 Giant／Nested 权重支持 GS head，不能套用到所有型号 |
| 前景／实例掩码 | [SAM 3.1](https://github.com/facebookresearch/sam3) | 2026-03-27 版本；代码、需申请访问的权重 | 视频实例分割／跟踪，供静态过滤、GaME 分割输入与动态层关联使用；运动判定还需时序／几何信息 |
| 三维增量融合 | [GaME](https://github.com/VladimirYugay/GaME) | 2026-04 代码 | 已知位姿 RGB-D 与分割 → 增删 GS、屏蔽过时观测、局部共视优化；适合维护不断扩展／变化的地图 |
| 固定时间、变视角的动态重构 | [NoPo4D](https://github.com/bralani/NoPo4D) | 2026-05 论文；已提供推理入口、预训练 checkpoint | 同步多视角视频 → 动态 Gaussian、深度、相机、光流；通过其渲染器查询 C、t |
| 长序列动态重构备选 | [ClipGStream](https://github.com/liangjie1999/ClipGStream) | 2026-05／06 公开代码与示例数据 | 按片段拟合长动态场景；需要多视角视频、相机和片段点云，属于场景优化系统 |
| 时间推进的 AR 后端备选 | [LongLive 2.0](https://github.com/NVlabs/LongLive) | 2026-05-13 版本；代码覆盖 T2V／I2V、AR 训练、蒸馏与推理 | 替换时序生成后端；GS 控制、严格固定机位和动态几何回写仍需适配，不直接等同于完整 4D 世界模型 |
| GS 资产浏览 | [Spark 2.1](https://github.com/sparkjsdev/spark) | v2.1.0：2026-05-18 | 浏览器 GS 展示；不是深度估计器或增量融合器 |
| 少视图 GS 初始化备选 | [F4Splat](https://github.com/mlvlab/F4Splat) | 2026-03 论文／仓库；checkpoint、demo 可用 | 从少量图像生成 GS；是重建器，不是通用的外部 GS 增量更新器 |
| 物理仿真外围 | [MuJoCo](https://github.com/google-deepmind/mujoco) | 成熟引擎，持续维护 | 物理与机器人状态推进；需另备碰撞体、关节、质量等，GS／视频生成侧负责相应视觉输出 |

时间依据：[HY-World 发布记录](https://github.com/Tencent-Hunyuan/HY-World-2.0#-news)、[Spatia 论文](https://arxiv.org/abs/2512.15716)、[Spatia 权重](https://huggingface.co/Jinjing713/Spatia)、[MapAnything CHANGELOG](https://github.com/facebookresearch/map-anything/blob/main/CHANGELOG.md)、[GaME 首个代码提交](https://github.com/VladimirYugay/GaME/commit/1c971d65d29952789fa4a2ebb342580d41acbbff)、[SAM 3.1 发布说明](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md)、[Spark v2.1.0](https://github.com/sparkjsdev/spark/releases/tag/v2.1.0)。其余项目的日期类型见表，不能从会议年份倒推出代码发布时间。

## 2. 为什么这轮用 Spatia 作组装主干

与仅提供单次新视角的模型相比，Spatia 的当前代码已经有历史帧累积、相机轨迹切片、参考帧选择和跨片段调用，比较接近这张图需要的控制流。其实际入口使用 MapAnything 处理采样历史，再做点渲染；**当前公开实现不是直接维护并渲染 GaME 的持久 GS**。图中的 GS 路径是要接入的新组件。[Spatia README](https://github.com/ZhaoJingjing713/Spatia)、[推理源码](https://github.com/ZhaoJingjing713/Spatia/blob/f75b10c9bb5f6b0cd779ec8c41ab33dd8382dba3/inference.py)

适合抽取的调用点：

- `select_reference_frames`：按可见点重叠选历史视图。
- `pipe.call_latent_inference`：已有 `control_video`、`control_score`、`ref_images`、`input_video` 等条件。
- `run_mapanything`：已有图像／相机与几何前端衔接。
- 替换 `run_render`，并改造每轮建图调度，使其读取持久 GS，而不是每轮重新生成点云作为唯一状态。

保留首帧参考比较直接；**额外的首帧 GS 渲染参考**应在既有参考条件协议内实验，必要时微调，而不是给模型新增未经训练的任意输入通道。相同地，从点渲染替换成 GS 渲染，需要匹配控制图与 score 的语义及退化分布。

### 可替换的主干，不串联堆叠

| 方案 | 适合什么 | 本次定位 |
|---|---|---|
| [WorldWarp](https://github.com/HyoKong/WorldWarp)，2025-12 | GS warp 与生成修复最接近你的原始描述；本目录已有代码 | 保留为本地基线。复用采样／VAE 路径时要抽 adapter；现有片段入口不是外部持久 GS 渲染图的直接 API |
| [AlayaWorld](https://github.com/AlayaLab/AlayaWorld)，2026-07，v1.1 在 08 月 | 显式空间缓存、历史压缩编码、相机控制、AR／蒸馏及交互服务 | 作为较新的整套记忆—生成替代后端；保留其自身 DA3／ViGeo 空间接口，不能把内部缓存直接标成 GS |
| [SPMem](https://github.com/spmem/spmem)，2026-03 建立公开代码仓库 | 显式空间记忆、动静分离数据流程与流式控制 | 后续整套对照；已有权重和训练示例，不放进主线当通用检索插件 |
| [Mirage / LatentSpatialMemory](https://github.com/microsoft/LatentSpatialMemory)，2026-06 论文 | 在 latent 空间保存并查询三维记忆，减少 RGB 重编码 | 性能方向对照；它有意绕过 RGB 渲染路径，因此不强塞进本次 GS→RGB 的主线 |

AlayaWorld 当前仓库还提供 AR teacher、DMD student、训练阶段和不同推理路径；这比仅有演示页面更适合后续做完整替换实验。[AlayaWorld](https://github.com/AlayaLab/AlayaWorld)

## 3. 真正需要自写的四处衔接

### A. 初始化资产 → 统一会话

HY-World 的 world-generation 是多阶段流程；WorldMirror 则负责已有图像／视频重建。保留输出的参考图、深度与相机，统一世界坐标和尺度。将初始 GS 导入 GaME 所需的参数／优化器状态，或用这些 posed RGB-D 为 GaME 建立初始地图。**GaME 的现成数据集入口不等于已经提供外部 GS 导入器。**[HY API 文档](https://github.com/Tencent-Hunyuan/HY-World-2.0/blob/main/DOCUMENTATION.md)、[GaME](https://github.com/VladimirYugay/GaME)

### B. GS 渲染 → 视频生成条件

gsplat 输出的 RGB、ED、alpha 需要转换为 Spatia 训练时使用的控制视频和 score 格式。低覆盖度 mask、动态前景 mask 与模型置信度各有含义，不可直接互换。若渲染误差分布明显改变，要做控制分支／LoRA 的适配训练。[gsplat API](https://docs.gsplat.studio/main/apis/rasterization.html)

### C. 生成 RGB-D → 地图增量提交

原 Spatia 路径返回 RGB；MapAnything 根据新片段、历史参考和目标相机得到几何。转换后送入 GaME 的 posed RGB-D／分割数据入口，执行局部更新。SAM 3.1 给出对象实例，不自动证明物体正在运动；静态背景筛选还需运动／重投影判断。

GaME 主要解决场景布局变化及旧几何替换，不把它当成连续运动的 4DGS 模型。静态 GS 与动态层的提交策略需要分开。[GaME 方法](https://vladimiryugay.github.io/game/)、[SAM 3](https://github.com/facebookresearch/sam3)

### D. 时间生成 → 同步多视角动态重构

NoPo4D 的示例按 camera-major 组织同步多相机、多时刻图像。单路 Spatia／LongLive 视频不能不经处理就当作这些输入；需要在同一时刻生成／收集其他机位，保持对象与运动一致，再交给动态重构器。ClipGStream 还需预处理的相机和片段点云。

因此 4D 可以组装，但“同一 t 的多机位一致性调度”是明确要补的工程／训练模块；NoPo4D 的 4D 参数也不能直接塞进普通静态 gsplat 调用，先用它自带渲染器。[NoPo4D](https://github.com/bralani/NoPo4D)、[ClipGStream](https://github.com/liangjie1999/ClipGStream)

### 最小数据边界

| 数据 | 建议统一方式 |
|---|---|
| 相机 | 会话统一 OpenCV c2w + 像素 K；Spatia／渲染侧按入口转 w2c，归一化 K 按分辨率换算 |
| 深度 | 明确 z-depth、单位、无效 mask；gsplat 使用 ED 时保留 alpha，不把累计 D 当相同深度 |
| 几何 | GS 的位置、协方差／尺度旋转、SH、opacity 与点云在同一世界坐标；坐标改变时同步变换 |
| 上下文 | 参考图、首帧 GS 图、RGB-D 历史、相机和时间索引；控制首帧／窗口／检索帧数量 |
| 更新 | map_version、静／动态对象 ID、关键帧来源与置信度；可局部回滚 |

建议分进程／分环境服务化这些模块，先保留各自依赖版本。Spatia、GaME、HY-World 的 Python／Torch／CUDA 栈不同，不建议先强行合成一个环境。

## 4. 代码、权重与许可：简表

这里的“开源组装”按公开可取得的项目来组织；**不是所有权重、依赖都属于同一种开源许可，也不是商用许可清单**。

| 项目 | 本次核查到的许可边界 |
|---|---|
| HY-World 2.0 | Tencent HY-WORLD 2.0 Community License，自定义条款；底层全景模型等依赖还需分别处理。[License](https://github.com/Tencent-Hunyuan/HY-World-2.0/blob/main/License.txt) |
| Spatia | GitHub 代码 Apache-2.0；发布的控制／LoRA 权重标为 CC-BY-SA-4.0，不能用代码许可替代权重许可。[权重卡](https://huggingface.co/Jinjing713/Spatia) |
| MapAnything | 代码 Apache-2.0；默认权重 CC-BY-NC-4.0；另提供 `facebook/map-anything-apache` 权重。本次读到 Spatia 的几何脚本实际加载 `facebook/map-anything`，不是 Apache 权重支线。[模型说明](https://github.com/facebookresearch/map-anything#models)、[Spatia 几何脚本](https://github.com/ZhaoJingjing713/Spatia/blob/f75b10c9bb5f6b0cd779ec8c41ab33dd8382dba3/utils/map_anything_inference.py) |
| DA3 | 代码 Apache-2.0；Giant／Nested／Large 等权重含 CC-BY-NC；Base／Small／部分单目模型列 Apache-2.0。[型号表](https://github.com/ByteDance-Seed/Depth-Anything-3#-model-cards) |
| GaME | 顶层 MIT；LICENSE 明确列出的 Inria 派生 rasterization、simple-knn、flashsplat 等只允许非商用研究／评估，整体不能简单宣称 MIT 商用。[完整许可](https://github.com/VladimirYugay/GaME/blob/main/LICENSE) |
| SAM 3.1 | SAM 自定义许可；模型权重需要申请访问。[SAM 3 仓库](https://github.com/facebookresearch/sam3) |
| NoPo4D | 顶层 MIT；Depth Anything 3 等 backbone 权重、子模块另行适用其许可。[仓库](https://github.com/bralani/NoPo4D) |
| ClipGStream | 本次未找到明确的顶层标准许可；不能因仓库公开就推定授权范围。[仓库](https://github.com/liangjie1999/ClipGStream) |
| WorldWarp | 本次未找到明确的顶层许可证；代码可读与完整再分发／商用授权分开处理。[仓库](https://github.com/HyoKong/WorldWarp) |
| AlayaWorld | 当前 README 对代码与权重给出 LTX-2 Community 及研究／非商用说明；第三方 Gemma、DA3 另有条款。[许可段](https://github.com/AlayaLab/AlayaWorld#-license) |
| LongLive 2.0 | 仓库 Apache-2.0；采用的基础模型与具体下载权重另核对。[仓库](https://github.com/NVlabs/LongLive) |
| F4Splat | 顶层 MIT；具体 checkpoint 的模型卡和上游依赖需随版本保留。[仓库](https://github.com/mlvlab/F4Splat) |
| gsplat / Spark / MuJoCo | 分别 Apache-2.0 / MIT / Apache-2.0；GaME 内置 rasterizer 不会因为另接 gsplat 而自动更换许可。[gsplat](https://github.com/nerfstudio-project/gsplat)、[Spark](https://github.com/sparkjsdev/spark)、[MuJoCo](https://github.com/google-deepmind/mujoco) |

## 5. 核查记录与落地顺序

本次读取了官网仓库、模型卡、发布时间及关键源码；没有安装新模型、下载大权重或运行跨项目 GPU 推理。

关键源码快照：

- Spatia：`f75b10c9bb5f6b0cd779ec8c41ab33dd8382dba3`
- GaME：`1c971d65d29952789fa4a2ebb342580d41acbbff`
- HY-World 2.0：`df9988efb87bfc0f4947eb3889411cf957478b06`
- LongLive：`00c44e5418e8a5333a5cb3871c54948d5935b950`
- Spatia HF 权重仓库：`97dc39565d2dac4cd7bc4be697f45b5dae507549`

建议先跑 Spatia 原生点云闭环建立基线，再接 GaME 持久地图和 gsplat 控制渲染；之后接 HY 初始化，最后扩展同步多视角的 4D 分支。WorldWarp 作为现有本地对照保留，AlayaWorld 作为整套后端对照。

核心研究模型／版本基本落在近一年窗口内。最终交付是**组装设计图 + 已核对项目清单**，不是已经完成模型集成的运行结果。
