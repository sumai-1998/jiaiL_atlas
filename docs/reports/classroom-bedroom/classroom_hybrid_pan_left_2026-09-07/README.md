> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/README.md)。本目录未复制视频或大型资产。

# 教室匀速左转：MapAnything → GaME → WorldWarp

已完成三项目实际串联，并与此前 WorldWarp 单独生成的成片比较。本次的主要收益是原图可见区域更保真；时间平滑性没有改善。

- [串联版成片](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/video/classroom_pan_left_4chunks_10.7s.mp4)
- [左右并排对比视频](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/comparison/classroom_side_by_side_10.7s.mp4)：左为 WorldWarp 原版，右为三项目串联版。
- [指标曲线](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/comparison/metric_curves.png)、[关键帧对比](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/comparison/comparison_contact_sheet.jpg)、[几何阶段预览](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/geometry_stages.png)。
- [完整指标 JSON](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/comparison/comparison.json)、[逐帧 CSV](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/comparison/per_frame.csv)、[结果摘要](../../../../WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/result_summary.json)。

输入为 `/data4/sumai/GIL_ATLAS/Data/classroom.png`。成片 480×608、30 fps、321 帧、总计 10.7 秒；四段各生成 81 帧，后三段各去掉一帧重叠后拼接。相机位置固定，输入条件为绕 Y 轴匀速左转 20°，每帧 -0.0625°，即 -1.875°/秒。沿用此前的四段总时长设置。

## 本次比较结果

指标针对两份最终拼接编码后的 MP4 计算。PSNR、SSIM 只评估原图中可见、在目标帧仍位于视野内的区域，按第 1–320 帧取平均。

| 指标 | WorldWarp 原版 | 三项目串联 | 解读 |
| --- | ---: | ---: | --- |
| 已知区域 RGB PSNR，越高越好 | 20.67 dB | 23.94 dB | 提高 3.26 dB |
| 已知区域亮度 SSIM，越高越好 | 0.692 | 0.765 | 原有结构更接近输入 |
| 已知区域 RGB 绝对误差，0–255，越低越好 | 18.16 | 11.34 | 减少约 37.6% |
| 运动补偿后帧间亮度绝对误差，0–255，越低越好 | 1.529 | 1.636 | 增加约 7.0%，平滑性未改善 |
| 特征运动相对目标轨迹的平均误差 | 0.102 px | 0.103 px | 接近，未见运动精度整体改善 |

三处接缝的运动补偿亮度误差分别为原版 **4.113 / 3.829 / 3.716**，串联版 **3.988 / 3.861 / 4.204**。第一处略好，第二处接近，第三处略差；两版在接缝处都比普通相邻帧有更高的变化。

已查看首、中、尾和三处接缝的关键帧。后半程原图可见区域的布局保留更好，与保真度指标一致。墙面文字、细小桌腿和新显露区域仍存在生成失真，不能据此声称文字精确、三维几何完全正确或整体质量全面更优。PSNR 也会受亮度、颜色和对齐影响，不单独代表锐度。

## 三个项目如何接起来

1. **MapAnything**：对与原版相同的 480×608 输入预测单视图深度，得到 `mapanything_dense/posed_rgbd.npz`。使用原版虚拟相机内参作为输入，并将预测深度映射回原始像素网格；保留原版 K 和单位初始位姿以固定比较条件。这个 K 不是对真实拍摄相机的标定，深度未用真实测量验证。
2. **GaME**：将这一份 RGB-D 用作静态场景输入，执行 500 次主优化（另有原生初始化步骤），获得约 14.4 万个高斯。加载真实 GaME 检查点，按同一条 321 帧轨迹渲染 RGB 和 alpha，保存于 `game_guidance/`。原始视角有效区域重建 PSNR 为 37.19 dB；相机投影适配误差约 0.0000038 像素。
3. **WorldWarp**：以 GaME 的 RGB/alpha 替换原流程内部的几何重投影结果，实际进入原有 VAE 编码、有效区域掩码处理和扩散采样。每段保留前一段的一帧作为上下文。四次实际注入的全局帧区间为 `[0,80]`、`[80,160]`、`[160,240]`、`[240,320]`，记录在 `video/pipeline_report.json` 及实验目录的 `geometry_bridge_calls.json`。

这里固定使用同一份 GaME 场景，没有将新生成的视频帧反馈给 GaME 扩展场景。因此这是静态几何条件串联实验，尚不属于持续更新世界的完整闭环。GaME 有效覆盖约从首帧 99.2% 下降到末帧 54.2%，其余区域由视频模型补全。

只凭此实验不能拆分 MapAnything、GaME 以及固定场景策略各自的贡献，也不能证明对其他图片、平移轨迹或随机种子同样有效。

## 公平性与检查

两次运行使用同一输入像素、相机轨迹及内参、seed 32、strength 0.6、50 步采样和 guidance scale 5.0，并逐段复用原版实际使用的提示词。已逐字比较四份提示词；配置文件仅输出目录不同。WorldWarp 核心文件、轨迹辅助文件和旋转生成入口与原版运行时源码快照相同。证据见 `configuration_comparison.json`。

纯旋转条件下，原图可见区域可以通过 `H = K_target · R_targetᵀ · R_source · inv(K_source)` 投影到目标帧，不依赖深度。比较脚本使用这一解析参考，并以 15×15 核腐蚀有效区域边界，避免黑边干扰；SSIM 使用亮度、11×11 高斯窗和 sigma 1.5。帧间误差先按相邻相机旋转对齐，再比较重叠区域。特征运动误差使用双向一致的 KLT 跟踪，只是诊断，不是实际相机位姿估计。

新比较代码的三个解析案例检查通过：左转投影方向、已知像素位移的运动补偿、拒绝使用纯旋转公式处理平移。实际 GaME 渲染另通过五个角度的解析投影检查，见 `game_guidance/projection_validation.json`。

两份新 MP4 均完整解码为 321 帧、10.7 秒。成片 H.264、480×608；并排视频 H.264、960×656，顶部附标签。验证记录见 `video/inspection/validation.json`、`video/inspection/ffprobe.json` 和 `comparison/ffprobe.json`。

MapAnything 约 27.5 秒、GaME 建模约 9.0 秒、轨迹渲染约 10.4 秒、WorldWarp 视频阶段约 17.5 分钟。视频阶段峰值 PyTorch 分配显存约 23.1 GiB，GPU 0 已释放。本次复用了提示词，不能把节省的时间或显存全部归因于几何方法。

## 复现与文件

原版保存在 `../classroom_pan_left_2026-09-07/`。以下入口会顺序调用三个本地环境并生成对比；必须指定新的绝对输出目录：

```bash
cd /data4/sumai/GIL_ATLAS
CUDA_VISIBLE_DEVICES=0 bash WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/reproduce.sh /data4/sumai/GIL_ATLAS/WorldWarp_outputs/新的对比目录
```

脚本语法检查通过；本次已逐阶段执行其中对应命令，未额外重复整套耗时生成。

- `mapanything_dense/`：本次实际采用的深度、点图及预测记录。
- `game/`：GaME 检查点、高斯 PLY 和训练配置。
- `game_guidance/`：321 帧实际渲染的 RGB、alpha、轨迹及投影检查。
- `video/`：最终视频、原始四段、提示词、输入轨迹和运行记录。
- `comparison/`：并排 MP4、逐帧指标、图表和参考有效区域。
- `sources/`、`source_manifest.json`：源码快照及 SHA-256。
- `logs/`：本次各阶段完整日志。

`mapanything/` 和 `debug_failed_video_01/` 是保留的调试产物，不参与最终成片。实际使用的是 `mapanything_dense/` 和 `video/`。
