# Atlas 架构二次校准

校准日期：2026-09-06。范围：本目录旧调研、两张旧 SVG、WorldWarp 当前代码与已有产物，以及 World Labs 官方说明和关键项目的官方仓库。本文校正旧结论，不覆盖历史记录；没有运行新的 GPU 推理、训练或多片段质量测试。

## 结论

上一版的**功能划分基本可用，但对实现边界和可插拔程度判断偏乐观**。需要把三件事分开：

1. **Atlas 本体**：官方披露的统一多模态自回归扩散模型。
2. **复现系统**：用多个模型、显式几何和工程记忆拼出相近功能；不是 Atlas 内部实现的还原。
3. **可复用项目**：有的提供工具 API，有的是必须整套替换的模型，有的仅适合借鉴机制。

因此，不再把“RayMap3R + WorldWarp cache + DepthDirector + ReSplat”写成已经具备明确兼容性的推荐组合。新的优先级是：先建立正确的状态和相机接口，再做单变量替换实验。

新版图：

- [Atlas 官方架构与工程边界](../../../diagrams/atlas_architecture_calibrated.svg)
- [开源替代路线与部件映射](../../../diagrams/atlas_open_source_map_calibrated.svg)

两图中的 F / R / E 编号表示同一功能，但不再强迫所有项目使用相同的串行拓扑。

## 1. Atlas：哪些判断保留，哪些必须降级

官方明确的骨架是：输入被空间锚定后形成共同上下文；同一个从零预训练的多模态 Transformer 自回归地产生序列元素，连续输出使用 latent rectified flow。它原生处理文本、图像、相机和深度，视频是图像序列。新视角、几何、全景、动态重构和机器人 RGB-D 观测属于不同的任务使用方式。显式 3D 路径包含几何／点云到 Gaussian splats 的转换。[World Labs：Atlas](https://www.worldlabs.ai/blog/atlas)

据此，旧图需要这些校正：

| 旧图容易造成的理解 | 校准后的表达 |
|---|---|
| 编码器、空间上下文、AR、扩散是几套可独立替换的已知网络 | 它们首先是统一模型的功能抽象；模块边界、token 格式和共享参数细节未公开 |
| 自回归视频生成后再接一个空间输出模型 | AR 是序列维度，flow 是当前连续元素的采样过程；二者嵌套，不是前后两个产品 |
| 生成循环必然维护一份持久 GS，再把它渲染回模型 | “上下文管理”不等于已证实的 GS 内循环；长期关键帧库、检索、地图融合属于复现建议 |
| 全景主要是模型的外部初始化输入 | 全景也应画为模型的直接输出能力；开源系统中的先全景后扩展只是其中一种路线 |
| 所有传感器图像都必须经 GS 渲染器产生 | 原生 RGB-D 观测生成与显式资产渲染应区分，不应漏掉模型直接产生观测的分支 |
| 动态重构、时间插值、受动作影响的物理模拟是一回事 | 三者应分开验收；表示运动不自动提供接触、摩擦或反事实动作响应 |

上表关于“不能据此确认内部细节”的结论是本次证据边界判断，不是官方否认这些实现。工程上可以用射线编码、关键帧检索、显式 GS 或外部求解器实现，但不能标成 Atlas 已公开采用的方案。

另有两个评测边界：官方相机比较中，Atlas 得到数值相机输入，其他视频模型主要得到文字运动指令；点图重建比较提供输入位姿。因此，不能进一步外推成“所有相机原生模型都已被同条件击败”或“无位姿 SLAM、回环定位已经验证”。[官方评测说明](https://www.worldlabs.ai/blog/atlas)

机器人方面，World Labs 的 R2S2R 说明明确讨论按任务组合不同表示和建模方法，并通过真实／模拟的匹配动作检验对象响应。合理结论是“系统需要视觉与动力学共同对齐”，不是“Atlas 一个网络已公开替代全部物理求解器”，也不是“已确认使用某个开源引擎”。[World Labs：R2S2R](https://www.worldlabs.ai/blog/real-to-sim-to-real)

## 2. 最重要的本地代码校准：WorldWarp 不是现成全局地图系统

本地基准提交为 `0396b801c278546d01a6618a18e5a5c2a154c0a1`，保留既有 `gradio_demo.py`、`pose_control.py` 两处修改。以下结论针对**当前实际调用链**，不否认论文思想或仓库其他辅助函数。

### 2.1 当前真正执行的链路

`当前输入片段 → TTT3R 深度/位姿 → 从选定源帧初始化 GS → 优化 → 目标视角 RGB/有效性 mask → Wan 采样 → 下一片段`

证据：

- [pose_control.py:1249](../../../WorldWarp/pose_control.py:1249)：`run_inference_chunk` 读取 `input_video_path`，调用 `batch_warp_frames_via_3dgs`，随后将 warped RGB 编码成 latent，并使用 mask 采样。
- [ttt3r.py:1513](../../../WorldWarp/src/ttt3r/ttt3r.py:1513)：每次 `warp_with_validity_mask` 都运行几何估计，随后新建 splats、ParameterDict、优化器并训练。返回 RGB、mask、校正位姿，而不是把更新后的全局 GS 作为跨片段状态返回。
- [ttt3r.py:2097](../../../WorldWarp/src/ttt3r/ttt3r.py:2097)：`outputs, _ = ...` 没有把这次重建的 recurrent state 从此接口传给下次调用。
- [pose_control.py:1249](../../../WorldWarp/pose_control.py:1249) 的 `combined_video_path`、`cache_all` 形参在该函数体没有被消费；GUI 虽然传入拼接视频路径，也不能据此认定它被用于全历史重建。

所以应改称“**可运行的逐片段几何条件视频生成基线**”。片段接续和保存 PLY 不等于持续增长的统一世界地图，更不等于历史视角重访和全局回环已经解决。

### 2.2 原来把 mask / conf 说得过强

[ttt3r.py:84](../../../WorldWarp/src/ttt3r/ttt3r.py:84) 中 `confidence_threshold` 的实际筛选是 `depth_map > confidence_threshold`；[初始化函数](../../../WorldWarp/src/ttt3r/ttt3r.py:593) 的 `conf_threshold` 文档也描述最小深度，而不是预测置信度。

渲染 mask 来自 alpha 和源深度的重投影有效性；这是有用的几何支持信号，但不是已经校准的重建置信度，更不等于“动态物体已过滤”。旧文“每次只更新高置信静态区域”应改为**拟新增能力**。

### 2.3 本次实际验证了什么

重新读取现有文件得到：

- MP4：H.264，720×480，30 fps，81 帧，2.7 秒。
- PLY 文件头：50,000 个 Gaussian 顶点。
- 历史部署记录包含一次端到端验收；本次没有重跑。

这支持单片段流水线可运行，不支持多 chunk 漂移、回访一致性、持续地图质量或“任意长世界探索”的量化结论。上一版部署记录本身已经声明缺少系统 benchmark；架构选型部分不应越过这个边界。

## 3. 部件选型重新校准

### 3.1 四个必须改变的接口判断

**DepthDirector：独立的视频重渲染路线，不是换掉 WorldWarp 一个 tensor。**  
发布配置的 `extra_inputs` 是 `input_image,depth_cond,concat_video`，使用 Wan2.2 5B 相关模型配置。它需要源视频内容条件和目标视角深度；不是仅有任意首帧与 GS depth 就等价于训练分布。当前 WorldWarp 则是 Wan2.1 分支的 RGB warp / latent mask 控制。替换会涉及主模型、条件编码、时序对齐、深度规范和有效区域处理。当前证据也不足以把 visibility 描述成 DepthDirector 一个独立、现成的学习条件通道。[发布配置](https://github.com/FREDZEL2020/DepthDirector/blob/main/configs/depthdirector.yaml)、[数据处理工具](https://github.com/FREDZEL2020/DepthDirector/blob/main/tools/recam/README.md)

建议先使用真实源视频跑通官方重渲染样例，再测试用 GS 渲染深度代替其深度预处理结果。单图启动和长历史视频条件需要单独设计，不在首轮实验中假定成立。

**ReSplat：自带初始化与循环状态，不是任意 GS 的通用优化插件。**  
其 `forward(context, ..., renderer)` 从图像、相机和深度预测开始，内部产生 Gaussians 与特征状态，再利用渲染误差循环更新。公开入口没有接收外部 WorldWarp GS 的通用参数。渲染误差反馈机制仍值得借鉴，但移植到持续地图需要点关联、隐藏特征初始化和训练分布适配；F4Splat 也不自动提供这些适配。[ReSplat encoder](https://github.com/cvg/resplat/blob/main/src/model/encoder/encoder_resplat.py#L314)

**RayMap3R：保留几何前端候选，但不再承诺“直接得到全局 SLAM”。**  
复用 CUT3R 权重、双分支静态性门控、状态重置前后 Sim(3) 对齐均有依据。重置对齐不能直接改称完整的历史重定位、地点识别和位姿图回环。接入仍需保留跨帧状态、暴露所需输出并统一坐标和尺度；“同一 checkpoint”不代表“同一函数签名”。[RayMap3R 官方说明](https://github.com/Brack-Wang/raymap3r)

**NoPo4D：适合先做同步、固定机位的短片段原型。**  
编码器默认 `average_poses=True`，按相机把时间维位姿编码平均，注释明确用于约束静态相机。关闭开关不代表任意手持多机的精度已经验证。另外有接口文档不一致：README 的渲染外参写 c2w，模型 wrapper 的 docstring 写 w2c；decoder 实际把外参取逆后传给 gsplat。内参文档写 normalized，但该 decoder 直接传入 K，没有可见的像素换算。接入前必须做已知相机的投影和往返渲染单测，不能盲抄示例说明。[编码器](https://github.com/bralani/NoPo4D/blob/main/src/model/encoder/encoder.py#L73)、[wrapper](https://github.com/bralani/NoPo4D/blob/main/src/model/nopo4d.py)、[decoder](https://github.com/bralani/NoPo4D/blob/main/src/model/decoder/decoder_4dgs.py#L89)

### 3.2 修订后的功能对应表

“公开”只表示存在代码／模型发布路径；除 WorldWarp 历史单片段外，下列项目没有在本目录完成新一轮运行验收。

| 图中功能 | 候选项目 | 可拿来用的功能 | 关键限制／接入方式 |
|---|---|---|---|
| F1 全景初始化 | [HY-Pano 2.0](https://github.com/Tencent-Hunyuan/HY-World-2.0/tree/main/hyworld2/panogen) | 文本／图像到全景 | HY 系统入口；不是 Atlas 必经步骤 |
| F2 几何前端 | [RayMap3R](https://github.com/Brack-Wang/raymap3r)、[Pi3X](https://github.com/yyfz/Pi3)、[ViPE](https://github.com/nv-tlabs/vipe) | 分别对应流式动态抑制、条件化重建、视频几何预处理 | 可选前端，不必全部串联；Pi3X 权重非商用 |
| F3/F5 生成基础 | [Wan2.2](https://github.com/Wan-Video/Wan2.2) | VAE、DiT、视频先验与训练基础 | 不自动具备 Atlas 多模态序列协议和空间上下文 |
| F2/F4/F5 相机生成 | [SCoPE](https://github.com/TencentARC/SCoPE)、[SEVA](https://github.com/Stability-AI/stable-virtual-camera) | 数值相机条件生成／少视图 NVS | 各自整套模型；并非插在任意 DiT 后的后处理；SEVA 有非商用约束 |
| F5 源视频重渲染 | [DepthDirector](https://github.com/FREDZEL2020/DepthDirector) | 内容视频与目标深度条件的新轨迹视频 | 独立实验；先遵守其源视频输入契约 |
| E1 历史上下文参考 | [WorldMem](https://github.com/xizaoqu/WorldMem)、[HY 全景记忆库](https://github.com/Tencent-Hunyuan/HY-World-2.0/tree/main/hyworld2/worldgen) | 记忆组织与检索机制参考 | 不是通用 memory SDK；与空间模型绑定的部分需重新适配 |
| R2 显式 3D | [F4Splat](https://github.com/mlvlab/F4Splat)、[ReSplat](https://github.com/cvg/resplat) | 少视图 GS 预测／带内部反馈的 GS 重建 | 作为独立重建器比较；不直接互接外部 GS 状态 |
| R2 渲染与交付 | [gsplat](https://github.com/nerfstudio-project/gsplat)、[Spark](https://github.com/sparkjsdev/spark)、[spz](https://github.com/nianticlabs/spz) | 可微渲染、浏览器查看、压缩格式 | 工具层最容易复用；仍要校验 SH、旋转、尺度和坐标格式 |
| R3 动态重构 | [NoPo4D](https://github.com/bralani/NoPo4D)、[ClipGStream](https://github.com/liangjie1999/ClipGStream) | 前馈动态 GS／按片段优化长序列 | 同步与标定／位姿处理；不是从单图预测可交互未来 |
| R3 动态对应 | [Track4World](https://github.com/TencentARC/Track4World) | 世界坐标的稠密跟踪／运动信息 | 辅助动态关联；不是 GS 渲染器或物理引擎 |
| R4/E2 仿真 | [MuJoCo](https://github.com/google-deepmind/mujoco)、[Genesis](https://github.com/Genesis-Embodied-AI/genesis-world) | 物理状态更新与机器人仿真 | 需碰撞几何、关节、质量、摩擦和系统辨识；不等价替代 Atlas 原生观测模型 |
| E3 合成数据 | [BlenderProc](https://github.com/DLR-RM/BlenderProc)、[ViPE](https://github.com/nv-tlabs/vipe) | 合成 RGB-D／相机真值、真实视频几何标注 | 我们可用的数据工具；不是 Atlas 训练数据来源的证据 |

F4Splat 的 demo 输入数量范围不是通用融合保证；应按具体 checkpoint 的上下文规模、相机输入与分辨率做验证。[F4Splat 发布说明](https://github.com/mlvlab/F4Splat)

### 3.3 整套路线必须并列，不放在生成器后面

- **WorldWarp**：保留本地运行基线；优先检查跨片段状态与回访，不急着换生成模型。
- **HY-World 2.0**：完整静态世界工程对照。全景、轨迹规划、扩展生成、组合重建和 GS 优化都有独立阶段。其 WorldGen 文档建议至少 4 GPU，并要求 VLM 服务；不是轻量单卡默认替换。[WorldGen 说明](https://github.com/Tencent-Hunyuan/HY-World-2.0/blob/main/hyworld2/worldgen/README.md)
- **PixWorld**：更接近“生成／重建统一”的研究对照，整套像素空间扩散模型直接关联 GS。公开 5B 权重由 Wan2.2 转换，不能套用论文从零训练版本的指标。[PixWorld](https://github.com/SensenGao/PixWorld)
- **SpatialGen**：布局条件的室内场景路线，依赖 3D semantic layout，不能作为任意视频模型的通用几何输出头。训练代码可见不代表完整训练数据已经无条件公开。[SpatialGen](https://github.com/manycore-research/SpatialGen)

旧表中 ABot-Recon、ABot-World、YoNoSplat、ZipSplat、LGTM、CameraNoise 等作为候选池保留，本次没有重新跑其实现或逐项完成同深度代码审计，因此不把旧描述自动升级为已验收结论。ABot-3DWorld 的可运行性也不应只根据项目名称或论文相似性承诺；新版图不以其为交付依赖。

### 3.4 许可证要按代码、权重、依赖分别记录

公开 GitHub 不等于可自由再分发的完整产品。当前本地 WorldWarp 根目录未见 LICENSE，PixWorld 根目录也未见明确 LICENSE；应标“授权待确认”。DepthDirector 的 Apache-2.0 代码不消除默认几何预处理所用 [Pi3X 非商用权重](https://huggingface.co/yyfz233/Pi3X) 的约束。RayMap3R 的 MIT 文本也要求尊重上游代码／权重许可。NoPo4D 的根 MIT 不能替代其 DA3 backbone／模型资产核查。[RayMap3R LICENSE](https://github.com/Brack-Wang/raymap3r/blob/main/LICENSE)、[NoPo4D 依赖说明](https://github.com/bralani/NoPo4D)

这是本次发布材料的边界提示，不是对所有权重和下游使用情形完成的法律审查。HY、SEVA、SpatialGen 等应以选定版本各自条款为准。

## 4. 改进方案：先补系统契约，再换模型

以下是本次提出的工程方案，尚未实施。

### P0：记录真实状态与建立测试

1. 保存每个 chunk 的原始观测、生成帧、相机、世界尺度变换、重建配置、随机种子和来源标记。
2. 定义统一边界数据：RGB + K_px + T_c2w(OpenCV) + depth_z + valid + confidence + staticness + timestamp + provenance。valid / confidence / staticness 不要共用一个字段。
3. 显式区分三个索引：世界时间 t、序列元素 j、去噪时间 s。NoPo4D 的 [0,1] 时间需要由真实时间转换，不能用扩散步数替代。
4. 建立“静态场景向左移动→返回原位”的多片段测试，另测旋转、遮挡再显露和动态前景。单独记录几何误差、重投影误差、回访外观一致性、显存与延迟。

### P1：先做真正的持久地图与观测记忆

- 将 GS／关键帧状态提升到 session 级，避免仅保存文件而下一次重新初始化。
- 新帧先形成候选几何，用真实观测、交叉视角支持、遮挡关系和静态性验证后再提交；无法确认的新区域保留为“生成假设”，不要伪装成测量真值。
- 持久地图与 Transformer 的上下文 cache 分开管理。给定新目标相机时检索有用历史视图，不是把整段拼接视频无选择塞回模型。
- 位姿改变或 Sim(3) 对齐时同步更新地图与相机；局部静态门控不能替代全局位姿纠错。

### P2：一次只替换一个维度

- 固定 WorldWarp 生成端，先比较 TTT3R 与 RayMap3R 的静态前景抗干扰表现。
- 固定输入图像／相机，用 F4Splat、ReSplat 作为独立重建基线，先比输出资产，不先强行拼内部隐藏状态。
- 将 DepthDirector 放在独立的真实源视频重渲染实验；SEVA／SCoPE 放在相机条件生成实验。分别量化后再决定是否迁入主链。

### P3：动态与物理独立验收

先用同步固定机位短片验收 NoPo4D，再做 ClipGStream 的长序列优化对照；改视角与改时间分别测试。需要“换一个动作会怎样”时，再构建物理状态、资产和参数标定，验证接触结果，而不是只看 4D 视频是否顺滑。

## 5. 本次产物与保留范围

新增两张原生 SVG 和本报告。SVG 的框线与文字可编辑、缩放不失真；项目名称含可点击链接。两图已通过 XML 解析、全部文字宽度检查和 CairoSVG 渲染预览，均不包含嵌入位图。旧调研、旧 SVG、WorldWarp 代码、本地模型、环境和输出均保留。

本次采用的是“官方资料 + 实际调用代码 + 已有产物”的校准。它提高了结论的可追溯性，但不替代尚未进行的跨项目接入实验和长期质量 benchmark。
