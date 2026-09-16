# GIL_ATLAS 工作记录

工作目录：`/data4/sumai/GIL_ATLAS`。创建及最后更新：**2026-09-16**，时区 Asia/Shanghai。

本文件持续记录在本目录实际完成的部署、管线实验、评测和归档工作。首次整理根据已有配置、运行状态、指标 JSON 和报告回填历史；实验日期与本文件整理日期分开记录。操作参数以 [管线文档](docs/PIPELINES.md)和 [registry.json](pipelines/registry.json)为准。

本文是工作台账和结果索引。`runs/`、`WorldWarp_outputs/`、`Reports/` 中的链接指向服务器本地成果，这些大文件不随 Git 上传；只下载本文或代码仓库不能离线播放全部实验视频。需要离线阅读图文报告时，下载对应的完整 `Reports/` 子目录或 ZIP。

## 当前进度

| 工作 | 截至 2026-09-16 的状态 |
|---|---|
| WorldWarp 本地 DL3DV 基线 | **5 个不同场景已完成**，分为 3 场景和 2 场景两批；生成、六项指标、报告及文件核验完成 |
| 论文官方完整复现 | 未完成；现有结果是按公开方法固定的本地小样本协议 |
| 5 场景统一汇总 | 当前保留两批汇总，尚未生成独立的五场景合并报告 / 合并 FID |
| classroom 组合实验 | A–H 八个版本已完成历史推理、同步同屏对比和局部保真 / 时间一致性分析 |
| bedroom 左平移 | 已完成 WorldWarp 原版匀速左平移视频 |
| 中间结果补录 | 2026-09-14 重跑 A/F/G/H，并单独补录 GaME 静态模型和渲染过程 |
| 系统讲解与离线报告 | 已完成自包含 Markdown / HTML / 图片 / 视频报告 |
| 仓库和执行入口 | 三项目源码平铺整合；统一管线入口、参数注册表和 AI 执行规范已建立 |
| 同机多用户复用 | 共享启动器、独立缓存和说明已完成；尚未以其他 Linux 账号验证完整 GPU 推理 |
| 组合管线在同一批 DL3DV 上评测 | 尚未完成，不能把 classroom 结果直接当作五场景上的改进收益 |

## 2026-09-16：WorldWarp 五场景本地基线

### 数据来源与场景选择

前期在服务器找到的 38 个场景属于 DL3DV 官方评测基准中的场景，但没有证据将它们等同于 WorldWarp 论文的精确测试划分。清单及成员核对保存在 [数据盘点目录](Reports/dataset_inventory_2026-09-15/)和 [38 场景清单](Reports/dataset_inventory_2026-09-15/existing_dl3dv_38_scenes.json)。本次实际使用其中现有 pixelSplat Torch 格式数据，读取其他用户已有分片，没有重新下载完整 DL3DV。

| 批次 | 场景简称 | 场景 ID 前 12 位 / 运行子目录 | 已完成 |
|---|---|---|---|
| 第一批，3 场景 | 建筑与雕像 | `032dee9fb0a8` | 视频、图像指标、位姿指标 |
| 第一批，3 场景 | 温室花展 | `0569e83fdc24` | 同上 |
| 第一批，3 场景 | 餐厅 | `06da79666629` | 同上 |
| 第二批，2 场景 | 室外街边商铺 | `3bb894d1933f` | 同上 |
| 第二批，2 场景 | 室内汽车展厅 | `adf35184a12d` | 同上 |

完整场景 ID 保存在两批 `metrics_summary.json`。第一批按本地清单的场景 ID 排序取前三个；第二批在生成前查看剩余场景的首帧和相机元数据，固定选择一室外、一室内场景，不依据生成质量挑选。第二批的“典型场景”是本地选择，不是论文指定的经典场景列表。

第二批选场依据见 [selected_manifest.json](runs/dl3dv_worldwarp_eval2_20260916_142500/selected_manifest.json)和 [选场记录](Reports/dl3dv_scene_selection_20260916_1420/)。其 `metrics_summary.json` 的 `parameters.selection` 仍保留通用的排序选择文案；实际选择方式以该 manifest 和批次报告为准。

### 实际生成与评测协议

协议名为 `local-dl3dv-paper-based-pilot-v1`，运行 ID 为 `ww-dl3dv-benchmark`；两批均记录 `official_reproduction: false`。执行入口是 [scripts/pipelines.py](scripts/pipelines.py) 的 `benchmark plan / doctor / run`，实现见 [worldwarp_benchmark.py](scripts/worldwarp_benchmark.py)及 [指标脚本](scripts/worldwarp_benchmark_metrics.py)。

| 项目 | 本次基线实际设置 |
|---|---|
| 生成方法 | TTT3R → WorldWarp 原生 Gaussian Splatting（GS）→ WorldWarp 异步扩散；未接入 MapAnything 或 GaME |
| 图像与相机 | 按时间戳取前 225 帧；现有 480×270 图片放大、中心裁剪到 720×480，同时变换内参 |
| 控制轨迹 | TTT3R 从真实参考序列提取相机与内参；评分真值使用 DL3DV 标定相机 |
| 真实图像输入 | 生成图像历史只从第一张真实图开始，后续使用生成历史；参考序列深度仅保存诊断，不送入 GS 或扩散 |
| 分段 | 5 段 × 49 帧；首段上下文 1，后续重叠 5 帧；去重后 `49 + 4×44 = 225` 帧 |
| 成片 | 720×480，225 帧，30 fps，播放时长 7.5 秒；原始采集帧率未确认 |
| 生成参数 | strength 0.8，50 步采样，CFG 5，seed 32；GS 500 步，位置学习率 1.6e-3 |
| 历史几何 | TTT3R 接收上一段 49 帧；GS 使用末尾 5 个连续视图，首段仅 1 个；区别于 F/G/H 的均匀关键帧 |
| 文本 | Qwen 根据起始图和生成历史自动生成 caption |
| 图像评分 | 编码前无损 PNG，与对应真实帧全图比较，不进行图像配准或剔除失败案例 |
| 评测端点 | 第 50 / 200 帧，输入图计为第 1 帧，对应零基索引 49 / 199 |

这套 **225 帧 / 7.5 秒评测协议**与 classroom 的 **321 帧 / 10.7 秒标准视频管线**分开记录，不能交换默认配置。生成器虽只用一张真实图作为图像起点，评测仍利用真实参考序列估计控制相机，不能表述为完全没有轨迹信息的单图实验。

本地适配器把上一段解码后的 uint8 RGB 直接用于下一段图像历史，避免 MP4 往返；caption 仍读取分段视频。这与上游演示入口存在数据传递差异，已有报告明确披露。

### 六项指标与已保存结果

下表为各批次端点指标。PSNR、SSIM、LPIPS、R_dist、t_dist 对场景等权平均；FID 使用该批次端点图像集合计算，**不是单场景 FID 的平均**。数值按原始 JSON 四舍五入。

| 批次 | 帧 | PSNR ↑ dB | SSIM ↑ | LPIPS ↓ | R_dist ↓ rad | t_dist ↓ | FID ↓，小样本诊断 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 第一批，3 场景 | 50 | 10.980 | 0.3163 | 0.6087 | 0.7786 | 0.8038 | 193.039 |
| 第一批，3 场景 | 200 | 11.577 | 0.4392 | 0.8150 | 0.7221 | 0.7371 | 418.306 |
| 第二批，2 场景 | 50 | 11.219 | 0.3249 | 0.6282 | 0.5068 | 0.6498 | 279.076 |
| 第二批，2 场景 | 200 | 11.839 | 0.4117 | 0.7435 | 1.4183 | 0.5118 | 590.039 |

原始数据：[第一批指标](runs/dl3dv_worldwarp_eval3_20260916_112915/metrics_summary.json)、[第二批指标](runs/dl3dv_worldwarp_eval2_20260916_142500/metrics_summary.json)。这是两个不同场景集合，不能把两批分数差异解释为方法改进或退步。

指标口径：

- PSNR 使用 RGB [0,1]；SSIM 使用 11×11 高斯窗、sigma 1.5、总体协方差和 RGB 通道平均；LPIPS 使用 AlexNet v0.1。
- FID 使用 pytorch-fid 标准 Inception 2048 维特征。端点只有 3 张或 2 张图，统计不稳定；所有新生成帧的 FID 同样受帧间相关性影响，只作诊断。未来合并五场景 FID 必须合并特征重新计算，不能平均两批 FID。
- R_dist 使用独立 DUSt3R 从生成视频恢复位姿后，与数据集相机比较旋转测地距离，单位为弧度。
- t_dist 为相对首帧、各自按轨迹最大半径归一化后的平移 L2 误差，**不是米，也不是时间误差**；没有额外对真值做 Procrustes 拟合。
- DUSt3R 在两个端点分别重建，使用索引 0、9、19……49 / 199，完整双向配对，MST 初始化，全局优化 300 步、cosine、lr 0.01。另重建真实视频作为估计器诊断，不能把其误差直接从生成结果中扣除。

### 耗时与验收

以下来自 `status.json` 阶段时间及第二批 [timing_summary.json](runs/dl3dv_worldwarp_eval2_20260916_142500/timing_summary.json)，均为正式管线运行耗时，不含前期安装、选场、代码准备和后续打包。

| 批次 | 本地起止时间，2026-09-16 | 视频生成，含模型加载 | 图像 + 位姿指标阶段 | 报告阶段，含最终 FID | 管线总耗时 |
|---|---|---:|---:|---:|---:|
| 第一批 3 场景 | 11:29:47—12:50:17 | 61 分 30 秒 | 13 分 25 秒 | 约 15 秒 | **80 分 30 秒** |
| 第二批 2 场景 | 14:21:51—15:12:31 | 38 分 00 秒 | 9 分 02 秒 | 约 5 秒 | **50 分 41 秒** |

总耗时还包括数据准备、参考相机估计和完成检查。运行目录名中的时间只是名称，精确起止时间以 `status.json` 为准。

两批运行状态均为 `complete`，核验状态均为 `passed`。第一批核对 1,350 张真实 / 生成 PNG 和 675 行逐帧图像指标；第二批核对 900 张 PNG 和 450 行指标。视频帧数、尺寸、帧率、汇总均值及报告媒体链接均已检查，证据见 [第一批核验](runs/dl3dv_worldwarp_eval3_20260916_112915/verification.json)、[第二批核验](runs/dl3dv_worldwarp_eval2_20260916_142500/verification.json)。

### 结果解读与文件位置

已保存的抽帧观察显示：建筑场景出现雕像 / 基座变形和视角漂移；温室、餐厅后期明显模糊并丢失布局；商铺后期窗墙和遮阳篷结构改变；汽车展厅后期出现真实图中没有的网格纹理，车辆和展牌细节丢失。五个场景的第 200 帧 LPIPS 都比第 50 帧差，部分 PSNR / SSIM 上升不能据此判断画质改善。

退化画面也可能使 DUSt3R 位姿估计失真；例如汽车展厅的较大旋转误差需结合画面阅读，不能当成准确恢复出的真实相机运动。当前结果适合作为固定场景和协议下的本地对照，不足以推出整个数据集上的性能结论或论文排名。

| 批次 | 完整运行 / 原始中间产物 | 可离线阅读的报告 | 打包下载 |
|---|---|---|---|
| 3 场景 | [runs/dl3dv_worldwarp_eval3_20260916_112915](runs/dl3dv_worldwarp_eval3_20260916_112915/) | [报告 README](Reports/dl3dv_worldwarp_eval3_2026-09-16_112915/README.md) | [报告 ZIP](Reports/dl3dv_worldwarp_eval3_2026-09-16_112915.zip) |
| 2 场景 | [runs/dl3dv_worldwarp_eval2_20260916_142500](runs/dl3dv_worldwarp_eval2_20260916_142500/) | [报告 README](Reports/dl3dv_worldwarp_eval2_2026-09-16_142500/README.md) | [报告 ZIP](Reports/dl3dv_worldwarp_eval2_2026-09-16_142500.zip) |

完整运行保存真实 / 生成逐帧 PNG、MP4、逐帧 CSV、图像与位姿 JSON、数据集 / TTT3R / DUSt3R 相机、FID 特征、每段最终 GS PLY、caption、调度图、日志、参数、环境和代码快照。参考真实视频深度文件明确标注 `DIAGNOSTIC_ONLY`。这两批没有保存逐次 GS 更新模型或逐去噪 latent，不能与下述全量中间结果补录混淆。

离线报告包含文档引用的图片和视频，但不包含完整运行中的所有 PNG、深度、GS 原始文件。对比视频是每行一个场景、左侧真实 / 右侧生成的空间拼接。

## 2026-09-07—09-08：三项目组合与 classroom 对照

### 实际尝试过的管线

输入为 [Data/classroom.png](Data/classroom.png)。这些历史成片统一为 480×608、30 fps、321 帧，**4 段合计 10.7 秒**；固定相机中心匀速左转，总角度 −20°，50 步采样，CFG 5，seed 32。表中上下文 5 指后续段，首段仍只从输入图开始。

| 标签 | 当前管线 ID | 实际数据流与主要变量 | strength / 上下文 | 历史结果 |
|---|---|---|---|---|
| A | `ww-rotate` | TTT3R → WorldWarp 原生 GS → WorldWarp | 0.60 / 1 | [原版左转](WorldWarp_outputs/classroom_pan_left_2026-09-07/) |
| B | `map-game-ww` | MapAnything → GaME 固定静态场景 → 渲染 → WorldWarp | 0.60 / 1 | [三项目初版](WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/video/) |
| C | `map-game-ww-ctx5` | B 的视频上下文增加至 5 帧 | 0.60 / 5 | [context_5](WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/context_5/) |
| D | `map-game-ww-s050` | B 降低 strength，上下文仍为 1 | 0.50 / 1 | [strength_050](WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/strength_050/) |
| E | `map-game-ww-s065` | B 提高 strength，上下文仍为 1 | 0.65 / 1 | [strength_065](WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/strength_065/) |
| F | `map-ww-gs` | MapAnything 滚动历史几何 → 每段重拟合原生 GS → WorldWarp | 0.60 / 5 | [rolling_gs](WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/rolling_gs/) |
| G | `map-ww-anchor-gs` | F 加入原始图像锚定，原图权重 2 | 0.60 / 5 | [anchor_gs](WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_gs/) |
| H | `map-ww-anchor-points` | 原图 + 历史 → MapAnything → 点云投影 → WorldWarp；不优化 GS | 0.60 / 5 | [anchor_points](WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_points/) |

GaME 在 B–E 中仅拟合一次固定静态场景，使用全图静态 mask；没有运行 SAM / 动态实例更新，也没有持续把生成历史融合进 GaME 地图。因此这里验证的是静态几何渲染条件，不是动态环境地图更新能力。

F/G 每段重新估计几何并重新拟合 WorldWarp 原生 GS，没有跨段持久的 GaME 全局地图。它们用 5 个均匀历史关键帧估几何，用末尾 5 个连续帧作为视频上下文，两组选帧不同；G/H 额外保留原图。生成历史不是新增真实观测。G 是未指定具体组合时的默认 MapAnything + WorldWarp 入口，不代表已证明质量最好。

### 同屏对照和已有结论

已完成 [A–H 八版本 3×3 同步对比视频](WorldWarp_outputs/classroom_all_comparison_2026-09-08/classroom_all_8_versions_grid_10.7s.mp4)，第九格为原图旋转投影参考；是横向、纵向排布，同步播放 10.7 秒。分析和原始统计见 [对照报告](WorldWarp_outputs/classroom_all_comparison_2026-09-08/README.md)、[metrics.json](WorldWarp_outputs/classroom_all_comparison_2026-09-08/metrics.json)。

| 版本 | 原图可见区域 PSNR ↑ | SSIM ↑ | 旋转对齐后时间 MAE ↓ |
|---|---:|---:|---:|
| A | 20.67 | 0.692 | 1.529 |
| B | 23.94 | 0.765 | 1.636 |
| C | 24.27 | 0.783 | 1.527 |
| D | 25.20 | 0.804 | 1.506 |
| E | 22.93 | 0.731 | 1.697 |
| F | 24.84 | 0.819 | 1.140 |
| G | 24.96 | 0.819 | 1.159 |
| H | 24.09 | 0.800 | 1.106 |

这些是 **2026-09-08 历史视频**的统计，不是 09-14 重跑或新统一入口的一轮新测量。PSNR / SSIM 使用原图按目标旋转投影后仍可见的区域作参考；时间 MAE 是相邻帧按目标旋转对齐后的灰度绝对误差，灰度范围 0–255。它衡量时间一致性残差，区别于 DL3DV 的平移 `t_dist`。新露出的区域没有真实图像参考，不能用这些分数证明内容正确。

当时的判断是：C 相对 B 的上下文衔接有所改善；F/G/H 时间误差较低，但后半段桌椅、地面、文字纹理偏软；H 时间 MAE 最低，D 虽 PSNR 最高却有明显雾化和半透明家具。F/G 差异很小，尚不能证明原图锚定稳定更优。模糊也能降低时间残差，不能只按单一指标选管线。

这组实验只有单场景、单种子，且多个组件同时变化，不能把收益全部归因于移除 GaME；纯旋转缺少平移视差，也不足以证明深度估计准确度提升。

### 左平移和静态建模分支

- **bedroom 左平移**：输入 [Data/bedroom.png](Data/bedroom.png)，`ww-translate`，TTT3R → 原生 GS → WorldWarp；保持方向、沿 X 轴匀速左移。结果见 [bedroom 实验](WorldWarp_outputs/bedroom_truck_left_2026-09-07/README.md)和 [成片](WorldWarp_outputs/bedroom_truck_left_2026-09-07/bedroom_truck_left_4chunks_10.7s.mp4)。左平移与 classroom 左旋转是不同运动；当前 F/G/H 和 GaME 视频统一入口仅支持纯旋转。
- **只做几何**：`mapanything` 将单图或同一场景多视图转换为 RGB-D / 点图 / 点云；`mapanything-game` 再拟合 GaME 静态 GS。几何安装与试运行证据见 [geometry_outputs/install_smoke_2026-09-07](geometry_outputs/install_smoke_2026-09-07/)。这些分支本身不生成扩散视频。

## 2026-09-14：补录中间结果与系统报告

针对以前未完整保存的 GS 演变过程、TTT3R 几何条件、MapAnything 原生空间数组，重新运行 A/F/G/H 并补录。归档位于 [classroom_intermediates_2026-09-14](WorldWarp_outputs/classroom_intermediates_2026-09-14/)，含 [说明](WorldWarp_outputs/classroom_intermediates_2026-09-14/README.md)、[结果汇总](WorldWarp_outputs/classroom_intermediates_2026-09-14/result_summary.json)和 [核验](WorldWarp_outputs/classroom_intermediates_2026-09-14/validation.json)。

| 保存内容 | 已归档范围 |
|---|---|
| A/F/G/H 视频 | 每个版本 321 帧、30 fps、10.7 秒，核验通过 |
| GS 拟合过程 | 合计 6,550 次更新、6,564 个模型快照，及对应训练渲染 / 损失记录 |
| TTT3R | 405 个实际推理帧的深度 / 位姿等几何记录 |
| MapAnything 实际生成用几何 | 52 个视图的原生空间结果及送入后续阶段的变换结果 |
| MapAnything 成片诊断 | F/G/H 共 963 帧，即 3×321；视频生成后单独推理 |
| GaME 补录 | 共享静态场景拟合记录，以及 321 帧独立渲染 |

GS 第 n 次训练渲染使用更新前模型 n−1，保存的模型 n 是更新后状态，查看模型与画面时要错开对应。H 不进行 GS 拟合；没有保存逐去噪步 latent 或解码图。963 帧 `posthoc` 诊断不参与已完成视频的生成。

GaME 补录只重建旧共用静态场景并保存拟合 / 渲染过程，**没有再用该重建场景生成 B/C/D/E 视频**；旧成片与补录结果不能合称同一次端到端运行。

已制作 [自包含系统讲解报告](Reports/classroom_system_walkthrough_2026-09-14/README.md)，解释输入图如何依次形成几何、GS / 点云、相机渲染、扩散条件和最终视频。整个 [报告目录](Reports/classroom_system_walkthrough_2026-09-14/)包含 Markdown、离线 HTML、86 张 PNG、17 个 MP4。阅读与分享应下载该完整目录；全量中间归档是另一个更大的目录。详细归档口径见 [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md)。

## 工程整理与共享环境

截至本次登记，WorldWarp、MapAnything、GaME 已作为普通源码目录整合，保留许可证与 [上游来源记录](docs/upstream_sources.json)。统一入口负责自然语言管线映射后的计划、环境检查、执行、状态、日志和成片核验；历史固定路径脚本保留用于追溯。新路由可用不等于每个参数组合都已完成新的 GPU 质量实验。

三套环境位于 `conda_envs/worldwarp`、`conda_envs/mapanything`、`conda_envs/game`。2026-09-16 完成同机复用支持：新增 [shared_pipeline.sh](scripts/shared_pipeline.sh)，让其他账号调用现有解释器，并将运行 / 编译缓存放在各自目录；`doctor` 增加读取和执行权限检查。共享方案与使用方式见 [docs/SHARED_USE.md](docs/SHARED_USE.md)，部署依赖见 [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)。

当次已通过管线 / 评测 CPU 测试、三环境主要模块导入和小型 CPU 运算，并修正一个公开 TTT3R 权重的读取权限。未以其他账号执行完整 CUDA 推理；共享环境的可读性不等于 GPU 资源或他人数据目录自动可用。个人运行输出、缓存分别写入各自有权限的目录，共享环境由维护者更新。

## 后续更新约定

本节是持续记录规则，不自动启动新的实验。后续在本目录完成实质性的推理、评测、管线变更或归档任务时，更新顶部日期、当前进度，并按日期追加条目；同一任务补充结果时更新其条目，同时保留原运行路径和历史结论。

每次至少记录：

1. 日期、任务目的和状态：计划 / 运行中 / 已完成 / 失败 / 受阻。
2. 输入数据、管线 ID、关键参数、代码或配置变化；是否保存全量中间结果。
3. 唯一运行目录、实际成片 / 模型 / 报告 / 指标路径。
4. 耗时及统计范围、验证方式、实际结果与限制。
5. 未完成事项和下一步建议，明确区别于已经执行的工作。

当前待办候选：五场景统一汇总；让组合管线支持与基线一致的轨迹、帧数和评测协议后做对照；按新数据和种子复查细节衰减、原图约束收益；其他账号的实际运行验证。这些事项尚未执行，不预先填写结果。

首次整理仅建立工作记录并添加文档入口，核对已有参数、数值和本地链接；没有重新运行模型。随后按用户要求将文件命名为 `sumai-work-log.md`，并同步 README / AGENTS 引用。

## 2026-09-16：代码同步登记

同步目标为更名后的 GitHub 仓库 `sumai-1998/jiaiL_atlas`，分支 `main`。本次提交范围包括 DL3DV 基线生成与指标脚本、依赖约束、管线注册和路由、多用户共享启动器与缓存 / 权限检查、对应测试和使用文档，以及本工作记录。实验视频、原始中间结果、模型权重和 Conda 环境继续保存在本地忽略目录。

提交前已拉取远程引用并核对分支；11 项管线 CPU 测试和 6 项基线评测 CPU 测试全部通过，共享启动器 Bash 语法及 `git diff --check` 通过。本次同步未重新执行 GPU 推理。提交版本号和远程同步状态以 Git 提交记录及推送结果为准。
