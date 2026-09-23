> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/README.md)。本目录未复制视频或大型资产。

目前完成的 8 个 classroom 版本已经放进同一个 [3×3 同步对比视频](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/classroom_all_8_versions_grid_10.7s.mp4)。8 格为生成结果，第 9 格 I 是原图按目标相机旋转投影的参考；黑色表示原图没有观测到的区域。视频共 321 帧、30 fps、10.7 秒，1440×2016；每个生成版本均由 4 段组成。

我的判断是：后续可以继续用 F/G 这条 WorldWarp + MapAnything 管线，H 作为时间稳定性候选，同时保留 C 作细节参考。去掉 GaME 后的版本在时间一致性指标上更好，但还没有全面超过旧版：后半段桌椅、地面和墙面文字更软。F 与 G 差距很小，这次不能证明“每段加入原图”明显更优。

| 格子 | 版本 | 原图区域 PSNR ↑ | 原图区域 SSIM ↑ | 时间 MAE ↓ | 关键帧观察与判断 |
|---|---|---:|---:|---:|---|
| A | WorldWarp 原版，strength 0.60，上下文 1 | 20.67 | 0.692 | 1.529 | 原图区域改变较多，局部纹理仍有，但保真较弱。 |
| B | MapAnything → GaME → WorldWarp 初版，0.60/1 | 23.94 | 0.765 | 1.636 | 原图保真比 A 好；时间误差、分段衔接偏弱，新区域有重影。 |
| C | 三项目，上下文改为 5，0.60/5 | 24.27 | 0.783 | 1.527 | 旧管线中较均衡；一些桌椅和地面细节比 F/G/H 清楚，新增墙面仍有不自然的大色块。 |
| D | 三项目，strength 0.50，上下文 1 | 25.20 | 0.804 | 1.506 | PSNR 最高，但新增左侧区域明显雾化，家具有半透明感，不适合只按分数选它。 |
| E | 三项目，strength 0.65，上下文 1 | 22.93 | 0.731 | 1.697 | 相比 B 改动更大，保真下降，时间误差最高，本场景不优先采用。 |
| F | 两项目，滚动几何 + WorldWarp 原生 GS，0.60/5 | 24.84 | 0.819 | 1.140 | 保真与时间一致性较好；后半段纹理偏平滑，可作为继续优化的基线。 |
| G | 两项目，每段加入原图 + 原生 GS，0.60/5 | 24.96 | 0.819 | 1.159 | 与 F 同档，原图保真略高；本次差距不足以证明原图约束有稳定收益。 |
| H | 两项目，每段加入原图 + 点云渲染，0.60/5 | 24.09 | 0.800 | 1.106 | 整体时间误差最低，最后一处衔接误差最低；仍有纹理变软和细节改变。 |

“三项目”使用最初单张图建立的固定 GaME 场景，后续不从生成视频更新几何。“两项目”每段使用 MapAnything 重估选中的历史帧，并用 WorldWarp 原生 GS 或点云投影渲染下一段；G/H 额外加入原图。GS 指 Gaussian Splatting，这里的 F/G 没有调用 GaME。

有三点值得据此保留或调整：

- **增加上下文是旧管线中有依据的改进。** C 相对 B，SSIM 从 0.765 提到 0.783，整体时间 MAE 下降约 6.7%，三处衔接 MAE 均降低。strength 降至 0.50 或升至 0.65 都有明显取舍。
- **新管线主要改善了时间一致性。** F/G/H 相对 C 的整体时间 MAE 分别降低约 25.3%/24.1%/27.6%，最后一次衔接误差降低约 22.7%/22.2%/28.8%。第一处衔接没有改善，因此不能说所有衔接都更好。时间误差降低也可能部分来自模糊和平滑。
- **下一步优先解决细节累积损失。** 现有结果更支持保留 0.60、上下文 5 和滚动几何，重点检查历史帧反复生成带来的纹理变软，再验证原图的权重及高置信区域保留方式。这里是后续建议，本次没有增加新的推理实验。

可直接看 [约 8 秒时新增左侧区域](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/new_area_240.jpg)，D 的雾化尤其明显；再看 [最后一帧桌椅和地面裁剪](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/furniture_320.jpg)，对照 C 与 F/G/H 的纹理差异。还有 [末帧全画面对比](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/frame_320.jpg) 和 [指标图](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/metrics_overview.png)。各版本的中文文字都不能可靠保持。

本次对照采用同一张裁剪缩放后的 480×608 输入、同一虚拟相机内参、同一条 0° 到 −20° 的匀速原地左转轨迹、相同实际分段提示词、seed 32、50 次扩散采样与 CFG 5。strength 和上下文长度按表中标明变化；上下文 5 的版本首段仍为 1。已经核对输入像素、轨迹、提示词与种子，并核对新旧统计中重复基线的指标完全一致。

PSNR/SSIM 比较的是仍在原图视野内的区域，以原图按目标旋转投影作为参考；均为第 1–320 帧的平均值，不含作为条件的第 0 帧。时间 MAE 是把上一帧按目标旋转对齐后计算的灰度绝对误差，灰度范围 0–255，越低表示残差越小；它不是单独的感知质量分数。左侧新区域没有真实图像作参考，因此无法据此评定生成内容是否真实正确。

当前只有一个场景、一个种子，而且是纯旋转。新旧管线同时改变了几何估计、渲染、可见性掩码和历史更新方式，收益不能全部归因于去掉 GaME。F/G 的原生 GS 训练也存在数值非确定性，微小分差需要更多种子验证。纯旋转的投影位置不依赖正深度，因此本实验也不足以证明 MapAnything 深度比原方案更准确。

完整数据在 [metrics.csv](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/metrics.csv)、[metrics.json](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/metrics.json)，核对结果在 [validation.json](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/validation.json)，视频规格在 [ffprobe.json](../../../../WorldWarp_outputs/classroom_all_comparison_2026-09-08/ffprobe.json)。统计汇总复用了已计算的最终视频指标，并校验了重复基线；同屏视频重新逐帧读取全部 8 个视频，确认帧数、尺寸和帧率一致。

各版本原视频：

- [A：WorldWarp 原版](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/classroom_pan_left_4chunks_10.7s.mp4)
- [B：三项目初版](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/video/classroom_pan_left_4chunks_10.7s.mp4)
- [C：三项目 context 5](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/context_5/classroom_pan_left_4chunks_10.7s.mp4)
- [D：三项目 strength 0.50](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/strength_050/classroom_pan_left_4chunks_10.7s.mp4)
- [E：三项目 strength 0.65](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/strength_065/classroom_pan_left_4chunks_10.7s.mp4)
- [F：两项目 rolling GS](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/rolling_gs/classroom_pan_left_4chunks_10.7s.mp4)
- [G：两项目 anchor GS](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_gs/classroom_pan_left_4chunks_10.7s.mp4)
- [H：两项目 anchor points](../../../../WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_points/classroom_pan_left_4chunks_10.7s.mp4)
