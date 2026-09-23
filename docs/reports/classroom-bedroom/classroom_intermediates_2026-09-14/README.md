> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/README.md)。本目录未复制视频或大型资产。

已完成 classroom 重跑和几何中间结果归档，[核验结果](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/validation.json)为 `passed`，全部 9 个运行任务返回码均为 0。本次使用的 GPU 1、2、5、6 已释放。

正式记录包括 6,550 次 GS 优化、6,564 份模型快照、6,550 份训练渲染和逐次损失；原版 TTT3R 共 405 个推理帧；F/G/H 实际建模的 52 个 MapAnything 视图，以及对三个成片另做的全部 963 帧原始预测。另存 GaME 完整轨迹的 321 帧渲染。目录约 311 GiB，包含预检和源文件快照，详见 [storage.json](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/storage.json)。

| 版本 | 本次完整视频 | 中间结果入口 |
|---|---|---|
| A：WorldWarp 原版 | [10.7 秒视频](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/original/classroom_pan_left_4chunks_10.7s.mp4) | [TTT3R、逐次 GS、逐帧条件](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/traces/original) |
| F：滚动几何 + GS | [10.7 秒视频](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/rolling_gs/classroom_pan_left_4chunks_10.7s.mp4) | [逐次 GS 和条件](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/traces/rolling_gs)、[MapAnything 实际建模输入输出](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/rolling_gs/geometry)、[成片全部帧诊断](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/rolling_gs/mapanything_all_generated_frames) |
| G：原图约束 + GS | [10.7 秒视频](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/anchor_gs/classroom_pan_left_4chunks_10.7s.mp4) | [逐次 GS 和条件](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/traces/anchor_gs)、[MapAnything 实际建模输入输出](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/anchor_gs/geometry)、[成片全部帧诊断](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/anchor_gs/mapanything_all_generated_frames) |
| H：原图约束 + 点云 | [10.7 秒视频](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/anchor_points/classroom_pan_left_4chunks_10.7s.mp4) | [逐帧条件](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/traces/anchor_points)、[MapAnything 实际建模输入输出](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/anchor_points/geometry)、[成片全部帧诊断](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/anchor_points/mapanything_all_generated_frames) |
| 旧管线共用 GaME 场景 | [321 帧渲染数组和图片](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/game_shared_guidance) | [50 步预热与 500 步主拟合](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/traces/game/game)、[最终场景](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/game_shared_scene) |

重跑 WorldWarp 原版 A，以及 F/G/H 三个 WorldWarp + MapAnything 组合。相机、提示词、strength、上下文等保持对应版本的配置。另对旧三项目共用的固定 GaME 场景补跑一次 50 步预热和 500 步建模，不重复四次相同的建模过程。

每个最终视频仍为 4 段、321 帧、30 fps、10.7 秒，480×608，固定相机中心匀速向左转 20°。模型和记录参数见 [protocol.json](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/protocol.json)，命令、GPU、进程状态见 [jobs.json](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/jobs.json)。

视频生成种子为 32；GaME 独立拟合沿用旧脚本的种子 0。全部推理、逐帧诊断与 GaME 导出合计墙钟约 56.5 分钟，记录带来的计算和写盘开销包含在内，不能用于与未记录过程的旧实验直接比较推理速度。

| 内容 | 保存位置 | 完整性范围 |
|---|---|---|
| 原版视频 | `original/` | 全部四段与最终视频 |
| F：滚动几何 + GS | `rolling_gs/` | 全部四段与最终视频 |
| G：原图约束 + GS | `anchor_gs/` | 全部四段与最终视频 |
| H：原图约束 + 点云 | `anchor_points/` | 全部四段与最终视频 |
| 原生 GS 每次优化 | `traces/{original,rolling_gs,anchor_gs}/chunk_000…003/native_gs_fit_00/` | 每次 500 步，另存初始模型；共 12 次拟合 |
| GaME 每次优化 | `traces/game/game/game_gs_fit_00…01/` | 50 步预热、500 步主拟合，分别包含初始模型 |
| TTT3R 每帧预测 | `traces/original/chunk_000…004/ttt3r/` | 每次调用 81 帧；第 4 号为最后一段的补充诊断 |
| 实际输入扩散模型的逐帧画面与掩码 | `traces/各版本/chunk_000…003/diffusion_condition/` | 全部 81/85 帧，包含上下文前缀 |
| 掩码处理前的几何 RGB/alpha | `traces/各版本/chunk_000…003/raw_geometry_warp/` | 全部目标帧，保留原始浮点精度 |
| 生成帧，MP4 编码前 | `traces/各版本/chunk_000…003/generated_frames_before_codec/` | 每帧无损 PNG，包含上下文前缀 |
| 管线实际使用的 MapAnything 原始输出 | `{rolling_gs,anchor_gs,anchor_points}/geometry/chunk_000…003/mapanything_native/` | 保存每一个实际参与推理的视图 |
| 成片每帧的 MapAnything 补充诊断 | `{rolling_gs,anchor_gs,anchor_points}/mapanything_all_generated_frames/` | 每个视频全部 321 帧，按连续 5 帧的小窗口推理 |
| GaME 拟合后的完整相机轨迹渲染 | `game_shared_guidance/frames/` | 每帧 RGB、原始 alpha、裁剪后的 alpha、深度和相机，共 321 帧 |

每次 GS 拟合目录包含：

- `models/iteration_000000.pt` 是更新前初始模型；`iteration_000001.pt` 起是该次更新完成后的模型参数。全部浮点参数按原 dtype 保存，没有间隔抽样。
- `training_renders/iteration_000001.npz` 起保存每次实际用于计算损失的训练视角 RGB、alpha、深度及相机；`training_rgb/` 提供逐次 PNG 预览。第 n 次训练渲染和损失对应第 n−1 份模型，随后产生第 n 份模型；训练视角编号记录在损失表中。
- `losses.jsonl` 保存每次迭代的各项损失，核验脚本再导出 `losses.csv` 和 `losses.png`。
- `training_inputs.npz` 或 `training_keyframes.pt` 保存拟合输入，`final_optimizer_states.pt` 额外保留最终优化器状态。
- `manifest.json` 记录完整性和准确的迭代数量。

读取模型快照可用 `torch.load(path, map_location='cpu', weights_only=False)`。原生 GS 参数在返回字典的 `splats` 中；GaME 参数在 `tensors` 中。各段的 `frame_index.json` 列出局部帧号、全局帧号、上下文标记和是否保留进最终视频；TTT3R 目录也有单独的输入帧映射。

核验检查了全部帧号/迭代号、每个模型文件的 ZIP 目录结构，并加载每次拟合的初始、中间和最终模型检查参数。F/G 的最后一份迭代快照与各自最终模型逐张量相等；视频经 ffprobe 逐帧计数。14 次拟合均已导出完整损失 [示例曲线](../../../../WorldWarp_outputs/classroom_intermediates_2026-09-14/traces/anchor_gs/chunk_003/native_gs_fit_00/losses.png) 和 CSV。

“每次迭代的渲染”指优化器当次实际使用的训练视角；拟合后的目标相机轨迹则逐帧归档。没有为每个模型快照额外渲染一遍全部 321 个目标视角，模型参数和相机数据均保留，后续可按需重渲染。

MapAnything 每个视图包含 `prediction.pt`、`prediction_arrays.npz`、`processed_input.pt`，以及深度/置信度预览和字段元数据。PT 保留完整原始输出及 dtype；NPZ 中 BF16 转为能精确表示其数值的 FP32。输出在任何深度恢复、空间重采样之前保存。预览按各图有效值的 2%–98% 分位数着色；定量分析应读取数组。

原管线的几何来源选帧不变：F 后续每段取上一段均匀分布的 5 帧，G/H 额外加入原图。单独的 `mapanything_all_generated_frames` 是成片之后的补充推理，输入是交付 MP4 解码得到的全部帧，没有参与该视频的生成；多视图分组会影响估计，分组与全局帧号均有记录。不要将它与实际建模时的预测混用。

原版 TTT3R 的第 0 次调用输入是重复的原图。第 1–3 次调用对应已生成的前三段，额外第 4 次调用补齐最后一段。映射见 `traces/original/ttt3r_all_generated_frames_mapping.json`，按重叠处去重后覆盖成片时间网格的全部 321 帧。TTT3R 预测相机、GS 实际使用相机和目标相机分别保存，不视为同一个量。

这是重新执行和记录，不能精确找回历史运行的未保存状态。缓存历史实际提示词用于对照，GS 数值非确定性仍可能导致与旧视频不同。记录钩子只在本次进程中注入；未修改 WorldWarp/GaME 上游源文件。源文件快照与哈希见 `sources/`，实际注入后的函数见各 `traces/*/instrumented_sources/`。
