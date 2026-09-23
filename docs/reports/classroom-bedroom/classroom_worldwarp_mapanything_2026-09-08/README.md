> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/README.md)。本目录未复制视频或大型资产。

# Classroom：WorldWarp + MapAnything，去除 GaME

状态：全部完成。三组各 4 段、321 帧、30 fps、10.7 秒，已核验文件帧数与时长；GPU 0、1、2 已释放。

## 视频与结论

[五版本同屏比较（3×2，同步播放）](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/comparison/classroom_worldwarp_mapanything_grid_10.7s.mp4)

- [滚动几何 + 原生 3DGS](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/rolling_gs/classroom_pan_left_4chunks_10.7s.mp4)
- [原图约束 + 原生 3DGS](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_gs/classroom_pan_left_4chunks_10.7s.mp4)
- [原图约束 + 点云投影](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_points/classroom_pan_left_4chunks_10.7s.mp4)

| 方案 | 已知区域 PSNR ↑ | 已知区域 SSIM ↑ | 运动补偿后亮度误差 ↓ | 新区域时间误差 ↓ |
| --- | ---: | ---: | ---: | ---: |
| WorldWarp 原版（上下文 1） | 20.671 | 0.6919 | 1.5287 | 1.4463 |
| 之前含 GaME 的上下文 5 版本 | 24.268 | 0.7833 | 1.5268 | 1.2351 |
| 滚动几何 + 原生 3DGS | 24.839 | 0.8186 | 1.1403 | 1.0164 |
| 原图约束 + 原生 3DGS | 24.964 | 0.8190 | 1.1592 | 1.0366 |
| 原图约束 + 点云投影 | 24.087 | 0.8005 | 1.1058 | 1.0482 |

相对旧的含 GaME 上下文 5 版本，新三组整体时间误差下降约 24%～28%，最后一个接缝也改善，但第一个接缝没有改善。三组的 SSIM 都提高；点云版的 PSNR 略低于旧 GaME 版。

建议先比较原图约束 + 原生 3DGS 与原图约束 + 点云投影：前者已知区域指标最高，后者整体时间误差最低，抽查的中段桌椅边缘也更锐。两组 GS 的指标很接近，结合首段数值非确定性，不能认定原图约束带来了显著收益。三组在后半段均存在画面变软、文字变形和生成内容偏差；旧 GaME 版本在一些桌椅和地面细节上更清楚。低时间误差可能部分来自平滑，不能表述成整体画质提高 24%～28%。

三组推理耗时分别约 20.26、20.47、20.20 分钟；父 WorldWarp 进程峰值分配显存约 20.13 GiB，独立 MapAnything 子进程的显存另见每段报告。首段共享的 MapAnything 预计算约 26.5 秒，不计入这三个推理耗时。

完整指标与每段／接缝结果见 [comparison.json](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/comparison/comparison.json)，逐帧数据见 [per_frame.json](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/comparison/per_frame.json)，来源验证见 [config_checks.json](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/comparison/config_checks.json)。

## 实验组合

| 目录 | MapAnything 输入 | 几何条件生成 |
| --- | --- | --- |
| `rolling_gs/` | 首段用原图；后续段用上一段的 5 张真实生成帧 | WorldWarp 自带的 3DGS 拟合、渲染 |
| `anchor_gs/` | 上述历史帧加上原始图片；重复时间 0 的生成帧由原图替换 | 同一原生 3DGS；原图采样权重 2 |
| `anchor_points/` | 同样的原图与历史帧策略 | RGB-D 反投影为点云、双线性前向投影、逐视图深度缓冲、加权颜色融合；原图权重 2 |

三个新组合都不加载或调用 GaME，也不加载或推理 TTT3R 模型。两组 GS 使用的是 `WorldWarp/src/ttt3r/ttt3r.py` 中原有的 GS 建模和渲染代码；该文件名不代表使用了 TTT3R 模型。

每段重新用 MapAnything 估计几何，随后渲染下一段所需条件。历史窗口为上一段的局部帧 0、20、40、60、80，不使用为 VAE 长度适配而重复的前缀。原图约束版从第三段起共 6 个视图。首段的同一份 MapAnything 输出由三个实验共享；后续各自从自己生成的历史计算。

## 固定条件

- 图片：`/data4/sumai/GIL_ATLAS/Data/classroom.png`，与旧实验相同方式裁剪至 480×608。
- 4 段，合计 321 帧、30 fps、10.7 秒。相机固定位置，匀速向左转 20°。
- strength 0.60、50 次扩散采样、CFG 5、seed 32，复用旧基线各段实际使用的提示词。
- 首段上下文 1 帧，后续上下文 5 帧；内部 81、85、85、85 帧，额外重叠在编码前裁掉，交付的相机时间网格不变。
- GS 两组每段 500 次优化，每个来源最多采样 50,000 个初始高斯点。
- MapAnything：406×518 处理分辨率，BF16；提供虚拟相机内参与请求位姿，保留下游相机参数；不将纯旋转的零平移作为真实尺度观测。关闭边缘和置信度百分位筛选，保留模型有效区域掩码。
- 三组针对这条纯旋转轨迹，使用精确旋转投影后的来源可见范围，再结合渲染覆盖；WorldWarp 的 0.5 阈值、15×15 掩码腐蚀保持一致。

## 为何调整可见性检查

预检发现，原生 GS 在首视图的颜色重建 PSNR 约 38.7 dB，但原版深度一致性阈值只接受约 71.7% 的像素。对固定相机中心的纯旋转，已观测区域的可见性可由相机旋转和原图有效掩码直接确定，不需要依赖拟合后高斯的期望深度。更新后的两种渲染后端通过了首视图颜色和覆盖检查，详见 `geometry_smoke.json`。

`geometry_smoke.log` 保留首次发现覆盖不足的诊断；`geometry_smoke_v2.log` 是临时测试未指定 CUDA 12.8 导致的编译失败。正式推理使用 CUDA 12.8；`geometry_smoke_v3.log` 对应通过的验证。这些诊断不是额外生成的视频版本。

## 验证和结果位置

- `experiment_protocol.json`：事先记录的参数、假设和比较限制。
- `jobs.json`、各变体 `.log`：三个进程均以返回码 0 完成。
- 每组 `geometry/chunk_*/`：实际输入的历史帧、MapAnything RGB-D、几何渲染、有效掩码和参数记录。
- 每组 `geometry_bridge_calls.json`、`pipeline_report.json`：各段实际执行的几何条件注入。
- `sources/`：本次使用的脚本和核心源文件快照、SHA-256 清单。
- `comparison/`：3×2 同屏视频、细节截图、指标和输入／历史帧验证记录，已全部完成。
- `individual_video_verification.json`：三个独立视频的 ffprobe 检查。
- `first_chunk_numerical_variation.json`：独立 GS 运行在相同首段条件下产生的数值差异记录。

比较视频的上排为三个新组合，下排为 WorldWarp 原版、之前含 GaME 的上下文 5 帧版本、静态输入原图。所有视频同步播放 10.7 秒。

## 解释范围

这是一个教室、一条纯旋转轨迹、一个初始种子的实验。纯旋转时，正深度点的图像投影坐标与深度数值无关，因此该实验不能独立证明 MapAnything 深度预测更准确。生成帧提供的是模型产生的历史，不是真实拍摄的新观测。GS 的 CUDA 优化和栅格化可能有数值非确定性，相同初始种子不保证输出逐像素相同。

已知区域的 PSNR、SSIM 相对原图的精确旋转投影计算；新露出的区域没有真值。时间一致性用运动补偿后的亮度差衡量，低差值也可能来自模糊，需结合视频查看。

WorldWarp 原版使用 1 帧上下文，其余比较版本使用 5 帧。相对旧 GaME 管线，几何来源、历史更新、来源选择与可见性检查同时变化；不能把所有结果变化单独归因于去掉 GaME。
