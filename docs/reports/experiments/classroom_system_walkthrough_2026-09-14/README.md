> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../Reports/classroom_system_walkthrough_2026-09-14/README.md)。本目录未复制视频或大型资产。

# Classroom：从一张图片到完整视频的中间结果说明

本报告使用 **2026-09-14 完整记录的 classroom 重跑结果**，沿着实际数据流解释：一张图片如何变成深度和三维表示，三维表示如何产生目标视角的 RGB 与有效掩码，这些条件如何控制 WorldWarp，生成的画面又如何进入下一段，最终组成视频。

以 **G：MapAnything + 原图约束 + WorldWarp 原生 3DGS + WorldWarp 视频生成** 为主线；A 原版、F 滚动几何、H 点云渲染及旧 GaME 分支放在后面说明。G 不调用 GaME，也不调用 TTT3R 模型，但仍使用 WorldWarp 自带的 GS 建模代码。

**阅读入口：** Markdown 从本文件开始；浏览器可直接打开同目录的 [完整离线图文版](../../../../Reports/classroom_system_walkthrough_2026-09-14/index.html)，或打开 [视频与逐帧对照播放器](../../../../Reports/classroom_system_walkthrough_2026-09-14/viewer.html)。本文引用的图片、视频及示例数据均在本文件夹内，使用相对路径，可以将整个文件夹复制到其他机器查看。

**先明确时长：这批实际保存的视频是 4 段合计 10.7 秒，而非每段 10.7 秒。** 每个成片 321 帧、30 fps、480×608。本文解释这批真实结果，没有把它描述成 42.8 秒，也没有重新运行视频模型。

## 1. 先看完整数据流和最终效果

![主线数据流](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/pipeline.png)

可以把系统理解成两个互相配合的部分：几何部分提供“按指定相机看过去，已有画面大致应该落在哪里，以及哪些位置有来源支持”；视频模型根据这些几何条件、文本描述和历史上下文，联合生成一整段连续画面。

**一段内部并不是先独立生成第 1 帧，再独立生成第 2 帧。** 本次 WorldWarp 在压缩后的视频 latent 上联合处理 81 或 85 帧对应的时空数据。真正的循环发生在段与段之间：一段完成后，挑出历史画面，重估下一段的几何，并提供连续的上下文帧。

[观看 G 完整视频](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_final.mp4) · [观看 G 四阶段同步视频](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_stages_sync_321.mp4)

<video controls preload="metadata" width="100%" poster="images/stages_at_boundaries.png" src="../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_stages_sync_321.mp4"></video>

同步视频从左到右依次为 **几何 RGB → 二值有效掩码 → 实际送入 VAE 的 RGB → 生成帧**。四列是同一全局帧号、同一请求相机。最后一列来源于保存的编码前 PNG，再编码成便于播放的演示视频；原始交付 MP4 单独提供，两者不是同一个压缩文件。

| 步骤 | 接收什么 | 输出什么 | 下一个环节怎样使用 |
|---|---|---|---|
| 输入准备 | 一张原始照片 | 480×608 RGB、请求相机轨迹 | RGB 进入几何模型，相机定义要看的方向 |
| MapAnything | 原图 / 历史关键帧、给定 K 和 c2w | 原生深度、点图、射线、置信度、mask、预测相机 | 本适配器主要取 depth_z 和 mask，恢复到视频分辨率 |
| 几何适配 | 原生预测、预处理相机、请求相机 | 对齐的 RGB-D、valid、K、c2w | 反投影初始化 GS，提供颜色和深度监督 |
| GS 拟合 | RGB-D、多视图相机 | 可渲染的高斯参数、训练损失和训练渲染 | 用最终参数渲染下一段的所有目标相机 |
| 目标视角渲染 | GS、目标 K/c2w、来源有效区域 | 每帧 warped RGB 与 alpha | RGB 成为扩散参考；alpha 决定有效 / 待补区域 |
| 条件整理 | 几何 RGB、alpha、1 或 5 个上下文帧 | 精确的 VAE 输入 RGB、二值 mask、latent mask | VAE 编码 RGB；mask 决定分区域噪声日程 |
| WorldWarp ST-Diff | 视频 latent、mask、文本、随机噪声 | 整段生成 latent | VAE 解码成所有输出帧 |
| 输出与反馈 | 解码帧 | 分段视频、最终 MP4、历史关键帧与上下文 | 裁剪 / 去重后交付；历史图像供下一段重建 |

## 2. 输入到底是什么，相机又从哪里来

![原图与模型输入](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/input_pair.png)

本次唯一真实观测是 [原始 classroom.png](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/input_original.png)，尺寸 **1320×1681**。准备脚本保持比例缩放、中心裁剪到 [480×608 输入图](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/input_prepared.png)。后续出现的其他视角都是模型生成的，不是现场拍摄的多视图照片。

原版接口接受视频，所以首段还构造了一份重复原图 81 次的输入视频。这只是在适配接口，**重复图片不会增加真实几何信息**。G 首段的 MapAnything 几何推理直接使用 1 个原图视图。

本次为相机指定固定内参，而不是从照片中测量真实镜头参数：

```text
K = [[576,   0, 240],
     [  0, 576, 304],
     [  0,   0,   1]]

c2w = 相机坐标 → 世界坐标的 4×4 变换矩阵
w2c = inverse(c2w)
```

轨迹保持相机中心不动，绕 Y 轴做负向旋转，即脚本约定的匀速向左转。第 g 帧的角度为 `−0.0625° × g`，g 从 0 到 320；总转角 −20°，角速度 −1.875°/秒。没有平移、变焦、俯仰或滚转。

完整相机数组在 [requested_camera_trajectory.npz](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/requested_camera_trajectory.npz)，`c2w` 为 `[321,4,4]`，`intrinsics` 为 `[321,3,3]`。这份实际请求轨迹是判断运动的依据；[配置快照](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/config.yaml)还保留了上游通用的相机模板字段，不能据此把本次运动误读成模板中的 `pitch`。

这里的“请求相机”是期望生成的视频运动。模型输出是否严格遵守该相机，是另一个需要验证的问题，不能把请求轨迹当成对生成视频实测出的相机真值。

## 3. 首段：MapAnything 从一张图输出了什么

G 第 0 段把原图连同给定 K/c2w 送入 MapAnything。模型预处理后的原生图像为 **406×518（宽×高）**；数组中的空间维度按高、宽排列，即 `[518,406]`。

![实际 MapAnything 输出](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/map_geometry.png)

上图来自实际参与首段生成的预测。两个深度图共用同一色标；蓝紫色较近、红色较远。深度是模型估计值，本次没有测量尺度基准，不能直接当作经过标定的教室尺寸。原生 mask 几乎全白，意味着模型认为大部分像素可用；这并不证明深度正确。

| 原生字段 | 本例形状 | 含义 | 在当前下游中的作用 |
|---|---|---|---|
| `depth_z` | `[1,518,406,1]` | 相机 z 轴方向深度 | **实际用于恢复深度、反投影和 GS 深度监督** |
| `depth_along_ray` | `[1,518,406,1]` | 沿射线方向的距离 | 保存供检查；不能与 z 深度无条件互换 |
| `pts3d` / `pts3d_cam` | `[1,518,406,3]` | 世界 / 相机空间逐像素三维点 | 完整保存；本适配器会用保留的相机重新反投影 |
| `ray_directions` | `[1,518,406,3]` | 逐像素射线方向 | 保存供诊断 |
| `conf` | `[1,518,406]` | 模型置信度分数 | 保存并恢复到视频空间；本配置未开启置信度筛除，也未按它加权 GS 损失 |
| `mask` | `[1,518,406,1]` | 原生预测有效掩码 | 与有限、正深度检查结合，决定可用深度 |
| `non_ambiguous_mask` 等 | `[1,518,406]` | 内部有效性相关输出 | 原样保存，便于进一步检查 |
| `intrinsics` / `camera_poses` | `[1,3,3]` / `[1,4,4]` | 模型预测的相机参数 | 保存诊断，**下游仍保留我们给定的相机** |
| `cam_trans` / `cam_quats` / `metric_scaling_factor` | 小型向量或矩阵 | 位姿、尺度相关预测 | 原样保存，本实验没有据此声明实测尺度 |
| `img_no_norm` | `[1,518,406,3]` | 模型预处理后的可显示 RGB | 检查空间对齐 |

本地示例包括 [原生预测 NPZ](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/map_first_native/prediction_arrays.npz)、[完整原始预测 PT](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/map_first_native/prediction.pt)、[实际预处理输入 PT](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/map_first_native/processed_input.pt)和 [字段元数据](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/map_first_native/metadata.json)。PT 保留原始对象与 dtype；NPZ 便于 NumPy 读取，遇到 BF16 字段会用 FP32 精确表示其数值。

本次关键开关是 `apply_mask=True`、`mask_edges=False`、`apply_confidence_mask=False`，推理使用 BF16。输入标记 `is_metric_scale=False`，并设置 `ignore_pose_scale_inputs=True`，因为纯旋转没有提供可测量的平移基线。

### 为什么保存预测相机，却继续使用给定相机

我们希望保持预先指定的相机轨迹。MapAnything 虽然接收相机条件，预测输出仍可能与给定值略有不同。例如本例预处理 K 的焦距约 490.737，而模型预测的 fx、fy 约 477.844、510.373。适配器保留请求 K/c2w，避免把这些变化直接引入视频轨迹。详细数值见 [首段几何报告](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/reports/G_chunk_000_geometry.json)。

这一选择也有代价：预测深度与保留相机未必完全一致。因此“给了相机条件”不能理解成模型预测天然满足所有几何约束。

## 4. 原生预测怎样变成能建模的 RGB-D

MapAnything 输出位于 406×518 网格，视频位于 480×608 网格。这里不能只改数组尺寸，还要对应预处理造成的像素坐标变换。

对视频空间像素 `p = [u,v,1]ᵀ`，用 `p_native ∼ K_processed × inverse(K_video) × p` 找到原生空间采样位置。其中 `K_processed` 是实际预处理输入的相机，不是模型另行预测的 K。

深度恢复采用有效性加权的双线性采样：

```text
weight = remap(native_valid)
numerator = remap(native_depth_z × native_valid)
restored_depth = numerator / max(weight, 1e-6)
restored_valid = weight > 0.999 且深度有限、为正
无效位置的 restored_depth 置 0
```

这样可以避免把无效深度 0 直接混入有效深度边界。结果写入 [G_first_posed_rgbd.npz](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/G_first_posed_rgbd.npz)：

| 字段 | 首段形状 | 作用 |
|---|---|---|
| `rgb` | `[1,608,480,3]`，uint8 | 拟合目标颜色 |
| `depth_z` | `[1,608,480]`，float32 | 初始化三维点，监督 GS 逆深度 |
| `valid` | `[1,608,480]`，bool | 来源有效支持域 |
| `confidence` | `[1,608,480]`，float32 | 保留诊断，当前不进入损失权重 |
| `intrinsics` / `c2w` | `[1,3,3]` / `[1,4,4]` | 与 RGB-D 对齐的请求相机 |
| `frame_ids` / `observed` | `[1]` / `[1]` | 全局帧号，以及是否来自唯一真实原图 |

接着用深度和相机做反投影：

```text
X_camera = depth_z × inverse(K) × [u,v,1]ᵀ
X_world  = R_c2w × X_camera + t_c2w
color    = RGB(u,v)
```

![反投影点云](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/pointcloud.png)

上图从实际恢复后的深度反投影得到，每 5 个像素抽样一次，用两个辅助观察角度展示。它不是新增推理视图，也不是最终视频中的相机画面。可读取 [抽样点云数组](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/G_first_pointcloud_sample.npz)。单图提供的是可见表面，遮挡背面和视野外区域仍然缺少观测。

实现依据见 [几何恢复适配代码](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/source/mapanything_worldwarp_rgbd.py)中的预处理和 `remap`，以及 [建模适配代码](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/source/worldwarp_map_geometry.py)中的 `unproject_sources`、`render_geometry`。

## 5. GS 怎么拟合，中间模型、渲染、损失各代表什么

GS 是 3D Gaussian Splatting（三维高斯泼溅）：用一组带位置、大小、方向、透明度和颜色参数的三维高斯来表示场景。它接收上一步的 RGB-D，而不是凭空生成一间完整教室。

G 首段最多抽取 50,000 个深度点，实际初始化 50,000 个高斯；后续多视图按每个来源最多 50,000 点、总数上限 350,000 初始化，本次四段分别为 **50,000 / 250,000 / 300,000 / 300,000** 个。每段单独优化 500 次，不优化相机位姿。

每次优化会选择一个来源视角，用当前 GS 渲染这个视角，把渲染 RGB、深度与该来源图像的 RGB-D 比较，计算损失，再更新高斯参数。当前原生 GS 的损失为：

```text
loss = 0.8 × L1_RGB
     + 0.2 × (1 − SSIM)
     + 0.01 × L1_inverse_depth
```

深度项在有效深度像素上比较逆深度；监督目标是估计的 RGB-D，**不是实测三维真值**。后续 G 把原图视角放入训练视角列表两次，生成历史视角各一次，因此原图的抽样权重为 2，历史视角为 1。首段只有原图，权重为 1。

![GS 训练演变](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/GS_evolution.png)

[播放全部 500 次实际训练渲染](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_GS_training_all500.mp4)。演示以每秒 20 次迭代播放，25 秒走完，不表示实际训练耗时。首段只有一个训练来源，所以可以直接观察这个视角逐渐拟合的过程。其他多视图段的训练渲染会随所抽到的来源视角切换，不能把这种切换误认为模型在抖动。

![GS 首段完整损失](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/GS_first_losses.png)

本次首段总损失从第 1 次的 **0.175982** 降到第 500 次的 **0.008309**。这说明模型更接近当前训练输入，不能据此证明新视角、未观测区域或视频内容一定更真实。每次各分项数值见 [G 首段完整 500 行损失表](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/losses/G_chunk_000.csv)。

**保存文件之间有一个关键的先后关系：**

```text
模型 iteration_000000
  → 用它渲染并计算第 1 次损失
  → 更新参数
  → 模型 iteration_000001
  → 用它渲染并计算第 2 次损失
  → ……
  → 第 500 次训练渲染使用模型 499
  → 更新后得到最终模型 500
```

报告包带有 [初始模型 0](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/models/G_chunk000_iteration_000000.pt)、[模型 250](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/models/G_chunk000_iteration_000250.pt)、[最终模型 500](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/models/G_chunk000_iteration_000500.pt)，以及 [第 500 次训练 RGB/alpha/depth 和相机数组](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/GS_training_iteration_000500.npz)。这些都是原归档文件的直接复制。

完整归档保存了每次迭代模型；本说明包选择 3 个完整模型作为可读示例，全部 500 次渲染通过视频展示，14 次拟合的全部损失表都放在 [data/losses](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/losses)。没有把约 311 GiB 的整个原始归档再复制一遍。

实现依据为 [原生 GS 源码](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/source/worldwarp_ttt3r.py)中的 `_initialize_splats_from_depth`、`_train_splats`、`_rasterize_splats`；记录对齐规则见 [拟合记录说明](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/reports/GS_first_manifest.json)。

## 6. 最终 GS 如何渲染下一段全部相机

GS 完成后，对下一段的每个目标 K/c2w 渲染一次，得到 RGB 和连续 alpha。RGB 是几何认为目标相机能看到的颜色，alpha 描述渲染覆盖；两者都不是最终视频。

对于本次纯旋转，适配器还将每个来源的 valid 投影到目标视角，取所有来源支持区域的并集。该支持域与渲染 alpha 相乘后，才作为交给 WorldWarp 的有效程度。来源支持域指“当前输入中是否有颜色 / 深度来源”，并不等同于“真实世界中已被观测和验证”。后几段的来源中包含生成历史帧。

```text
source_support = 各来源有效区域按请求旋转投影后的并集
valid_alpha = rendered_alpha × source_support
输出：warped_rgb[t]、valid_alpha[t]、target_cameras[t]
```

首段目标帧为全局 0–80。转向左侧以后，原照片没有覆盖的新区域出现在画面左边；几何渲染可能在那里出现黑色、空洞或模糊的边界。这些位置正是需要视频生成模型补充的部分。

![全局帧 80 的完整条件链](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/frame080_fullchain.png)

这张图全部来自同一个目标帧：

1. **几何 RGB：**已有桌椅和黑板随请求相机投影，左侧存在缺失。
2. **浮点 alpha：**展示连续有效程度，0 为黑、1 为白，细节处可能小于 1。
3. **二值 mask：**按阈值将区域分成已有支持与待补部分。
4. **latent mask：**进一步腐蚀、降采样后，交给 ST-Diff 调度的掩码。
5. **VAE 输入 RGB：**这是送入视频 VAE 编码的实际画面。
6. **生成帧：**视频模型解码后的画面，缺失区得到补充，已有内容也可能被修改。

本例有效面积在首段末尾约 **86.77%**，但这是阈值后的几何覆盖率，不是深度准确率、生成成功率或真实区域占比。精确值及每帧统计在 [measured_facts.json](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/measured_facts.json)与 [321 帧索引](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/G_delivered_frame_index.json)。

## 7. RGB、alpha、mask 怎样变成扩散条件

这里存在四个不同层次的数据，混在一起看容易误判。

| 数据 | 保存时点与处理 | 为什么需要 |
|---|---|---|
| `raw_geometry_warp/rgb.npy`、`alpha.npy` | 桥接渲染返回后、WorldWarp 自身阈值化和上下文替换前 | 检查几何模块实际交出了什么 |
| `diffusion_condition/rgb_float32.npy` | RGB clamp 到 `[0,1]`，并替换上下文画面之后 | 精确记录 VAE 编码前的 RGB |
| `binary_mask.npy` | alpha `<0.5` 为 0，`≥0.5` 为 1 | 记录像素空间的有效 / 无效划分 |
| `latent_mask.npy` | 时间每 4 帧取样，15×15 腐蚀，再按空间 8 倍最近邻降采样 | 对齐视频 latent 的尺寸，控制各时空位置的噪声 |

第一段的前 1 帧会用实际输入视频的对应画面覆盖几何 RGB。后续段前 5 帧用上一段末尾的真实解码画面覆盖，这里的“真实解码”指实际读到的生成视频像素，并不是新增的现场观测。后续帧保留几何渲染参考。

15×15 腐蚀要求邻域全部有效，因而会扩大边缘和孔洞的待补区域。这样可减少几何边界伪影被过分保留，但也可能放松本来可保留的细节。它不是对 RGB 做腐蚀。

VAE 在本次设置下按时间 4 倍、空间 8 倍压缩：81 帧对应 21 个时间 latent，85 帧对应 22 个；480×608 对应 60×76 latent 空间网格。条件掩码形状分别为 `[1,21,1,76,60]` 和 `[1,22,1,76,60]`。这也解释了为什么使用满足 `帧数 = 1 + 4k` 的段长度。

本包保留 [首段完整 latent mask](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/G_chunk000_latent_mask.npy)、[目标 / 来源相机请求示例](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/G_chunk000_camera_request.npz)和 [全局 80 帧的浮点中间数组](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/G_frame_080.npz)。[60×76 原生掩码 PNG](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/latent_mask_native_60x76.png)可查看像素级网格；文中放大的掩码使用最近邻，仅用于显示。

桥接模块内部可能已经对 RGB 做过 clamp，因此这里的“raw”严格指 WorldWarp 条件整理之前，不意味着早于几何适配器的所有处理。

## 8. WorldWarp 怎样利用这些条件生成一整段

本次使用 WorldWarp 微调权重，基础视频模型为 Wan2.1 T2V 1.3B。文本经过文本编码器形成条件；VAE 输入 RGB 被编码并归一化为视频 latent；有效掩码在 latent 网格上选择噪声日程。三个条件作用不同：

| 条件 | 主要作用 | 本次具体来源 |
|---|---|---|
| 文本 | 约束场景语义、外观和内容 | 缓存的实际分段 caption、固定负面提示词 |
| 几何 RGB latent | 提供已有内容在新视角的大致位置和外观 | 上一步渲染，再替换连续上下文 |
| latent 有效掩码 | 区分有几何支持和需要更自由补充的时空位置 | alpha 阈值、腐蚀、降采样 |
| 连续上下文 latent | 将新一段接在历史画面之后 | 首段 1 帧；后续 5 帧 |
| 随机噪声 | 提供生成随机性 | seed 32 的采样状态 |

本次重跑复用了历史运行的实际 caption，因此不是每次重新请求视觉语言模型生成描述。四段的 [caption 文件](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/captions)和 [固定提示词配置](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/config.yaml)都在包内。caption 是语言描述，不是精确物体清单；几何控制也不是简单地把“向左转”写进文本。

### 有效区域与无效区域采用不同的噪声起点

共有 50 次采样循环，`strength=0.6` 对应实现中的 `minxs=0.4`，于是有效区使用调度器第 `int(0.4×50)=20` 个索引的噪声等级起步，无效区从最高噪声等级起步。有效区在前面的调度阶段保持其起始等级，随后随采样降低噪声；无效区经历完整的高噪声到低噪声过程。

```text
z_ref = VAE 编码、归一化后的参考视频
epsilon = 采样噪声
z_start = (1 − sigma_start) × z_ref + sigma_start × epsilon

有效区：sigma_start 取调度器索引 20
无效区：sigma_start 取调度器索引 0
上下文：使用干净的参考 latent，并在采样时保持固定
```

`strength=0.6` **不等于 60% 原图混合或 60% 的 RGB 噪声**。实际 sigma 由 FlowMatch 调度器给出，需要区分配置参数、调度索引、噪声强度与像素混合。

每次模型更新同时使用有文本条件和无文本条件的预测，通过 CFG=5 合成，随后做 flow-matching 的 Euler 更新。代码中的简化关系是：

```text
prediction = uncond + 5 × (cond − uncond)
z_next = z_current + (sigma_next − sigma_current) × prediction
```

只有上下文 latent 被专门保持固定。已有几何支持的其他区域仍然允许生成模型修改；即使上下文 latent 固定，VAE 编解码也不保证输出 RGB 与输入图片逐像素相同。

### 实际保存的日程图怎样读

[查看完整噪声日程图](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/noise_schedule_original.png)。横向按视频 latent 时间位置排列，纵向按采样步骤排列，每个小格内部仍然是空间网格，颜色表示噪声时间等级。上下文位置为零噪声，已有支持与待补区域采用不同日程。

![实际噪声日程缩略图](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/noise_schedule_preview.png)

**这张图是噪声日程，不是逐步去噪后的图像。** 这次几何中间结果归档没有保存每一个扩散采样步的 latent 或解码图片，也没有保存 VAE 编码后的完整 latent 张量。本文依据实际源码解释这个内部过程，展示的是已保存的 VAE 前条件、日程可视化和最终解码帧，不虚构未记录的采样状态。

相关实现可在 [WorldWarp 推理源码](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/source/worldwarp_pose_control.py)的 `run_inference_chunk`、`sample_sequence`、`flow_matching_sample_step` 中直接核对。

## 9. 第一段完成以后，历史怎样进入第二段

一段生成 latent 经 VAE 解码、后处理为 uint8 RGB，再写成分段视频。此次额外保存了 **MP4 编码前的每张 uint8 PNG**。下一段几何和上下文从实际保存的视频读取历史帧，因此存在视频编解码这一步；它们不必与编码前 PNG 逐像素一致。

反馈有两条用途不同的路径。

**路径一：抽取历史关键帧，重新估计几何。** 第 0 段生成全局 0–80；随后 G 使用原始图片 0，以及历史生成帧 20、40、60、80。第 2 段则使用原图 0，加上上一段的 80、100、120、140、160。

![第 2 段的实际几何来源](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/history_sources_chunk2.png)

第一格是始终保留的原图，后五格来自生成历史。它们带有对应请求相机，一起进入 MapAnything 多视图推理，得到这一轮新的 RGB-D，再初始化、拟合新的 GS。**本适配器每段重新拟合场景，并没有把上一段 GS 持续增量更新成一个全局地图。** 被继承的主要是图像信息。

**路径二：取连续末尾帧，作为视频上下文。** 第 1 段在生成时，把全局 76、77、78、79、80 作为 5 个连续条件帧。这些帧替换几何渲染前缀，并在 latent 采样阶段提供固定上下文。

![第二段的连续上下文](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/context_chunk1.png)

| 对比 | 几何关键帧 | 视频上下文 |
|---|---|---|
| 如何选 | 上一段局部 0、20、40、60、80，G/H 再加原图并去重 | 上一段末尾连续 5 帧 |
| 时间分布 | 稀疏、跨度较大 | 连续、靠近边界 |
| 送给谁 | MapAnything → GS / 点云 | VAE → WorldWarp 采样 |
| 主要用途 | 提供更多已生成视野，支撑下一段几何 | 延续局部运动和外观，减轻接缝 |
| 是否为新增真实观测 | 否，只有单独保留的原图是真实输入 | 否，来自生成视频 |

这样的反馈能让新生成的左侧内容在下一段获得几何支持；同时也会把上一段的文字变形、物体变形、模糊和相机偏差带到下一轮。原图权重 2 是软约束，不能保证完全消除误差积累。

## 10. 四段如何裁剪、去重，最终得到 321 帧

下表以 G/F/H 的实际帧映射为准，所有区间均包含端点。段编号从 0 开始。

| 段 | 本段几何输入：G 的全局来源帧 | 原始生成目标帧 | 视频上下文 | 原始输出帧数 | 裁剪后分段 MP4 | 最终新增交付帧 |
|---|---|---|---|---:|---|---|
| 0 | 0 原图 | 0–80 | 0 | 81 | 0–80，共 81 帧 | 0–80，共 81 帧 |
| 1 | 0 原图、20、40、60、80 | 76–160 | 76–80 | 85 | 80–160，共 81 帧 | 81–160，共 80 帧 |
| 2 | 0 原图、80、100、120、140、160 | 156–240 | 156–160 | 85 | 160–240，共 81 帧 | 161–240，共 80 帧 |
| 3 | 0 原图、160、180、200、220、240 | 236–320 | 236–240 | 85 | 240–320，共 81 帧 | 241–320，共 80 帧 |

后续每段的 85 帧先删除前 4 帧，得到带一个边界重叠帧的 81 帧分段视频；拼接时再跳过这个重叠帧。于是：

```text
原始采样帧数：81 + 85 + 85 + 85 = 336
裁剪后的 4 个分段：4 × 81 = 324
最终交付：81 + 80 + 80 + 80 = 321 帧
播放时长：321 / 30 = 10.7 秒
末帧时间戳：320 / 30 = 10.6667 秒
```

末帧时间戳与媒体播放时长相差一帧时长，是正常的计数差别。原版 A 使用 1 帧上下文，每段原始输出都是 81 帧，直接跳过后三段的首个重叠帧，也得到 321 帧。

![帧映射与实际覆盖率](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/timeline_coverage.png)

下半图展示 G 的实际二值掩码有效面积。每段开头引入较新的历史视图后，覆盖率会回升；随后继续转向未知方向，覆盖率又下降。**覆盖率回升反映当前来源支持变多，不等于拿到了新的真实观测。**

可以逐段查看 [第 0 段](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_chunk_000.mp4)、[第 1 段](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_chunk_001.mp4)、[第 2 段](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_chunk_002.mp4)、[第 3 段](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_chunk_003.mp4)，或读取 [完整交付帧索引](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/G_delivered_frame_index.json)。原始上下文前缀是否保留、局部帧与全局帧的关系，另见 [分段索引目录](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/frame_index)。

## 11. 把四段末帧放在一起看

![四段末尾阶段对照](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/stages_at_boundaries.png)

每行分别是全局 80、160、240、320；每列分别是几何 RGB、二值 mask、VAE 输入 RGB、生成帧。可以沿行观察“同一目标帧怎样被补全”，也可以沿列观察“随着历史反馈，几何条件和生成结果怎样变化”。

这些都是段末尾帧，不属于上下文前缀，因此几何 RGB 与 VAE 输入 RGB 在这些位置通常相同或仅有数值整理差异。要观察上下文替换，应看第 9 节的全局 76–80 条件帧。

此处能够直接观察到：几何渲染留下的新视野缺口被生成模型填补，桌椅与墙面文字也可能随生成发生变化。不能仅凭“孔洞补上了”判断生成区域符合真实教室布局；原图之外没有对应真值图像。

四条独立全长轨道也已打包：[几何 RGB](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_geometry_321.mp4)、[二值 mask](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_binary_mask_321.mp4)、[VAE 输入 RGB](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_condition_321.mp4)、[生成帧演示](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_generated_precodec_321.mp4)。[播放器](../../../../Reports/classroom_system_walkthrough_2026-09-14/viewer.html)支持同步播放、定位时间和查看选定帧的 PNG；关键帧 PNG 与对应浮点 NPZ 分别位于 [images/frames](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/frames)和 [data/examples](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples)。

## 12. A / F / G / H 各自换了哪一部分

| 版本 | 几何估计 | 场景表示 / 渲染 | 历史策略 | 视频上下文 |
|---|---|---|---|---|
| A 原版 | TTT3R | WorldWarp 原生 GS | 原版输入序列与来源选择 | 所有段 1 帧 |
| F | MapAnything | WorldWarp 原生 GS | 后续段只使用上一段 5 个均匀历史帧 | 首段 1 帧，后续 5 帧 |
| G | MapAnything | WorldWarp 原生 GS | F 的历史策略，加原始图片；同一全局 0 去重 | 首段 1 帧，后续 5 帧 |
| H | MapAnything | 直接点云投影与融合 | 与 G 相同的原图 + 历史选帧策略 | 首段 1 帧，后续 5 帧 |

共同的采样设置为 strength 0.6、50 步、CFG 5、seed 32、同一输入和请求轨迹，复用对应分段 caption。A 与 F/G/H 的上下文长度不同，因此 A 对比 G 不是只替换一个几何模型的严格单变量实验。F/G/H 生成的历史内容也会逐步不同，后几段的实际几何输入不再完全相同。

[观看本次 A/F/G/H 横纵同步对比](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/AFGH_comparison_321.mp4) · 单独观看 [A](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/A_final.mp4)、[F](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/F_final.mp4)、[G](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_final.mp4)、[H](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/H_final.mp4)。这是同一时刻的空间拼接，视频仍为 10.7 秒。

![本次四版本全局 240 帧](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/AFGH_frame240.png)

此对比使用 9 月 14 日重跑文件。此前 9 月 8 日比较中得到的 PSNR、SSIM、时间误差等数值属于此前的视频，不能直接贴到这次重跑上；本报告没有混用历史指标，也不按单张截图宣布某一分支绝对最好。

### A：TTT3R 的中间结果怎样接到原生 GS

A 将输入序列送给 TTT3R，得到逐帧深度、内部预测 c2w 与内参等信息，再由原生 GS 流程选择来源视角、拟合与渲染。后续段会把 TTT3R 预测的历史相对位姿用于历史部分，并与请求的后续目标轨迹衔接。因此需要区分 **TTT3R 原始预测相机、GS 实际使用相机、请求目标相机**，三者不是同一个量。

![TTT3R 历史帧深度示例](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/TTT3R_example.png)

这张示例是第 1 次历史调用的输入末帧，也就是第一段生成后的全局 80。其深度供下一段几何处理使用。包内附有 [该帧 RGB / 深度 / 预测相机 NPZ](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/TTT3R_call1/frame_080.npz)、[本次调用全部 81 帧预测位姿](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/TTT3R_call1/predicted_c2w.npy)、[预测内参](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/TTT3R_call1/predicted_intrinsics.npy)和 [输入索引](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/TTT3R_call1/frame_index.json)。

原归档共保存 5 次调用 × 81 帧 = 405 个 TTT3R 推理帧。调用 0 输入重复原图，调用 1–3 对前三段生成历史推理；额外调用 4 处理最后一段，是补齐末段几何的诊断，**没有再生成第五段视频**。

### H：不用 GS 时，点云如何形成几何引导

H 将每个来源 RGB-D 反投影为彩色点，投到目标相机的 4 个相邻像素做双线性 splat。每个来源有自己的 z-buffer，只保留接近最近深度的点（阈值为最近深度的 1.02 倍，加数值容差）；多个来源再按覆盖与来源权重融合颜色，原图权重 2，生成图权重 1。

因此 H 有逐帧 warped RGB 和有效掩码，但没有 500 步 GS 优化，也没有 GS 迭代模型。这是该分支的设计，不是漏存了模型。

## 13. GaME 分支处在什么位置，这次记录说明了什么

此前三项目管线的顺序是 **MapAnything → GaME 拟合一个固定场景 → 渲染轨迹 → WorldWarp**。为补齐拟合演变，这次重新拟合了那个共用的静态场景：50 步预热、500 步主拟合，并保存全部 321 个目标视角的渲染。

这次 GaME 输入沿用此前共用场景的 MapAnything RGB-D，不是上面 G 第 0 段的新预测；只有 1 张关键帧、全图静态 mask，没有使用 SAM / 运动分割，也没有运行完整的动态环境更新任务。GaME 接口用 w2c，适配器显式对输入 c2w 求逆。主拟合后有 143,951 个高斯，详情见 [GaME 拟合报告](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/reports/GaME_fit_report.json)。

![GaME 固定场景渲染](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/GaME_static.png)

[观看 GaME 全 321 帧 RGB / alpha 对照](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/GaME_static_guidance_321.mp4)。随着相机转向左侧，原图支持域以外的区域缺少新信息；这个分支没有像 F/G/H 那样，把前面生成的新视野反馈进下一轮建模。

![GaME 主拟合损失](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/GaME_main_losses.png)

包内保留 [50 步预热损失](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/losses/GaME_phase_0.csv)、[500 步主拟合损失](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/losses/GaME_phase_1.csv)和 [末帧 RGB / alpha / 深度 / 相机数组](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/GaME_frame320.npz)。GaME 的损失组成、高斯参数组织与 WorldWarp 原生 GS 不完全相同，不能直接比较两者损失的绝对数值。

**这次重建的 GaME 场景没有继续生成新的 B/C/D/E 视频，也没有参与本报告 A/F/G/H 的生成。** 因此这里把它作为独立分支的真实中间结果展示，不能把这份新 GaME 渲染与旧视频拼成一条声称实际执行过的因果链。

对于当前静态教室，去掉 GaME 可以简化这条实现；但“去掉 GaME”与“去掉三维高斯建模”不是一回事。G 保留了 WorldWarp 原生 GS，H 才改为不做 GS 优化的点云渲染。

## 14. 实际生成中的预测与成片后的逐帧诊断

这是这次归档最容易混淆的地方。

| 记录 | 输入怎么来 | 数量 | 是否影响这次成片 |
|---|---|---:|---|
| F 实际 MapAnything | 首段 1 个视图，后续每段 5 个历史视图 | 16 个视图 | 是 |
| G 实际 MapAnything | 四段分别 1 / 5 / 6 / 6 个视图 | 18 个视图 | 是 |
| H 实际 MapAnything | 四段分别 1 / 5 / 6 / 6 个视图 | 18 个视图 | 是 |
| F/G/H 成片后逐帧 MapAnything | 最终 MP4 解码，按连续 5 帧小窗口重新推理，最后窗口 1 帧 | 每版 321，共 963 帧 | **否，事后诊断** |
| A 的最后一次 TTT3R | 最后一段生成历史 | 81 帧 | **否，补齐末段诊断** |

实际管线没有每生成一帧就调用一次 MapAnything，也没有用事后得到的全部 321 张深度图反过来生成同一个视频。

[观看 G 成片后全部 321 帧 MapAnything 深度诊断](../../../../Reports/classroom_system_walkthrough_2026-09-14/videos/G_MapAnything_posthoc_depth_321.mp4)。该视频使用保存的原生深度预览，每一帧按各自 2%–98% 分位数着色，因此只能粗看结构，**颜色跳动不能直接当作深度数值跳动**。定量比较应读取深度数组，统一尺度与色标。

![G 末帧事后深度诊断](../../../../Reports/classroom_system_walkthrough_2026-09-14/images/map_posthoc_frame320.png)

本包附 [末帧诊断原生数组](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/map_posthoc_frame320/prediction_arrays.npz)、[字段与预览元数据](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/examples/map_posthoc_frame320/metadata.json)、[完整诊断窗口索引](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/reports/G_posthoc_manifest.json)。多视图模型的结果受一组输入图像影响；实际关键帧组与事后连续 5 帧组不同，即使全局帧号相同，也不保证预测完全相同。

## 15. 这些中间结果能解释哪些问题，不能证明什么

**可以定位问题发生在哪一步。** 如果 MapAnything 深度已经把细桌腿和背景混在一起，后续 GS 的几何边界容易出问题；如果 RGB-D 正常但 GS 训练渲染变软，可检查拟合损失、点数与模型参数；如果几何 RGB 仍清楚而生成结果文字明显变化，说明改变发生在视频生成环节；如果后续段逐渐变软，则需要同时检查历史选帧、压缩、重建和生成反馈。

**mask 是控制信号，不是置信度真值。** 二值 mask 为白只意味着该位置被当前几何支持规则接受。孔洞被腐蚀扩大，会让生成自由度增加；错误几何被标为有效，又可能使模型保留错误。置信度图本次被保存，但未开启按置信度过滤或损失加权。

**本次纯旋转不适合单独证明深度估计更准确。** 固定相机中心时，来源像素到目标像素的映射可以写为：

```text
p_target ∼ K_target × transpose(R_target)
           × R_source × inverse(K_source) × p_source
```

在这一投影关系中，正深度会约掉，没有平移带来的视差。因此视频看起来转得正确，并不足以验证三维深度。深度仍影响 GS 初始化、拟合、遮挡 / 有效性等实现环节，但需要带平移、深度真值或独立视角的实验，才能更有力地评估几何改善。

**未观测区域没有真值。** 左侧补出的桌椅、墙面和装饰可能符合视觉常识，却未必是这间教室的实际内容。低时间误差也可能来自画面变模糊，不能只凭平滑度评价真实感与细节。

**GS 原图约束不是像素锁定。** 它增加原图训练视角的抽样权重，扩散仍允许修改有支持区域。原图约束可以减少部分漂移，但没有保证全局几何、文字或家具拓扑一直不变。

**这次重跑不是找回旧运行的内部状态。** 随机种子和提示词等保持对应设置，但 GS 的数值非确定性可能让重跑与旧视频存在差异。本报告所有新可视化都从已记录数组制作，没有重新训练或重新生成视频。

## 16. 文件夹里具体有什么，怎样复查

```text
classroom_system_walkthrough_2026-09-14/
├── README.md                  本文
├── index.html                 完整离线图文版
├── viewer.html                同步视频与关键帧播放器
├── images/                    文中所有图片，含关键帧 PNG
├── videos/                    成片、分段、阶段轨道与演示视频
├── data/
│   ├── examples/              原生 Map、RGB-D、TTT3R、GS 渲染等示例
│   ├── models/                G 首段模型 0 / 250 / 500
│   ├── losses/                14 次 GS 拟合的全部 6,550 行损失
│   ├── captions/              四段实际文本条件
│   ├── frame_index/           四段原始帧与上下文映射
│   ├── reports/               原捕获报告、核验和分支报告
│   ├── source/                解释所依据的本地实现副本
│   ├── measured_facts.json    本报告直接读取的数值
│   ├── provenance.json        素材来源与转换方式
│   └── package_validation.json 本说明包链接、媒体与完整性检查
├── tools/                     示例读取、素材制作和打包核验脚本
└── checksums.sha256            包内文件校验值
```

这是包含全部引用素材的说明包，**不是整个实验归档或模型部署包**。在没有原工作区的机器上，也可以阅读全文、播放所有视频、查看示例图片和数组。查看媒体不需要网络、GPU 或模型权重。重新运行素材制作脚本需要原归档；重新进行模型推理还需要项目环境和权重。

包内提供 [示例读取脚本](../../../../Reports/classroom_system_walkthrough_2026-09-14/tools/read_examples.py)，安装 NumPy 后可在任意目录执行它；若额外带 `--models`，还会用 PyTorch 读取所附三份模型并显示参数结构。脚本按自身位置定位数据，不依赖原服务器路径：

```bash
python tools/read_examples.py
python tools/read_examples.py --models
```

例如读取一个目标帧的中间数组时，主要字段为：

```text
G_frame_080.npz
  raw_rgb       [608,480,3] float32
  raw_alpha     [608,480]   float32
  condition_rgb [608,480,3] float32
  binary_mask   [608,480]   float32，0/1
  global_frame  80
  local_frame   80
  chunk         0
```

报告包保留的原始 JSON 元数据中可能写有原服务器绝对路径，这些是来源记录，**不是本报告加载图片或视频所依赖的路径**。素材是否直接复制、是否由数组转换、是否仅为事后诊断，可查看 [provenance.json](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/provenance.json)。完整原归档的检查结果见 [capture_validation.json](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/reports/capture_validation.json)，本说明包自身的检查结果见 [package_validation.json](../../../../Reports/classroom_system_walkthrough_2026-09-14/data/package_validation.json)。

原归档已检查四个成片的实际解码帧数、相机与输入一致性，以及 14 次拟合的帧号 / 迭代号、模型结构和抽样张量。其总记录为 **6,550 次 GS 优化、6,564 份模型快照、405 个 TTT3R 推理帧、52 个实际 MapAnything 视图、963 个事后 MapAnything 诊断帧、321 帧 GaME 渲染**。这些计数描述完整原归档，本说明包只对模型和数组取了有代表性的样本，媒体引用全部自包含。
