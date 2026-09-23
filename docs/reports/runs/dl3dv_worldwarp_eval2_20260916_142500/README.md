> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/README.md)。本目录未复制视频或大型资产。

# WorldWarp：DL3DV 本地 2 场景基准

这是一次按论文已公开方法建立的本地小样本基准，**不是论文官方结果复现**。本次 2 个场景：在生成前查看未测场景的首帧和相机元数据，固定选择室外街边商铺、室内汽车展厅两类典型场景；与上次三个场景不重复，不按生成质量筛选。

[所有场景同时对比视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/all_scenes_comparison.mp4)：每行一个场景，左侧是真实帧，右侧是生成帧。225 帧、30 fps、播放时长 7.5 秒；30 fps 是播放速度，不代表原始采集时间。

## 第 50 / 200 帧指标

第一张输入图计为第 1 帧，因此第 50 / 200 帧分别对应数组索引 49 / 199。以下各场景等权平均，未使用图像配准、挑帧或去除失败案例。

| 帧 | PSNR↑ (dB) | SSIM↑ | LPIPS↓ | R_dist↓ (rad) | t_dist↓ | FID↓（仅 2 张，诊断） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 11.219 | 0.3249 | 0.6282 | 0.5068 | 0.6498 | 279.076 |
| 200 | 11.839 | 0.4117 | 0.7435 | 1.4183 | 0.5118 | 590.039 |

**FID 限制：**每个端点只有 2 张图，协方差秩至多为 1，数值不稳定，不能用于对照论文 FID 排名。全部新生成帧合并的 FID 也只是诊断，帧之间高度相关。
全部 448 张新生成帧的诊断 FID：165.723。

![逐帧指标](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/metric_curves.png)

## 本地轨迹的运动幅度

下表均按第 50 / 200 帧的顺序列出。GT 角度是端点相对首帧的净旋转，不是累计转角，也不包含平移。不同场景的同一帧号不代表相同运动难度。论文未公开精确采样，因此不能把本地第 50 帧默认为与论文有相同的视角跨度。

| 场景 | GT 净旋转（°） | TTT3R 参考相机相对 GT 的旋转误差（°） | 参考估计 / 数据集标定 f_x |
|---|---:|---:|---:|
| 室外街边商铺 | 23.72 / 16.23 | 2.36 / 3.70 | 1.329 / 1.348 |
| 室内汽车展厅 | 36.75 / 3.89 | 4.78 / 11.22 | 1.435 / 1.465 |

## 各场景

### 室外街边商铺

场景 ID：`3bb894d1933f3081134ad2d40e54de5f0636bd8b502b0a8561873bb63b0dce85`

[并排视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/3bb894d1933f/comparison.mp4) · [生成视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/3bb894d1933f/generated.mp4) · [真实视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/3bb894d1933f/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/3bb894d1933f/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 11.935 | 0.2744 | 0.5842 | 0.4448 | 0.5499 | 0.0383 / 0.0690 |
| 200 | 11.068 | 0.3680 | 0.7711 | 0.1651 | 0.8932 | 0.0329 / 0.0409 |

画面抽查：第 50 帧店铺、遮阳篷和窗户仍较清晰，但视角偏向起始画面，与真实帧不同；第 200 帧遮阳篷和橱窗结构已丢失，立面变为另一种窗墙布局，并伴随明显模糊与颗粒状纹理。


![第 50 帧](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/3bb894d1933f/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/3bb894d1933f/comparison_frame_200.jpg)

### 室内汽车展厅

场景 ID：`adf35184a12d4cfa3f4248b87aa5adb4f39f179df460d6d76136e13d37299a2a`

[并排视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/adf35184a12d/comparison.mp4) · [生成视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/adf35184a12d/generated.mp4) · [真实视频](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/adf35184a12d/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/adf35184a12d/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 10.503 | 0.3754 | 0.6722 | 0.5688 | 0.7498 | 0.0163 / 0.0212 |
| 200 | 12.610 | 0.4554 | 0.7158 | 2.6715 | 0.1304 | 0.0243 / 0.0329 |

画面抽查：第 50 帧仍有清晰可辨的两辆车和展牌，但生成视角偏向车身侧面，真实视角已转向车头；第 100 帧主体尚可辨认，右侧背景已有拉伸和重影；第 200 帧出现真实画面中没有的大面积网格状纹理，车辆轮廓、展牌和空间关系显著丢失，最后一帧仍未恢复。


![第 50 帧](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/adf35184a12d/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_worldwarp_eval2_20260916_142500/adf35184a12d/comparison_frame_200.jpg)

## 实际流程与参数

1. 从现有 pixelSplat 格式 DL3DV 分片读取相机和图片，按时间戳取前 225 帧。原图 480×270，经 Lanczos4 放大并中心裁剪到 720×480；内参应用同一像素变换，外参由 OpenCV w2c 转为 c2w，统一到第一帧坐标系。
2. 遵循论文补充 §7，用 TTT3R 处理真实参考序列，提取生成所需的参考相机与内参。它产生的真实序列深度仅保存作诊断，**不输入生成的几何拟合或扩散模型**。这属于使用参考视频估计相机的评测设置，不是只给一张图且完全没有轨迹信息的设置。
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

- 本地适配器把上一段解码后的 uint8 RGB 直接作为下一段图像历史，不经过 MP4 再解码；caption 仍读取分段视频。这样避免把视频编码损失加入几何历史与评分，但与上游演示脚本的视频文件往返存在差异。原生 GS 与扩散算法保持上游实现。

## 文件与复用

- metrics_summary.json：可供 AI 工具读取的总表；每个场景 image_metrics.csv / image_metrics.json / pose_metrics.json：明细。
- gt/、generated/：225 帧无损图片；dataset_cameras.npz、reference_ttt3r_cameras.npz：数据集与实际控制相机。
- reference_ttt3r_depth_DIAGNOSTIC_ONLY.npy：参考视频深度，仅作诊断；generation/artifacts/：每段最终 GS、caption、扩散调度图、分段视频。没有逐 GS 迭代模型或逐去噪 latent。
- dust3r_*.npz：真实与生成视频重建的相机；inception_features.npz：FID 特征。
- plan.json、preflight.json、status.json、logs/：执行参数、状态与日志。下载整个本目录即可离线查看文档及所有引用的图片和视频。

复跑入口（输出目录必须不存在，先检查 GPU）：

```bash
python scripts/pipelines.py benchmark plan --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval2_20260916_142500/selected_manifest.json --count 2 --output runs/NEW_RUN --gpu GPU_ID
python scripts/pipelines.py benchmark doctor --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval2_20260916_142500/selected_manifest.json --count 2 --output runs/NEW_RUN --gpu GPU_ID
python scripts/pipelines.py benchmark run --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval2_20260916_142500/selected_manifest.json --count 2 --output runs/NEW_RUN --gpu GPU_ID
```

方法依据：[WorldWarp 论文 §5 与补充 §7](https://arxiv.org/html/2512.19678v1)、[官方代码](https://github.com/HyoKong/WorldWarp)、[DUSt3R 官方代码](https://github.com/naver/dust3r)、[LPIPS](https://github.com/richzhang/PerceptualSimilarity)、[pytorch-fid](https://github.com/mseitzer/pytorch-fid)。
