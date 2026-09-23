# Atlas 架构第三版：整体复核与更新说明

日期：2026-09-06。审阅对象为第二版两张 SVG、二次校准报告、本地 WorldWarp 调用链、已安装 gsplat 源码，以及官方项目资料。**本次是架构／接口审查与静态校验，不是新一轮 GPU 模型复现。**前两版文件均保留。

## 总结

第二版对 Atlas“统一多模态自回归扩散模型”、整套模型与工具组件的区分仍然成立。没有理由推翻这些结论；第三版主要纠正**图的因果方向、可调用接口和数据语义**，不是为了升级版本而换一批项目。

第三版产物：

- [Atlas 功能架构与证据边界](../../../diagrams/atlas_architecture_v3.svg)
- [公开项目映射与可实现的工程架构](../../../diagrams/atlas_open_source_map_v3.svg)

## 一、第二版仍需更新的地方

| 项目 | 第二版不足 | 第三版处理 |
|---|---|---|
| 任务与输出的连线 | 连续输出后接“相机生成／机器人观测”等任务框，容易被理解为先出结果，再运行这些任务 | 任务协议独立展示；正文图只保留输入 → 统一模型 → 请求结果 → 可选资产转换 |
| 深度编码 | “视觉／深度的 latent 表示”可能暗示已知二者的 codec 结构 | 保留模型级 latent diffusion；RGB／depth 的具体编码器、是否共用 VAE、输出头形式均列为未知 |
| “记忆”的含义 | 虽已提醒地图与上下文不同，但图上仍容易合并理解 | 区分原始观测库、模型计算缓存、显式几何状态；三者用途与生命周期不同 |
| WorldWarp 在新闭环中的位置 | “gsplat → WorldWarp，沿用当前生成接口”不够准确 | 明确需从当前入口抽取 VAE／采样／解码 adapter，不能直接调用会重新建图的端到端入口 |
| 生成结果的验证 | “新观测校验后写回地图”容易将生成帧误称新真实观测 | 用“生成候选”；生成内容可写假设层，但不能仅凭自洽自动升级为真实测量 |
| depth 契约 | 单写 depth_z 仍不足以消除差异 | 区分 z-depth、ray distance、累计 D、期望 ED；记录 alpha、单位、尺度来源及无效区域 |
| NoPo4D 的相机接口 | 只指出 README 与 docstring 不一致 | 沿官方入口追到 encoder、decoder，给出当前渲染路径的明确契约与证据 |
| 场景坐标变换 | 仅提 Sim(3) 与尺度对齐，不够落实到状态更新 | 图示加入 world-frame / map-version；相机、点、Gaussian 位置和协方差应同步变换 |
| 验证等级 | 渲染检查容易被看成“架构已经实现” | 明示本次只做源码核对、示例契约测试与 SVG 检查，不宣称模型效果或跨库集成已通过 |

## 二、Atlas 本体：保留的最小事实与未知边界

官方披露的是从零预训练的多模态自回归扩散 Transformer；相机对图像／深度进行空间锚定，先前序列元素形成生成条件。模型级方法包含 latent diffusion 与 rectified flow。图像／全景、新视角、几何、视频重构和机器人 RGB-D 属于不同任务使用方式。点云到 GS 的资产输出路径另行展示。[Atlas 官方说明](https://www.worldlabs.ai/blog/atlas)

第三版不进一步声称：

- 每一个深度图一定使用哪一种 VAE，或与 RGB 共用同一 latent 空间；
- 一个序列元素必然是一帧、一个 patch，或某个固定长度的视频块；
- 官方已经公开特定 Plücker 编码、RoPE 方案、KV-cache 调度或 GS 回写循环；
- 动态视频重构已经证明可预测未发生的动作后果；
- 机器人动作／关节／力是 Atlas 已公开的原生 token 类型。

这些是**目前材料不能确定**，而不是断言 Atlas 没有这些能力。R2S2R 官方描述支持任务级视觉与物理联合对齐，但没有给出可以还原全部系统内部实现的技术细节。[R2S2R 官方说明](https://www.worldlabs.ai/blog/real-to-sim-to-real)

## 三、WorldWarp：应复用“采样路径”，不是误用现有总入口

本地提交仍为 `0396b801c278546d01a6618a18e5a5c2a154c0a1`。既有两处本地修改保持不动。

### 确认的调用边界

[run_inference_chunk](../../../WorldWarp/pose_control.py:1249) 接收视频路径与相机参数，在函数内部：

1. 运行 TTT3R／GS 初始化、优化和 warp；
2. 构造有效性 mask，插入上下文帧；
3. 编码文本与 RGB warp，处理 VAE latent 归一化；
4. 调用 [sample_sequence](../../../WorldWarp/pose_control.py:1009)；
5. 解码并写出视频。

因此它不是“输入外部 GS 渲染图就直接生成”的既有 API。

主线中的点图／位姿前端也不是增量 GS 融合器。应另接 GS 初始化、优化和事务式合并逻辑；可以复用 WorldWarp 的部分建图代码，但不能把 RayMap3R 或 Pi3X 的输出标签直接改名为全局 GS。

### 第三版拟议拆分

建议抽取一个生成 adapter，职责覆盖：

`warp RGB + 有效性 mask + 引用帧 + 文本 → VAE 编码/归一化 → sample_sequence → VAE 解码`

这是**待重构接口**。其中采样函数与权重已有，但外部调用协议、上下文帧处理、mask 腐蚀／降采样、latent 时序尺寸、设备／精度管理都需要保留并测试。不是换一个函数名即可接入。

此外，复用长期 GS 渲染结果会改变模型看到的 warp 误差分布。即使 adapter 的 shape 全通过，也仍需质量测试，必要时重新训练或微调。第三版主链因此全部标为“拟议”，没有标为本地已集成。

## 四、数据契约：这次新增的实质验证

### 4.1 D 与 ED 不能混为一谈

本地 [gsplat/rendering.py](../../../conda_envs/worldwarp/lib/python3.12/site-packages/gsplat/rendering.py:103) 和 [官方 API](https://docs.gsplat.studio/main/apis/rasterization.html) 对两者的定义一致：

- 累计深度：`D = Σ(w_i × z_i)`。
- 覆盖度：`alpha = Σw_i`。
- 期望深度：`ED = D / alpha`，只在有效覆盖区域使用。

即使选择 ED，也不是获得了真实表面深度保证：它仍是混合结果，多层表面和遮挡边界尤其需要检查。不能把低 alpha 区域除出来的数值当有效测量。

本地 WorldWarp 的 [几何有效性检查](../../../WorldWarp/src/ttt3r/ttt3r.py:1439) 已经调用 `ED`；这里**不是发现它使用了错误模式**。本次发现的是跨项目统一接口中遗漏了语义区别：NoPo4D 的当前 decoder 使用 `RGB+D` 并直接返回该深度通道，不能不经转换当成同一种 depth_z。

### 4.2 NoPo4D：当前渲染路径可以给出明确结论

本次通过 GitHub commits API 核对的版本：

- NoPo4D：`cb54c9349792d474aa541274842e0fadf1d807c7`
- DepthDirector：`7f876dbda1e24f4b8516ed05519e6aa740ce58f3`
- ReSplat：`cae7ddc4cdbd80e05e9f5fa00f5ea02c4e9056b1`

以 NoPo4D 的这一版本为准：

1. [encoder](https://github.com/bralani/NoPo4D/blob/cb54c9349792d474aa541274842e0fadf1d807c7/src/model/encoder/encoder.py) 返回 `extrinsic_c2w` 和 `intrinsic_px` 对应的 `intrinsic` 字段。
2. [官方 inference](https://github.com/bralani/NoPo4D/blob/cb54c9349792d474aa541274842e0fadf1d807c7/src/inference.py) 直接把这两个字段传给 `model.render`。
3. [decoder](https://github.com/bralani/NoPo4D/blob/cb54c9349792d474aa541274842e0fadf1d807c7/src/model/decoder/decoder_4dgs.py) 对外参取逆，作为 gsplat 的 w2c；K 原样传入。

**因此此渲染路径应输入 c2w + 像素 K。**不要照 wrapper docstring 传 w2c，也不要因为 normalized 的注释就直接给归一化 K。这里的结论只针对 render 路径：encoder 的已知外参条件接口另有 w2c 约定，不能套用同一个转换到所有入口。

固定机位与时间排序约束仍保留；输入应该按相机、时间组织，并检查真实同步关系。归一化 [0,1] 时间要记录实际时间基准，不可假定不同片段共享同一世界时刻。

### 4.3 建议的公共边界格式，不是所有模型强制支持的输入

| 类型 | 最少应记录的信息 |
|---|---|
| 图像 | image_id、camera_id、frame_id、尺寸、resize/crop/pad 变换、来源 |
| 相机 | OpenCV c2w、像素 K、世界坐标标识、尺度来源；畸变与快门假设 |
| 深度 | z 或 ray distance、D 或 ED、单位／相对尺度、valid mask；不得隐式互换 |
| 可信度 | alpha、几何支持、模型 confidence、staticness 分字段；缺失时保留 unknown |
| GS | 位置、协方差或尺度+旋转、SH 约定、opacity 的 raw/activated 状态、地图版本 |
| 时间 | 真实时间／相机同步偏移、片段归一化映射；与 AR 元素 j、去噪步 s 分开 |
| 证据 | 真实 RGB、估计几何、生成 RGB、合成几何分别标记；保留来源依赖 |

这是一套**adapter 边界设计**，不是把所有模型包装成同一固定参数签名。SEVA、SCoPE 不必接 RGB warp；DepthDirector 仍应保留源视频条件；F4Splat、ReSplat 仍作为完整重建器比较。

resize、crop、pad 应同步更新 K。Sim(3) 世界重对齐应同步更新位姿、点和 GS 协方差；仅移动 Gaussian 中心或只改相机平移是不完整的。单目尺度未校准时必须标为相对尺度，不能直接用于米制机器人碰撞仿真。

## 五、持久地图：真实性与一致性分开

第三版设计两层状态：

- **观测证据层**：真实采集帧、相机标定及可修订的估计几何。真实 RGB 也不意味着其单目估计深度就是真值。
- **生成假设层**：生成视图及其推断几何，保留父观测／模型／种子／版本与置信信息。

生成视图相互重投影一致，只证明这一组假设自洽，不能证明它们就是现实中遮挡区域的真实形状。生成内容可以提交到假设层、参与后续探索；若要升级为有观测支持的几何，需要独立采集或其他有效外部证据。发生冲突时保留证据、降权／替换假设并使关联缓存失效。

原始观测库、模型 KV 等计算缓存、世界 GS 状态还应分别维护版本。地图坐标重置或条件改变后，不能假定旧缓存仍有效；具体哪些缓存可复用须由所选模型协议决定。

## 六、项目选型：不大换血，重新明确角色

| 角色 | 项目 | V3 对应方式 |
|---|---|---|
| 本地运行基线 | [WorldWarp](https://github.com/HyoKong/WorldWarp) | 单片段既有产物；新地图闭环需要采样 adapter |
| 几何前端 | [RayMap3R](https://github.com/Brack-Wang/raymap3r)、[Pi3X](https://github.com/yyfz/Pi3) | 点图／位姿／静态性等候选；先验证返回值与尺度 |
| 几何渲染工具 | [gsplat](https://github.com/nerfstudio-project/gsplat) | typed GS → RGB / ED / alpha；几何支持 mask 另算 |
| 模型记忆参考 | [WorldMem](https://github.com/xizaoqu/WorldMem) | 机制借鉴，不是通用持久地图组件 |
| 数值相机生成 | [SEVA](https://github.com/Stability-AI/stable-virtual-camera)、[SCoPE](https://github.com/TencentARC/SCoPE) | 另一个生成后端；可绕过 GS warp 路线 |
| 视频重渲染 | [DepthDirector](https://github.com/FREDZEL2020/DepthDirector) | 源视频 + 目标深度条件；独立协议，不能只给任意首帧 |
| 静态资产重建 | [F4Splat](https://github.com/mlvlab/F4Splat)、[ReSplat](https://github.com/cvg/resplat) | 完整重建器，不是外部 GS 的通用增量更新算子 |
| 动态重构 | [NoPo4D](https://github.com/bralani/NoPo4D)、[ClipGStream](https://github.com/liangjie1999/ClipGStream)、[Track4World](https://github.com/TencentARC/Track4World) | 前馈／优化／跟踪分工；不自动解决反事实动力学 |
| 物理仿真 | [MuJoCo](https://github.com/google-deepmind/mujoco)、[Genesis](https://github.com/Genesis-Embodied-AI/genesis-world) | 需要独立物理资产与参数；GS 外观不能直接代替碰撞体 |
| 展示／数据 | [Spark](https://github.com/sparkjsdev/spark)、[spz](https://github.com/nianticlabs/spz)、[BlenderProc](https://github.com/DLR-RM/BlenderProc)、[ViPE](https://github.com/nv-tlabs/vipe) | 展示格式、合成监督、真实视频几何预处理 |
| 完整路线对照 | [HY-World 2.0](https://github.com/Tencent-Hunyuan/HY-World-2.0)、[PixWorld](https://github.com/SensenGao/PixWorld)、[SpatialGen](https://github.com/manycore-research/SpatialGen) | 与本地主线并列，不放进统一“后处理头” |

第二版关于 DepthDirector 的源视频条件和 ReSplat 自带初始化／状态的判断保留。本次还核查了 [DepthDirector 测试入口](https://github.com/FREDZEL2020/DepthDirector/blob/7f876dbda1e24f4b8516ed05519e6aa740ce58f3/training/test.py)：其测试流程确实沿配置传入 `extra_inputs`，并非只在训练 YAML 中出现的字段。

“公开候选”不等于所有资产均为 OSI 开源或允许商用。WorldWarp／PixWorld 许可待确认、Pi3X／SEVA 的非商用约束等边界继续保留；代码、权重、数据和依赖必须分别核查。这里没有进行完整法律审核，也没有声称其他候选已在本机跑通。

## 七、应怎样验证第三版，而不是仅把图画完整

实施顺序：

1. **抽取 adapter 并做输出等价测试**：固定种子、输入和配置，确认拆分后与旧单片段路径一致。
2. **统一数据语义**：c2w/w2c、K resize、D/ED、GS raw/activated、尺度与时间转换。
3. **新增 session 状态与证据分层**：验证增量提交、回滚、缓存失效及真实／生成来源。
4. **再测长程质量**：返回原位、遮挡再显露、旋转和平移、动态前景污染；区分相机误差与几何误差。
5. **最后比较后端**：固定数据与协议，再比较几何、生成或资产重建模型，每次只换一个维度。

随附 [validate_v3.py](../../../diagrams/validate_v3.py) 检查 SVG XML、文字宽度、链接／箭头引用、无嵌入位图，以及小规模相机与深度契约算例。算例不是 NoPo4D 或 WorldWarp 的真实模型测试。两张 SVG 还需实际渲染后检查版面；任何“模型级通过”的结论仍以将来的独立实验为准。

本次完成结果：上述静态检查与契约算例均通过；两图已使用 CairoSVG 渲染并检查中文、版面和连线。前两版 SVG 与第二版报告的 SHA-256 保持一致。没有改变 WorldWarp 代码、权重、环境或既有生成产物。
