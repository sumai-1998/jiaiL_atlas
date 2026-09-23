> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/README.md)。本目录未复制视频或大型资产。

# WorldWarp / dataset-camera diagnostic：DL3DV 本地 1 场景基准

> 视觉验收：未通过。运行和评分已完成，但后期主体与目标视角明显不符，不能标记为成功复现；见本运行 quality_acceptance.json。

**这是标定相机诊断，不是论文 TTT3R 控制相机协议。** 实际请求 K/旋转来自数据集；平移只按数据集与参考 TTT3R 轨迹拟合一个正标量以统一深度单位。未使用参考深度生成。实际相机为 conditioning_cameras.npz；reference_ttt3r_cameras.npz 仍保留预测轨迹作对照。


这是一次按论文已公开方法建立的本地小样本基准，**不是论文官方结果复现**。本次 1 个场景：预先固定建筑与雕像 032dee9fb0a8；复用之前前225帧，检查上游内参处理修正，不按新生成分数筛选。

[所有场景同时对比视频](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/all_scenes_comparison.mp4)：每行一个场景，左侧是真实帧，右侧是生成帧。225 帧、30 fps、播放时长 7.5 秒；30 fps 是播放速度，不代表原始采集时间。

## 第 50 / 200 帧指标

第一张输入图计为第 1 帧，因此第 50 / 200 帧分别对应数组索引 49 / 199。以下各场景等权平均，未使用图像配准、挑帧或去除失败案例。

| 帧 | PSNR↑ (dB) | SSIM↑ | LPIPS↓ | R_dist↓ (rad) | t_dist↓ | FID↓（仅 1 张，诊断） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 11.175 | 0.3618 | 0.5661 | 0.1935 | 0.1164 | N/A（单张） |
| 200 | 10.972 | 0.4197 | 0.7512 | 0.1934 | 0.6119 | N/A（单张） |

**FID 限制：**每个端点只有 1 张图，协方差秩至多为 0，数值不稳定，不能用于对照论文 FID 排名。全部新生成帧合并的 FID 也只是诊断，帧之间高度相关。
全部 224 张新生成帧的诊断 FID：113.775。

![逐帧指标](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/metric_curves.png)

## 本地轨迹的运动幅度

下表均按第 50 / 200 帧的顺序列出。GT 角度是端点相对首帧的净旋转，不是累计转角，也不包含平移。不同场景的同一帧号不代表相同运动难度。论文未公开精确采样，因此不能把本地第 50 帧默认为与论文有相同的视角跨度。

| 场景 | GT 净旋转（°） | TTT3R 参考相机相对 GT 的旋转误差（°） | 参考估计 / 数据集标定 f_x |
|---|---:|---:|---:|
| 032dee9fb0a8 | 23.65 / 85.78 | 0.56 / 8.62 | 1.270 / 1.270 |

## 各场景

### 032dee9fb0a8

场景 ID：`032dee9fb0a8bc1b90871dc5fe950080d0bcd3caf166447f44e60ca50ac04ec7`

[并排视频](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/032dee9fb0a8/comparison.mp4) · [生成视频](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/032dee9fb0a8/generated.mp4) · [真实视频](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/032dee9fb0a8/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/032dee9fb0a8/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 11.175 | 0.3618 | 0.5661 | 0.1935 | 0.1164 | 0.0068 / 0.0460 |
| 200 | 10.972 | 0.4197 | 0.7512 | 0.1934 | 0.6119 | 0.0625 / 0.0223 |

![第 50 帧](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/032dee9fb0a8/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/032dee9fb0a8/comparison_frame_200.jpg)

## 实际流程与参数

1. 从现有 pixelSplat 格式 DL3DV 分片读取相机和图片，按时间戳取前 225 帧。原图 480×270，经 Lanczos4 放大并中心裁剪到 720×480；内参应用同一像素变换，外参由 OpenCV w2c 转为 c2w，统一到第一帧坐标系。
2. 用参考视频 TTT3R 位姿估计平移单位；实际采用数据集标定内参和旋转，数据集平移乘正的最小二乘尺度。仅标定相机与参考估计的平移参与尺度拟合，参考深度不用于生成。
3. 生成器的实际图像输入只有第一张真实图。后续 TTT3R、GS 与 Qwen caption 只接收已生成的历史。TTT3R 读取上一段 49 帧；原生 warper 用末尾 5 个连续上下文视图初始化和拟合 GS，首段只用第 1 帧。这不是均匀抽取 5 个历史关键帧。使用原生 WorldWarp GS 与异步扩散，不接入 MapAnything 或 GaME。
4. 5 段，每段 49 帧；首段上下文 1 帧，后续各重叠 5 个生成历史帧。拼接去重得到 49+4×44=225 帧。GS 500 步，位置学习率 1.6e-3；strength 0.8，采样 50 步，CFG 5，seed 32。Qwen 根据起始图及生成历史自动写 caption。
5. 编码前保存生成 PNG，与相同索引、相同裁剪的真实 PNG 计算全图指标；输入帧不进入平均新视角分数。视频编码不参与评分。

## 指标定义和不能直接对照论文的部分

- PSNR：RGB [0,1] 均方误差转 dB；SSIM：11×11 高斯窗、sigma=1.5、总体协方差、RGB 通道平均。LPIPS：AlexNet、v0.1。论文未公开具体 SSIM 实现或 LPIPS 主干，因此此处固定定义用于后续本地比较。
- FID：pytorch-fid 的标准 Inception-v3 2048 维特征。小样本用低秩协方差因子的等价公式计算，避免奇异矩阵开方；数学可计算不代表统计可靠。
- 位姿：使用独立的官方 DUSt3R 512 DPT 权重，从生成图重建相机；不把请求相机直接当成生成相机。第 50 帧使用索引 0、9、19、29、39、49；第 200 帧使用 0、9、19、…、199。完整双向配对、MST 初始化、全局优化 300 步、cosine 调度、lr=0.01。各端点分别重建。
- R_dist 按论文旋转测地距离，主表用弧度。t_dist 按 L2，先相对第一帧，然后预测和真值各除以各自轨迹内最远距离；没有再对 GT 做 Procrustes 拟合。论文没有公开具体归一化代码，因此这一定义需要固定后再比较其他管线，不能解释为米。
- 另对真实视频使用同一 DUSt3R 过程，展示估计器自身的误差参照；这不是可直接减掉的噪声下界。pose_metrics.json 也保存 TTT3R 参考相机相对数据集相机的误差，以及生成相机相对 TTT3R 控制轨迹的诊断值。
- 严重模糊或结构崩坏的生成画面也可能使 DUSt3R 位姿不可靠。给出有限数值仅表示重建过程完成，不等于相机一定恢复准确；真实视频上的估计误差也不能作为这些退化画面的误差上界。位姿分数需要结合图像指标和实际画面一起阅读。
- 未公开的论文场景划分、采样间隔、相机评测代码不能复原。本次只代表这里固定的场景、现有低分辨率图片、前 225 帧顺序和本地代码。原始片段的实际采集帧率未从分片中确认，不能把此处 50 帧运动跨度假定为论文的同一跨度。

- 本地适配器把上一段解码后的 uint8 RGB 直接作为下一段图像历史，不经过 MP4 再解码；caption 仍读取分段视频。这与已有原版基线相同，扩散仍使用 WorldWarp 原生实现。

## 文件与复用

- metrics_summary.json：可供 AI 工具读取的总表；每个场景 image_metrics.csv / image_metrics.json / pose_metrics.json：明细。
- gt/、generated/：225 帧无损图片；dataset_cameras.npz、reference_ttt3r_cameras.npz：数据集与实际控制相机。
- reference_ttt3r_depth_DIAGNOSTIC_ONLY.npy：参考视频深度，仅作诊断；generation/artifacts/：每段最终 GS、caption、扩散调度图、分段视频。没有逐 GS 迭代模型或逐去噪 latent。
- dust3r_*.npz：真实与生成视频重建的相机；inception_features.npz：FID 特征。
- plan.json、preflight.json、status.json、logs/：执行参数、状态与日志。下载整个本目录即可离线查看文档及所有引用的图片和视频。

复跑入口（输出目录必须不存在，先检查 GPU）：

```bash
python scripts/pipelines.py benchmark plan --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/selected_manifest.json --count 1 --output runs/NEW_RUN --gpu GPU_ID --camera-intrinsics upstream-mean --camera-source dataset-calibrated --audit-guidance
python scripts/pipelines.py benchmark doctor --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/selected_manifest.json --count 1 --output runs/NEW_RUN --gpu GPU_ID --camera-intrinsics upstream-mean --camera-source dataset-calibrated --audit-guidance
python scripts/pipelines.py benchmark run --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/selected_manifest.json --count 1 --output runs/NEW_RUN --gpu GPU_ID --camera-intrinsics upstream-mean --camera-source dataset-calibrated --audit-guidance
```

方法依据：[WorldWarp 论文 §5 与补充 §7](https://arxiv.org/html/2512.19678v1)、[官方代码](https://github.com/HyoKong/WorldWarp)、[DUSt3R 官方代码](https://github.com/naver/dust3r)、[LPIPS](https://github.com/richzhang/PerceptualSimilarity)、[pytorch-fid](https://github.com/mseitzer/pytorch-fid)。
