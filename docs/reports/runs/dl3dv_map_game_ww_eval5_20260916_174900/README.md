> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/README.md)。本目录未复制视频或大型资产。

# MapAnything + GaME + WorldWarp：DL3DV 本地 5 场景基准

这是一次按论文已公开方法建立的本地小样本基准，**不是论文官方结果复现**。本次 5 个场景：固定使用之前两批已完成 WorldWarp 基线的五个不同场景，不重新选场景。

[所有场景同时对比视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/all_scenes_comparison.mp4)：每行一个场景，左侧是真实帧，右侧是生成帧。225 帧、30 fps、播放时长 7.5 秒；30 fps 是播放速度，不代表原始采集时间。

## 第 50 / 200 帧指标

第一张输入图计为第 1 帧，因此第 50 / 200 帧分别对应数组索引 49 / 199。以下各场景等权平均，未使用图像配准、挑帧或去除失败案例。

| 帧 | PSNR↑ (dB) | SSIM↑ | LPIPS↓ | R_dist↓ (rad) | t_dist↓ | FID↓（仅 5 张，诊断） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 11.510 | 0.3343 | 0.6445 | 0.6631 | 0.6852 | 213.826 |
| 200 | 11.755 | 0.4198 | 0.7769 | 0.9588 | 0.8428 | 390.429 |

**FID 限制：**每个端点只有 5 张图，协方差秩至多为 4，数值不稳定，不能用于对照论文 FID 排名。全部新生成帧合并的 FID 也只是诊断，帧之间高度相关。
全部 1120 张新生成帧的诊断 FID：144.685。

![逐帧指标](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/metric_curves.png)

## 本地轨迹的运动幅度

下表均按第 50 / 200 帧的顺序列出。GT 角度是端点相对首帧的净旋转，不是累计转角，也不包含平移。不同场景的同一帧号不代表相同运动难度。论文未公开精确采样，因此不能把本地第 50 帧默认为与论文有相同的视角跨度。

| 场景 | GT 净旋转（°） | TTT3R 参考相机相对 GT 的旋转误差（°） | 参考估计 / 数据集标定 f_x |
|---|---:|---:|---:|
| 建筑与雕像 | 23.65 / 85.78 | 0.56 / 8.62 | 1.254 / 1.253 |
| 温室花展 | 40.38 / 62.42 | 7.57 / 14.04 | 1.467 / 1.488 |
| 餐厅 | 85.52 / 35.79 | 3.97 / 3.19 | 1.105 / 1.166 |
| 室外街边商铺 | 23.72 / 16.23 | 2.36 / 3.70 | 1.329 / 1.348 |
| 室内汽车展厅 | 36.75 / 3.89 | 4.78 / 11.22 | 1.435 / 1.465 |

## 各场景

### 建筑与雕像

场景 ID：`032dee9fb0a8bc1b90871dc5fe950080d0bcd3caf166447f44e60ca50ac04ec7`

[并排视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/032dee9fb0a8/comparison.mp4) · [生成视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/032dee9fb0a8/generated.mp4) · [真实视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/032dee9fb0a8/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/032dee9fb0a8/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 13.449 | 0.4565 | 0.5845 | 0.3876 | 0.3948 | 0.0068 / 0.0460 |
| 200 | 10.779 | 0.4123 | 1.0111 | 1.0396 | 1.0488 | 0.0625 / 0.0223 |

画面抽查：第 50 帧三项目仍保留雕像和立柱，但视角偏向初始画面；原版也存在结构和视角偏差。第 200 帧三项目出现大面积模糊、雾状纹理和强光斑，雕像与台阶结构基本丢失；原版虽然几何关系不正确，仍保留可辨的台阶和立柱。此场景后期三项目明显更差。固定 GaME 条件覆盖率同期下降到约 16%，是需要进一步消融验证的相关因素，不能单独认定因果。


![第 50 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/032dee9fb0a8/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/032dee9fb0a8/comparison_frame_200.jpg)

### 温室花展

场景 ID：`0569e83fdc248a51fc0ab082ce5e2baff15755c53c207f545e6d02d91f01d166`

[并排视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/0569e83fdc24/comparison.mp4) · [生成视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/0569e83fdc24/generated.mp4) · [真实视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/0569e83fdc24/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/0569e83fdc24/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 9.003 | 0.1379 | 0.6659 | 0.7142 | 1.8747 | 0.0616 / 0.0598 |
| 200 | 9.120 | 0.1613 | 0.6909 | 1.0863 | 1.0047 | 0.1495 / 0.0148 |

画面抽查：第 50 帧两种生成都偏向起始构图，未跟上真实相机向花坛低处移动的视角。第 200 帧原版大面积模糊，三项目仍保留清晰可辨的红色花艺人形、白色台面和植物，后期外观保持明显较好；但三项目构图仍接近初始视图，与真实相机位置不一致，左侧植物有重影和不自然纹理。保持清晰不等于轨迹跟随正确。


![第 50 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/0569e83fdc24/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/0569e83fdc24/comparison_frame_200.jpg)

### 餐厅

场景 ID：`06da796666297fe4c683c231edf56ec00148a6a52ab5bb159fe1be31f53a58df`

[并排视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/06da79666629/comparison.mp4) · [生成视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/06da79666629/generated.mp4) · [真实视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/06da79666629/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/06da79666629/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 12.579 | 0.4638 | 0.6896 | 1.2455 | 0.5234 | 0.0159 / 0.0155 |
| 200 | 12.187 | 0.6505 | 0.7558 | 0.9906 | 0.4170 | 0.0210 / 0.0273 |

画面抽查：第 50 帧两种生成均未跟随真实相机转向，桌椅与过道布局明显不同。第 200 帧原版明显模糊但仍能辨出窗户和部分座椅；三项目变成近处墙面、卡座与桌角的局部画面，整体房间布局丢失，边缘有重影，未见整体改善。三项目此时 GaME alpha 覆盖约 82%，说明高覆盖率不代表几何条件或目标视角正确。


![第 50 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/06da79666629/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/06da79666629/comparison_frame_200.jpg)

### 室外街边商铺

场景 ID：`3bb894d1933f3081134ad2d40e54de5f0636bd8b502b0a8561873bb63b0dce85`

[并排视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/3bb894d1933f/comparison.mp4) · [生成视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/3bb894d1933f/generated.mp4) · [真实视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/3bb894d1933f/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/3bb894d1933f/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 11.951 | 0.2531 | 0.5977 | 0.4174 | 0.2876 | 0.0383 / 0.0690 |
| 200 | 12.927 | 0.3939 | 0.7813 | 0.2146 | 0.9147 | 0.0329 / 0.0409 |

画面抽查：第 50 帧两种方法仍有清晰店铺细节，但都偏向起始视角，未与真实帧对齐。第 200 帧两者均丢失真实店铺的条纹遮阳篷、橱窗和门：原版变成另一种砖墙窗户布局，三项目变成带长列竖向结构的墙面，仍有明显颗粒与模糊。三项目未保住店铺结构，也没有达到正确新视角。


![第 50 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/3bb894d1933f/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/3bb894d1933f/comparison_frame_200.jpg)

### 室内汽车展厅

场景 ID：`adf35184a12d4cfa3f4248b87aa5adb4f39f179df460d6d76136e13d37299a2a`

[并排视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/adf35184a12d/comparison.mp4) · [生成视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/adf35184a12d/generated.mp4) · [真实视频](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/adf35184a12d/ground_truth.mp4) · [逐帧 CSV](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/adf35184a12d/image_metrics.csv)

| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |
|---|---:|---:|---:|---:|---:|---:|
| 50 | 10.566 | 0.3601 | 0.6849 | 0.5505 | 0.3454 | 0.0163 / 0.0212 |
| 200 | 13.762 | 0.4807 | 0.6453 | 1.4628 | 0.8287 | 0.0243 / 0.0329 |

画面抽查：第 50 帧两种方法均保留清晰车辆，但都停留在偏侧面的起始构图，与真实正面视角不同。第 200 帧原版被大面积网格状纹理和模糊覆盖；三项目仍保留可辨的红色和黄色车辆，外观清晰度较好，但将原敞篷汽车改造成封闭车身，车辆比例、结构、展厅布局及相机视角均不正确。此例体现外观保持改善，同时存在明显内容幻觉，不能据此认为三维重建或轨迹正确。


![第 50 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/adf35184a12d/comparison_frame_050.jpg)

![第 200 帧](../../../../runs/dl3dv_map_game_ww_eval5_20260916_174900/adf35184a12d/comparison_frame_200.jpg)

## 实际流程与参数

1. 从现有 pixelSplat 格式 DL3DV 分片读取相机和图片，按时间戳取前 225 帧。原图 480×270，经 Lanczos4 放大并中心裁剪到 720×480；内参应用同一像素变换，外参由 OpenCV w2c 转为 c2w，统一到第一帧坐标系。
2. 遵循论文补充 §7，用 TTT3R 处理真实参考序列，提取生成所需的参考相机与内参。它产生的真实序列深度仅保存作诊断，**不输入生成的几何拟合或扩散模型**。这属于使用参考视频估计相机的评测设置，不是只给一张图且完全没有轨迹信息的设置。
3. 复用原基线的真实 PNG 和参考相机文件，逐文件核验哈希。MapAnything 仅估计输入首图的深度，使用首图单独 TTT3R 推理所得深度的像素比中位数校准一个全局尺度；没有读取参考序列深度或其他真实帧来建模。GaME 从首图 RGB-D 拟合一次固定静态场景，用完整旋转和平移轨迹渲染 RGB/alpha。没有生成历史回写几何；SE3 渲染使用原生 GS alpha，不使用纯旋转视野单应性裁剪。
4. 5 段，每段 49 帧；首段上下文 1，后续重叠 5 帧，去重后 225 帧。GaME 在 720×480 拟合 500 步，另有原生 50 步预热，GaME seed 0。扩散 strength 0.8、采样 50 步、CFG 5、seed 32 与原基线相同。Qwen 按相同策略描述当前生成历史，因此后续 caption 不保证逐字相同。这是历史三项目架构的基准适配版，不是 classroom B 的 .6/ctx1 原配置复跑。
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
- mapanything/：首图原始几何；geometry/：首图尺度诊断与转换后 RGB-D；scene/：GaME 模型；guidance/：225 帧 RGB/alpha 条件；generation/artifacts/：caption、调度图及分段视频。没有逐 GS 迭代模型或逐去噪 latent，未复制真实参考序列深度。
- dust3r_*.npz：真实与生成视频重建的相机；inception_features.npz：FID 特征。
- plan.json、preflight.json、status.json、logs/：执行参数、状态与日志。下载整个本目录即可离线查看文档及所有引用的图片和视频。

复跑入口（输出目录必须不存在，先检查 GPU）：

```bash
python scripts/pipelines.py benchmark plan --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_map_game_ww_eval5_20260916_174900/selected_manifest.json --count 5 --output runs/NEW_RUN --gpu GPU_ID --method map-game-ww --baseline-runs /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval3_20260916_112915 /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval2_20260916_142500
python scripts/pipelines.py benchmark doctor --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_map_game_ww_eval5_20260916_174900/selected_manifest.json --count 5 --output runs/NEW_RUN --gpu GPU_ID --method map-game-ww --baseline-runs /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval3_20260916_112915 /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval2_20260916_142500
python scripts/pipelines.py benchmark run --manifest /data4/sumai/GIL_ATLAS/runs/dl3dv_map_game_ww_eval5_20260916_174900/selected_manifest.json --count 5 --output runs/NEW_RUN --gpu GPU_ID --method map-game-ww --baseline-runs /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval3_20260916_112915 /data4/sumai/GIL_ATLAS/runs/dl3dv_worldwarp_eval2_20260916_142500
```

方法依据：[WorldWarp 论文 §5 与补充 §7](https://arxiv.org/html/2512.19678v1)、[官方代码](https://github.com/HyoKong/WorldWarp)、[DUSt3R 官方代码](https://github.com/naver/dust3r)、[LPIPS](https://github.com/richzhang/PerceptualSimilarity)、[pytorch-fid](https://github.com/mseitzer/pytorch-fid)。
