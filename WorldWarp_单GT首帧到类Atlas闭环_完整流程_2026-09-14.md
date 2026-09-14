# WorldWarp 主导的类 Atlas 管线：从单张 GT 首帧到连续新视角视频

## 本地三个项目：Git 链接与配合方式

以下地址已对照三个本地仓库的 `origin` 核实。

| 项目 | Git 仓库链接 | 本地目录 | 核心职责 |
|---|---|---|---|
| WorldWarp | [HyoKong/WorldWarp](https://github.com/HyoKong/WorldWarp.git) | `WorldWarp/` | 按相机轨迹，利用几何渲染条件与历史帧生成新视角 RGB 视频；内部也自带局部 GS 拟合和渲染。 |
| MapAnything | [facebookresearch/map-anything](https://github.com/facebookresearch/map-anything.git) | `MapAnything/` | 从首图或生成历史恢复深度、相机与三维几何；当前桥接器使用预测深度，并保留输入的请求相机。 |
| GaME | [VladimirYugay/GaME](https://github.com/VladimirYugay/GaME.git) | `GaME/` | 接收带相机参数的 RGB-D 和掩码，构建、优化、保存及渲染高斯场景，提供地图后端能力。 |

三者的职责可以概括为：**MapAnything 恢复几何，GaME 维护高斯场景，WorldWarp 生成新画面。** 当前本地有两种实际接法，不能混成一条已经完成的持久闭环：

- **三项目串联实验：** GT 首图 → MapAnything 深度 → GaME 拟合固定 GS 场景 → 渲染 RGB / Alpha → WorldWarp 分段生成视频。已有实验复用同一个初始 GaME 场景，尚未将生成帧反馈给 GaME 扩图。
- **本文的滚动主线：** GT / 生成历史 → MapAnything → WorldWarp 自带的 GS 拟合与渲染 → WorldWarp 生成下一段 → 再选历史重建。这里不调用 GaME，而是逐段重建局部 GS 缓存。
- **进一步组合的目标：** 保留 WorldWarp 生成器，用 MapAnything 重建新内容，再写回同一个持久 GaME 地图，供下一轮渲染；跨轮地图状态、坐标对齐和可信更新仍需接通。

---

整理日期：2026-09-14。依据：当前目录源码、已有教室实验记录，以及最近三次关于整体流程、GS 监督和有效性掩码的问答。

本文按实际执行顺序重新组织，不是三次回答的简单拼接。主线采用 **MapAnything → WorldWarp 原生 GS → WorldWarp 视频生成** 的 `anchor_gs` 分支；WorldWarp 原版、`rolling_gs`、点云投影版和固定 GaME 版在后文分别说明。

本文描述当前实现，不将后续计划写成已完成功能；本轮只新增说明文档，没有修改算法、环境、权重或启动新的生成实验。

## 1. 一句话概括，以及最终得到什么

只有一张 GT 首图时，程序先预测深度、建立局部 GS，再沿目标相机轨迹渲染粗视频，让 WorldWarp 补全和修正画面；随后从生成视频选择历史图像，重新估计几何并拟合下一轮缓存，继续生成下一段。

```text
GT 首图 I₀ ＋ 相机轨迹 / 内参 ＋ 文字与生成配置
                         │
                         ▼
                MapAnything 预测几何
                         │
                         ▼
               RGB-D 反投影 → 三维点
                         │
                         ▼
              WorldWarp 原生 GS 拟合
                         │
                         ▼
        目标相机渲染 → 粗 RGB ＋ Alpha
                         │
       来源有效区域 ──────┤
                         ▼
           合并覆盖判断、生成有效性掩码
                         │
                         ▼
      历史上下文 ＋ 粗视频 → VAE → WorldWarp 去噪
                         │
                         ▼
                   VAE 解码 → 新视频段
                         │
                         ▼
           选取生成历史帧，再加入原始 GT
                         │
                         └────→ 下一轮 MapAnything / GS
```

当前教室案例的主要输出是四段拼接的 **480×608、30 fps、321 帧、10.7 秒 RGB 视频**，同时保存每段的几何输入、RGB-D、GS 参数、渲染条件、相机和报告。

需要先记住三点：

1. **循环单位是一段视频，不是一张视频帧。** 一段内部做视频潜变量去噪，段与段之间利用历史继续生成。
2. **WorldWarp 生成 RGB，MapAnything 再恢复几何。** 当前不是一个统一网络直接输出完整 RGB-D 世界。
3. **滚动 GS 是每段重新拟合的局部缓存。** 当前没有保留旧 GS 身份和优化器状态、跨轮原地续写同一份全局地图。

已有实验说明：[MapAnything＋WorldWarp 三个变体](WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/README.md)。

## 2. 整条管线究竟接受哪些输入

### 2.1 场景输入与控制输入

| 输入 | 当前例子 | 用途 |
|---|---|---|
| 一张 GT 首图 | `Data/classroom.png` | 提供初始视角下的真实外观 |
| 相机内参 K | 程序设置的虚拟内参 | 定义像素射线、反投影与渲染 |
| 相机轨迹 Cⱼ | 固定位置，逐步向左转 20° | 指定每个目标视频帧希望使用的视角 |
| 场景文字 | 教室内容及保持静态等描述 | 为视频生成提供语义条件 |
| 生成配置 | 4 段、strength 0.6、50 步采样、CFG 5、seed 32 | 控制生成规模和采样过程 |

用户不需要提供真实深度、点云、GS 或第二张 GT。深度由模型预测；后续图像来自生成器。

GT 的含义仅限初始 RGB：虚拟 K 不是已知的真实相机标定，预测深度不是测量真值，后续生成帧也不是新的真实观测。

### 2.2 当前实验入口额外依赖什么

[generate_worldwarp_mapanything.py](scripts/generate_worldwarp_mapanything.py) 是为四段对照实验写的入口，实际要求 `--variant` 和 `--baseline`，并转交 `--image`、`--output` 等生成参数。

`--baseline` 用来读取同一张图的预处理结果、请求相机轨迹和已经保存的逐段提示词，以保证对照一致。它没有给新分支提供未来目标帧的 GT，也没有将基线的未来 RGB 当成 GS 监督。新分支从第二轮开始使用的是自己已经生成的历史画面。

`--first-rgbd` 可选择复用首图的同一份几何预计算。现有 MapAnything 变体不加载 TTT3R 模型，也不调用 GaME；但会复用 WorldWarp 仓库中的 GS 优化代码。

### 2.3 本文符号

- `I₀`：预处理后的原始 GT 图片。
- `Vⱼ`：当前分支已经生成的视频中，全局帧号为 j 的图像；不等于 GT。
- `Cⱼ = [Rⱼ, oⱼ]`：请求轨迹中的 camera-to-world 位姿，R 为朝向，o 为相机中心。
- `Kⱼ`：配对的相机内参。
- `Dᵢ`：MapAnything 为某张来源图预测并恢复到原图网格的 z-depth。
- `Gₖ`：第 k 轮使用的局部 GS 缓存，k 从 0 开始。

帧号 j、生成段编号 k、扩散去噪步是三个不同的索引。当前教室轨迹主要表示相机在静态场景中的运动，不是独立查询动态世界的物理时刻。

## 3. 第一步：整理首图，建立初始相机和整条目标轨迹

执行入口：[generate_worldwarp_rotation.py](scripts/generate_worldwarp_rotation.py)，核心在 `main` 与 `constant_y_rotation`。

程序读取首图，处理 EXIF 方向、转 RGB，保持比例缩放并轻微中心裁切为 480×608，保存 `input_prepared.png`。

相机初始位姿为单位矩阵，之后始终位于同一个位置，绕 Y 轴匀速左转。当前轨迹共有 321 个相机，角度为：

```text
θⱼ = −20° × j / 320，j = 0…320

C₀   ： 0°
C₂₀  ：−1.25°
C₄₀  ：−2.50°
C₆₀  ：−3.75°
C₈₀  ：−5.00°
…
C₃₂₀ ：−20.00°
```

这些相机是“希望生成器遵循的控制轨迹”，不是从最终视频测量出来的实际相机真值。

程序还把首图重复成 `source_81f.mp4`，以适配 WorldWarp 的视频输入接口。这里仍只有一份真实图像信息；重复 81 次不会产生 81 个多视角观测。MapAnything 分支的首轮几何输入仍直接选择一张 `I₀`。

**本步输出：** `I₀`、完整 K / C 轨迹、提示词和运行配置。

## 4. 第二步：MapAnything 把来源 RGB 变成带相机的 RGB-D

执行模块：[mapanything_worldwarp_rgbd.py](scripts/mapanything_worldwarp_rgbd.py)。MapAnything 在自己的环境中运行，通过 NPZ 与 WorldWarp 进程交换数据。

### 4.1 首轮输入与后续输入

首轮输入只有：

```text
I₀ ＋ K₀ ＋ C₀
```

后续则输入本轮选出的原图 / 生成历史及其配对相机。具体选帧表见第 5 节。

本地桥接器把 RGB、内参、请求位姿作为条件传入模型，使用 `is_metric_scale=False` 和 `ignore_pose_scale_inputs=True`，避免把纯旋转的零平移当成真实尺度基线。

### 4.2 实际取哪些模型输出

MapAnything 可以提供多种几何输出；当前桥接器主要使用：

- `depth_z`：来源相机坐标系中的 z-depth。
- `mask`：模型有效区域。
- `conf`：置信度，保存下来供检查。

当前教室几何推理分辨率为 406×518，之后根据处理前后的 K，将深度和有效区域映射回 480×608。深度恢复使用有效性加权插值，避免把无效的零深度直接混入有效像素。

导出的 `posed_rgbd.npz` 包含：

| 字段 | 含义 |
|---|---|
| `rgb` | 本轮来源 RGB，N×H×W×3，uint8 |
| `depth_z` | 对应预测深度，N×H×W |
| `valid` | 对应几何有效区域，N×H×W |
| `confidence` | 恢复到同一网格的置信度 |
| `intrinsics` | 来源内参，N×3×3 |
| `c2w` | 来源位姿，N×4×4 |
| `frame_ids` | 来源图像的全局帧号 |
| `observed` | 是否来自原始 GT，而非生成历史 |

**下游使用的是输入的请求 K / C。** 模型预测的相机参数另存为诊断信息，不替换 GS 拟合所使用的相机。

当前关闭置信度百分位筛选和边缘筛选，仍保留模型 mask、有限值和正深度检查。虽然 `confidence` 已保存，但它没有进入当前 GS 拟合的逐像素损失权重。

**本步输出：** 带配对相机的 RGB-D 数据包。首轮它主要描述首图可见表面，不是已经补全了遮挡后或背面的完整世界。

## 5. 第三步：点云初始化 GS，再用来源图像和深度优化

调度模块：[worldwarp_map_geometry.py](scripts/worldwarp_map_geometry.py) 的 `render_geometry`。

实际 GS 实现：[ttt3r.py](WorldWarp/src/ttt3r/ttt3r.py) 的 `GS3DWarper._initialize_splats_from_depth`、`_train_splats`。文件名含 TTT3R，不代表这个分支执行了 TTT3R 模型。

### 5.1 RGB-D 如何变成高斯

对来源像素 p，先依据 z-depth、内参和 camera-to-world 位姿反投影：

```text
相机坐标点 Xcam = Dᵢ(p) × Kᵢ⁻¹ × p
世界坐标点 Xworld = Rᵢ × Xcam ＋ oᵢ
颜色 = 来源 RGB 在 p 处的颜色
```

程序每个来源最多随机采样 50,000 个初始点，把不同来源的点放到同一轮拟合中；当前桥接器还设置了 350,000 点总上限。

随后初始化高斯的位置、尺寸、方向、不透明度和球谐颜色参数，并进行优化。这个过程是针对当前场景的数值拟合，不是又调用一个“图片到 GS”的预训练生成网络。

初始化代码中的 `conf_threshold` 名称容易误解：这里实际执行的是 `depth > threshold`，是最小深度过滤，不是 MapAnything 的置信度阈值。

### 5.2 GS 究竟用哪些图像和相机监督

以下是当前 `anchor_gs` 的真实来源组织方式。每张来源图都配对自己的 `Dᵢ、Kᵢ、Cᵢ`。

| 拟合时机 | RGB 监督图像 | 配对相机 | 此次运行的 GS 数量 |
|---|---|---|---:|
| 第 1 段之前：G₀ | I₀ | C₀ | 50,000 |
| 第 2 段之前：G₁ | I₀、V₂₀、V₄₀、V₆₀、V₈₀ | C₀、C₂₀、C₄₀、C₆₀、C₈₀ | 250,000 |
| 第 3 段之前：G₂ | I₀、V₈₀、V₁₀₀、V₁₂₀、V₁₄₀、V₁₆₀ | 对应全局帧号的相机 | 300,000 |
| 第 4 段之前：G₃ | I₀、V₁₆₀、V₁₈₀、V₂₀₀、V₂₂₀、V₂₄₀ | 对应全局帧号的相机 | 300,000 |

数量来自已有运行报告，不能理解为所有图像和配置下固定产生相同数量的高斯。

因此，首轮完全是单视图拟合：500 次优化都围绕 `I₀、D₀、K₀、C₀`。后续才是原始 RGB 加生成历史 RGB 的多视图拟合。未来待生成的图像此时尚不存在，不参与监督。

相机参数直接来自 `traj['c2w'][frame_ids]` 和配对内参。设置 `optimize_poses=False`，所以优化中相机固定，只改变 GS 参数。如果生成图没有准确遵循请求相机，当前这一步不会通过联合相机优化自动消除该偏差。

### 5.3 500 次优化具体如何执行

500 次是**整份局部 GS 的总迭代数**，不是每张来源图各 500 次。每次随机选一个来源视图：

```text
选来源图 Iᵢ / Vᵢ 及其 Dᵢ、Kᵢ、Cᵢ
           ↓
在该来源相机下渲染当前 GS → RGB_render、Depth_render
           ↓
RGB_render 与来源 RGB 比较
Depth_render 与 MapAnything 预测深度比较
           ↓
反向传播，只更新高斯参数
```

默认损失为：

```text
L = 0.8 × RGB_L1
  ＋ 0.2 × (1 − SSIM)
  ＋ 0.01 × inverse_depth_L1
```

深度项在来源深度大于零的位置计算，比较的是逆深度；代码中叫 `depth_gt` 的变量，在本管线里实际上是 MapAnything 预测值，不是真实测量深度。当前 RGB 损失没有按 MapAnything confidence 加权。

anchor 版通过重复训练视图编号，把 GT 的采样权重设为 2，生成来源权重设为 1：第二轮 GT 被选中的概率为 2/6，第三、四轮为 2/7。首轮只有一张图，权重设为 1 即可。

这只是提高 GT 被采样的概率，不会给 GT 初始化两倍高斯，也不会冻结 GT 对应的高斯或保证每次迭代都同时监督 GT。

**本步输出：** 局部 GS 参数 `Gₖ`，保存为 `native_3dgs.pt`，可从指定相机渲染。

## 6. 第四步：渲染未来视角，并构造有效性掩码

### 6.1 先从 GS 渲染粗视频

用本轮 `Gₖ` 在下一段的每个目标相机下渲染，得到：

- 粗 RGB：已有几何投到目标视角后的外观。
- Alpha：高斯在目标像素上的累积覆盖 / 不透明度。

目标相机控制已经通过渲染条件进入后续生成：相机改变，粗图的布局与覆盖随之改变。这些 RGB 不是最终视频，仍可能有空洞、拉伸、模糊和错误表面。

### 6.2 为什么不能只看 Alpha

Alpha 判断“GS 是否在这里渲染出了不透明覆盖”，不判断“这个方向是否有来源图像支持”。高斯尺寸过大时，颜色和 Alpha 可能扩散到来源视野之外。

当前纯旋转分支另外计算来源图像的覆盖，再与 Alpha 合并。

### 6.3 纯旋转下，来源覆盖怎么得到

每张来源有有效区域 `Uᵢ`，来自第 4 节的模型 mask、有效深度和重采样检查。它不是连续置信度评分。

在静态场景、相机中心不变的条件下，来源像素到目标像素的旋转单应关系为：

```text
p_target ∼ Hᵢ→target × p_source
Hᵢ→target = K_target × R_targetᵀ × R_source × K_source⁻¹
```

这里 R 都是 camera-to-world 的旋转部分。同一条空间射线上的深度在投影中消去，因此该映射不需要预测深度数值。

[rotation_source_support](scripts/worldwarp_map_geometry.py) 的核心实现是：

```python
support = np.zeros((height, width), np.float32)
for source_pose, source_k, source_valid in sources:
    H = target_k @ target_R.T @ source_R @ np.linalg.inv(source_k)
    coverage = cv2.warpPerspective(
        source_valid.astype(np.float32), H, (width, height),
        flags=cv2.INTER_LINEAR,
    )
    support = np.maximum(support, coverage)
support = (support > 0.999).astype(np.float32)
```

这是说明逻辑的伪代码，函数的真实变量与参数以源码为准。

含义是：把每张来源的有效掩码投到目标画面，再取并集。至少一张来源能完整覆盖，该位置就有支持。`0.999` 用来保守排除双线性插值产生的有效 / 无效混合边界。

注意：这里投影的是掩码，**RGB 仍然来自 GS 渲染**。覆盖并集没有多视图一致性投票，也没有区分 GT 与生成图的权威性；生成历史同样可以扩大覆盖范围。GT 的训练采样权重 2 不作用于这个并集。

这个分支针对当前同中心、小角度的纯旋转场景。它不是通用遮挡求解器，不能直接把它当作任意平移、大角度或动态场景的完整可见性验证。

### 6.4 来源覆盖与 GS Alpha 如何合并

令二值来源覆盖为 S，GS Alpha 为 A，先得到：

```text
Q = A × S
```

`Q` 被保存为 `valid_alpha.npy`。它是合并后的覆盖量，不是原始 GS Alpha，也还不是最终的潜空间二值掩码。

WorldWarp 随后用 `mask_thres=0.5` 二值化：

```text
M = 1[Q ≥ 0.5]
```

| 来源覆盖 S | GS Alpha A | 二值结果 M |
|---|---:|---|
| 1 | 0.9 | 1：有来源支持，GS 也覆盖充分 |
| 1 | 0.2 | 0：来源包含过，但当前渲染不足 |
| 0 | 0.95 | 0：GS 虽不透明，来源却未覆盖 |

因此，条件是“来源支持 AND 足够的渲染覆盖”，不是“Alpha 越高越真实”。

### 6.5 相机有平移时走另一条分支

程序先检查来源与目标相机中心是否一致。不满足纯旋转条件时，GS 路径改用 `_compute_geometric_validity_mask`：

1. 从 GS 渲染目标相机的期望深度。
2. 反投影目标像素为三维点。
3. 将三维点投回各来源相机。
4. 检查投影在图内、在相机前方，并比较来源预测深度。
5. 相对深度误差小于 10%，且至少一个来源通过，才认为有几何支持。
6. 再与 GS Alpha 相乘。

这是当前代码的分支机制，不代表已经用这组教室纯旋转实验验证了平移重建质量。

**本步输出：** 下一段粗 RGB 序列、合并覆盖 Q、目标相机。来源支持仅表示有可用历史，并不验证生成内容真实或纹理清晰。

## 7. 第五步：把粗视频与掩码转成潜空间条件，再生成新段

执行模块：[pose_control.py](WorldWarp/pose_control.py) 的 `run_inference_chunk`、`sample_sequence` 和 `flow_matching_sample_step`。

### 7.1 两个条件进入 VAE / 采样器前如何处理

图像条件：把粗视频开头的上下文位置换成首图或上一段末尾的真实历史画面，然后用视频 VAE 编码为 `z_render`。这里“真实历史画面”是确实生成过的帧，不是新的真实拍摄 GT。

掩码条件：

```text
合并覆盖 Q
  → 0.5 阈值二值化
  → 时间上每隔 4 帧取样
  → 15×15 二值腐蚀
  → 空间缩小至 1/8
  → 布尔潜空间掩码 M_lat
```

对 480×608 图像，空间掩码为宽 60、高 76；81 帧对应 21 个时间采样位置，85 帧对应 22 个。

`15×15` 腐蚀要求周围区域全部有效才保留中心位置，使有效边界内退约 7 像素，小孔附近与很细的有效区域也可能被排除。意图是减少不可靠边界约束，但代价是部分仍有内容的像素会交给生成器重做。

时间掩码是按帧间隔抽取，不是对全部输入帧做完整的时序有效性聚合。

### 7.2 掩码真正控制的是加噪和去噪时间表

当前没有把浮点 confidence 作为一个额外图像通道接入网络，也不是最后根据掩码把两张 RGB 硬贴在一起。

采样初值可写为：

```text
z_start(p) = (1 − σ(p)) × z_render(p) ＋ σ(p) × noise(p)
```

- `M_lat=1`：从粗视频潜变量加部分噪声开始，保留几何与外观提示，同时允许修正。
- `M_lat=0`：使用最高噪声等级，更多依赖生成器补全。
- 上下文潜变量：另行设为零时间步，并在采样中保持，优先级独立于覆盖掩码。

“有效”不等于“冻结”：除上下文外，有效区域仍然会参与去噪，也可能被改写。“无效”也不一定是从没见过的区域，可能只是渲染覆盖不足或被腐蚀排除的边界。

当前 `strength=0.6` 会令 `minxs=0.4`；50 步调度中索引 20 的噪声等级被选为有效区域起点。实际 σ 从带 shift 的 scheduler 查表，不能直接解释成 60% 噪声。

逐步去噪时，有效区域前期保持在自己的部分加噪状态，随后参与去噪；无效区域从最高噪声开始推进。代码也把空间变化的 timestep 传给视频 Transformer，因此掩码既影响初始潜变量，也影响后续调度。

该机制对应 WorldWarp 的几何引导“补全与修正”设计，见 [WorldWarp 官方方法说明](https://hyokong.github.io/worldwarp-page/)。

### 7.3 模型到底收到哪些条件、输出什么

外部模块提供粗 RGB、有效性和上下文；进入视频 Transformer 的核心是加噪后的视频潜变量、对应的空间时间步和文字嵌入。目标相机主要通过几何渲染后的条件图体现，而不是这个调用直接把整组 4×4 相机矩阵作为一个额外输入传给 Transformer。

当前并没有为“GT 首图、首相机 GS 渲染、目标相机 GS 渲染”设置三个独立且长期保留的参考槽。首图 / 历史通过上下文进入，GT 在 anchor 分支还通过几何拟合间接影响后续粗图。

去噪完成后，VAE 解码输出一段 RGB 视频。深度没有由这一步同步导出为新的世界几何；下一轮还要由 MapAnything 重估。

上下文在潜空间保留不保证经 VAE 解码、量化和视频编码之后，输出像素与输入 GT 逐像素完全相同。

**本步输出：** 已补全的新视角 RGB 视频段。AR 发生在段与段之间；并非每生成一个 RGB 帧就即时更新一次 GS。

## 8. 第六步：选历史、更新缓存，继续下一段

### 8.1 两组“5 帧”不要混淆

以第一段交付全局第 0～80 帧后为例：

| 历史用途 | 取哪些图像 | 送给谁 |
|---|---|---|
| 几何重建 | anchor 版取 I₀、V₂₀、V₄₀、V₆₀、V₈₀ | MapAnything，再拟合下一份 GS |
| 视频衔接 | 上一段末尾连续 V₇₆～V₈₀ | WorldWarp，作为下一段上下文 |

稀疏来源负责提供跨视角几何与外观；连续末尾帧负责接续最近的画面和运动。它们不是同一批帧。

代码为长度适配复制的前缀，不会被当成新的几何来源或伪造的末尾历史。后续 MapAnything 使用本分支刚刚生成的视频，而非另一个对照分支的未来图像。

### 8.2 新内容究竟怎样进入下一轮

第一段生成了首图之外的左侧区域，这些新区域出现在被选中的历史 RGB 里。随后：

```text
新区域的生成 RGB
  → MapAnything 预测深度
  → 反投影得到对应三维点
  → 与本轮其他来源共同拟合 G₁
  → G₁ 可以为下一段提供该区域的渲染条件
```

因此存在真实的“生成 → 几何 → 再生成”反馈。

但当前 `G₁` 是重新初始化和拟合的局部 GS，不是加载 `G₀` 后继续更新。同一轮不同来源的点共同拟合，不等于跨轮旧新地图的持久增量融合。原始内容通过 GT 和历史图像重放，而非旧高斯参数直接继承。

### 8.3 四段如何拼成 321 帧

当前 5 帧上下文配置由 [context_window](scripts/generate_worldwarp_hybrid_context.py) 组织：

| 段 | 内部目标全局帧号 | 历史上下文 | 裁前缀后保存的段 | 最终新增到成片 |
|---|---|---|---|---|
| 第 1 段 | 0～80，共 81 帧 | 首图，1 帧 | 0～80 | 0～80，共 81 帧 |
| 第 2 段 | 76～160，共 85 帧 | 76～80，5 帧 | 80～160 | 81～160，共 80 帧 |
| 第 3 段 | 156～240，共 85 帧 | 156～160，5 帧 | 160～240 | 161～240，共 80 帧 |
| 第 4 段 | 236～320，共 85 帧 | 236～240，5 帧 | 240～320 | 241～320，共 80 帧 |

后三段先在编码前裁去额外的 4 帧上下文前缀，最终拼接再各去掉 1 帧重叠：

```text
81 ＋ 80 ＋ 80 ＋ 80 = 321 帧
321 / 30 fps = 10.7 秒
```

这里没有靠重复帧或插帧延长成片，也没有增加新的 GT 输入。

### 8.4 最后一个 GS 为什么不是整个视频的最终场景

`G₃` 是生成第 4 段之前拟合的缓存，其来源只到第 240 帧。第 241～320 帧新产生的内容，要再执行一轮几何处理才会进入后续资产。

因此，四段视频全部生成完，并不自动意味着已导出覆盖全部生成区域的一份最终 GS。额外对成片做几何诊断，也不等于这些诊断结果已经反馈进原生成过程。

## 9. 当前目录中几个分支的区别

| 分支 | 几何前端 | 渲染 / 场景模块 | 生成历史是否更新几何 | 是否持续续写同一 GS |
|---|---|---|---|---|
| WorldWarp 原版 | TTT3R / CUT3R | WorldWarp 原生 GS | 是，后续段处理生成历史 | 否，所查调用链逐段重建 |
| `rolling_gs` | MapAnything | WorldWarp 原生 GS | 是，上一段均匀 5 帧 | 否 |
| `anchor_gs`，本文主线 | MapAnything | WorldWarp 原生 GS | 是，再保留原始 GT | 否 |
| `anchor_points` | MapAnything | 点云投影，无 GS 拟合 | 是，再保留原始 GT | 不适用 |
| 固定 GaME 串联版 | MapAnything 首图深度 | 首图建立的固定 GaME 场景 | 当前视频实验没有几何回写 | 复用固定场景，但不增量更新 |

### 9.1 原版并不等于本文选帧逻辑

原版先用 TTT3R 处理视频历史，再用 `source_ids` 对应的来源帧初始化和优化局部 GS。当前原版单帧上下文基线在后续段使用末尾来源帧建 GS，不能把本文 MapAnything 分支的“均匀 5 帧”套到原版上。

其相机处理也不同：原版后续段会用估计的历史相机组织局部来源几何；本文分支固定采用提供给 MapAnything 的请求 K / C。两者的几何前端替换不只是更换模型名字。

### 9.2 点云投影版跳过什么

`anchor_points` 跳过 GS 初始化和 500 步优化。它从 RGB-D 反投影点云，做双线性前向投影、逐来源 z-buffer 和来源间加权颜色融合；覆盖量再与旋转来源支持相乘。

这里的 coverage 是投影累计覆盖，不是高斯 Alpha；逐来源深度缓冲后的跨来源颜色融合，也不等于持久全局点云融合。

### 9.3 GaME 版实际怎样接

```text
I₀ → MapAnything 深度 → GaME 拟合固定场景 G₀
                                │
                                ├→ 渲染第 1 段条件 → WorldWarp
                                ├→ 渲染第 2 段条件 → WorldWarp
                                └→ 后续仍渲染这同一份 G₀
```

WorldWarp 仍然使用前一段末尾图像作视频上下文，但已有实验没有将新视频送回 GaME 增补场景。它验证了 GaME 的真实渲染可以替换 WorldWarp 几何条件，不是已完成的三项目持久闭环。

GaME 输入还需要匹配的 RGB-D、K 和位姿。本地适配显式将共享的 OpenCV c2w 求逆为 GaME 实际使用的 w2c，并使用相机适配器处理完整 K。该实验使用静态掩码，不是自动动态分割。

参见 [固定 GaME 串联实验](WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07/README.md) 和 [5 帧上下文对照](WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/README.md)。

## 10. 最终产物分别是什么，有什么用

以已有 [anchor_gs 实验报告](WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/anchor_gs/pipeline_report.json) 所在目录为例：

```text
anchor_gs/
├── input_prepared.png                  初始图像
├── requested_camera_trajectory.npz     完整请求相机与内参
├── classroom_pan_left_4chunks_10.7s.mp4 最终 RGB 视频
├── report.json                        帧数、时间、配置等生成记录
├── pipeline_report.json               实际经过的模块、来源和更新方式
├── geometry_bridge_calls.json         每段注入条件的具体记录
├── geometry/
│   ├── chunk_000/
│   ├── chunk_001/
│   ├── chunk_002/
│   └── chunk_003/
└── artifacts/                         分段视频、提示词、噪声调度等
```

每个 `geometry/chunk_*` 中，主要文件为：

| 文件 | 作用 |
|---|---|
| `source_*_global_*.png` | 实际用于这一轮几何估计的来源图 |
| `mapanything_input.npz` | 来源 RGB、全局帧号、GT 标记、输入 K / C |
| `posed_rgbd.npz` | 当前轮 RGB-D、有效区域、置信度与相机 |
| `posed_rgbd.json` | MapAnything 处理参数、预测相机诊断等 |
| `native_3dgs.pt` | 这一轮拟合得到的 GS 参数，仅 GS 分支有 |
| `warped_rgb.npy` | 目标相机下的粗 RGB 序列 |
| `valid_alpha.npy` | 渲染覆盖乘来源支持后的 Q，尚未腐蚀和潜空间转换 |
| `target_cameras.npz` | 这一轮渲染条件所用的目标 K / C |
| `render_report.json` | 来源、权重、高斯数量、覆盖率与拟合设置 |

这些分别是图像、几何资产、生成条件和溯源记录，不能全部统称为一个“持久世界 checkpoint”。当前 `native_3dgs.pt` 保存局部参数，不代表下一段会恢复并继续训练它。

本地还存在更细粒度的 [中间过程归档说明](WorldWarp_outputs/classroom_intermediates_2026-09-14/README.md)。其中用于成片之后诊断的 MapAnything 全帧推理，应与真正参与生成的来源几何区分；本文不依赖该归档是否已经全部完成来判断主流程。

## 11. 对应类 Atlas 架构：哪些已有，哪些不是当前功能

| 架构中的功能 | 当前对应实现 |
|---|---|
| 单图初始化局部世界 | MapAnything 深度＋点云反投影＋GS 拟合 |
| 已有世界渲染目标视角 | 原生 GS 渲染或点云投影；固定 GaME 版由 GaME 渲染 |
| 根据粗图补全新区域 | WorldWarp 的视频潜空间扩散 / flow |
| 使用历史保持连续 | 稀疏几何来源、连续视频上下文；anchor 版保留 GT |
| 新内容进入下一轮空间约束 | 滚动分支从生成 RGB 重估几何、重拟合下一份缓存 |
| 同一全局 GS 的持续增补与纠错 | 本文这些视频实验还没有接成 |
| 统一模型原生生成 RGB-D | 当前由 RGB 生成器和外部几何模型分担 |
| 独立世界时间控制 / 连续 4D 表示 | 当前静态教室空间探索管线没有实现 |

原系统综合假设仍可参见 [系统架构图 v2](diagrams/atlas_architecture_synthesis_v2.svg)。本文是在说明本地如何实现其中一部分功能，不将开源组装等同于 Atlas 官方内部结构。

## 12. 源码定位速查

文档内的本地链接均相对于本目录，打开源码后可按下面的函数名定位。

| 想核对的问题 | 文件 / 函数 |
|---|---|
| 首图、尺寸、轨迹、321 帧如何建立 | [generate_worldwarp_rotation.py](scripts/generate_worldwarp_rotation.py)：`main`、`constant_y_rotation` |
| 哪些参数和基线文件进入 MapAnything 变体 | [generate_worldwarp_mapanything.py](scripts/generate_worldwarp_mapanything.py)：`main`、`MapGenerator.geometry_warp` |
| 几何每段选哪几帧 | [worldwarp_map_geometry.py](scripts/worldwarp_map_geometry.py)：`select_history` |
| 模型输入、深度恢复与相机保留 | [mapanything_worldwarp_rgbd.py](scripts/mapanything_worldwarp_rgbd.py)：`main` |
| GS 初始化、采样权重与目标视角渲染 | [worldwarp_map_geometry.py](scripts/worldwarp_map_geometry.py)：`render_geometry` |
| GS 使用的 RGB / 深度损失 | [ttt3r.py](WorldWarp/src/ttt3r/ttt3r.py)：`GS3DWarper._train_splats` |
| 纯旋转来源覆盖 | [worldwarp_map_geometry.py](scripts/worldwarp_map_geometry.py)：`rotation_source_support` |
| 非纯旋转深度一致性 | [ttt3r.py](WorldWarp/src/ttt3r/ttt3r.py)：`_compute_geometric_validity_mask` |
| 掩码腐蚀、VAE 编码与解码 | [pose_control.py](WorldWarp/pose_control.py)：`erode_mask`、`run_inference_chunk` |
| 有效性如何影响噪声与时间步 | [pose_control.py](WorldWarp/pose_control.py)：`sample_sequence`、`flow_matching_sample_step` |
| 5 帧上下文与 85 帧内部窗口 | [generate_worldwarp_hybrid_context.py](scripts/generate_worldwarp_hybrid_context.py)：`context_window` |
| 固定 GaME 渲染如何注入 | [generate_worldwarp_hybrid.py](scripts/generate_worldwarp_hybrid.py)：`GuidedGenerator.geometry_warp` |
| GaME 静态 RGB-D 建图与相机转换 | [fuse_geometry_game.py](scripts/fuse_geometry_game.py)、[game_camera_adapter.py](scripts/game_camera_adapter.py) |

## 13. 最后的完整概括

给定一张 GT 首图，当前主线先建立虚拟相机和运动轨迹，用 MapAnything 预测深度，再把 RGB-D 反投影成点云并拟合局部 GS。GS 用来源图像的 RGB 和预测深度监督，相机固定为请求轨迹中的对应位姿。拟合完成后渲染下一段粗视频，用来源覆盖与渲染 Alpha 共同生成有效性掩码，再经过腐蚀和潜空间转换，控制 WorldWarp 哪些区域保留更多粗图条件、哪些区域进行更多生成。

WorldWarp 结合首图 / 末尾上下文和文字，在视频潜空间生成下一段 RGB。程序再从自己生成的历史里选择稀疏图像，anchor 版额外保留原始 GT，重新预测几何和拟合下一轮 GS，继续相同过程。

**它已经是一个“单图起步、相机受控、几何引导、历史反馈”的空间探索原型；核心记忆仍主要通过图像历史重放和局部 GS 重建传递，尚不是一份被连续读写、永久融合所有生成内容的全局高斯世界。**
