# Atlas 极简复刻：开源组件更新调研

更新时间：2026-09-05

## 结论先行

当前最务实的方案不是找一个项目整体替代 WorldWarp，而是把它保留为**静态、单图、可循环探索的可运行骨架**，再有选择地替换三个薄弱部件：

1. 用 RayMap3R 改善含动态前景的视频几何和长期地图更新；
2. 用 DepthDirector 的“内容流 + 深度视角流”替换 RGB 高斯渲染图直接做控制的方式；
3. 用 ReSplat/F4Splat 做两帧以后更可靠的前馈高斯初始化与融合。

真实动态应单独走多相机 4D 分支：短序列/前馈优先 NoPo4D，长序列/优化优先 ClipGStream。它和静态生成环共享相机、深度、点图接口，但不强行共用一套高斯状态。

## 推荐的最小可实现框架

```text
静态/生成分支
I0 + K0,T0
  -> 点图/位姿/置信度
  -> 初始静态 GS 缓存 G0
  -> 在目标 Ki,Ti 渲染 depth + visibility（RGB 仅作辅助）
  -> 视频扩散：I0/历史视频作 content，depth/visibility 作 view control
  -> Ii
  -> Ii 的点图/置信度/高斯候选
  -> 几何一致性门控 + render-error 更新
  -> Gi
  -> 循环

动态/采集分支
同步多相机视频 + 可选 K,T
  -> 时序点图/轨迹/scene flow
  -> 动静分解
  -> 静态背景 GS + 动态 4DGS
  -> 任意相机、任意时间渲染
```

这一拆分也更贴合 Atlas 官网描述：长时间、相机可控的“生成”，和少量同步相机完成的 bullet-time/时空重建，可以共享底层表征与相机接口，但没有必要在第一版 clone 中假定它们是同一条推理链。

## 每个部件最贴切的开源项目

| 部件 | 首选项目 | 输入 | 输出 | 与当前 WorldWarp 的关系 | 开源可用性 |
|---|---|---|---|---|---|
| 可运行的完整静态骨架 | [WorldWarp](https://github.com/HyoKong/WorldWarp) | 单图、目标相机轨迹 | 长轨迹视频、在线 3D cache | 已安装并跑通；作为 V1 主干 | 代码/权重公开；仓库根目录暂无 LICENSE，商用前确认 |
| 动态干扰下的在线点图/SLAM | [RayMap3R](https://github.com/Brack-Wang/raymap3r) | 连续 RGB | depth/conf/color、K/T、融合点云、静态性 | 最容易接入：复用 WorldWarp 已下载的 CUT3R checkpoint，以 staticness gate 抑制移动人物进入静态地图 | MIT，代码公开 |
| 长流式点图和位姿 | [ABot-Recon](https://github.com/amap-cvlab/ABot-Recon) | 任意长 RGB 流 | 当前帧点图、邻帧位姿、全局轨迹/点云 | 12 帧局部上下文和 KV cache，适合替代 TTT3R 做恒定显存长序列重建 | Apache-2.0 代码公开 |
| 已知相机的高精度点图 | [Pi3X](https://github.com/yyfz/Pi3) | RGB + 已知 K/T | 每像素 3D point map/confidence | 最接近 Atlas benchmark 的 posed reconstruction 接口；可作为离线几何基线 | 代码 BSD；公开权重带非商用约束，需区分 |
| 首批直接前馈 GS | [YoNoSplat](https://github.com/cvg/YoNoSplat) | 未标定位图；也可给 K/T | 3D Gaussians + 相机 | 可直接替代“点图再优化成 GS”，但公开 checkpoint 分辨率偏低 | MIT，代码/权重公开 |
| 两帧后的高斯生成 | [F4Splat](https://github.com/mlvlab/F4Splat) | 2–16 张图 | 带 densification/预算控制的 GS | 当循环得到 `I0 + I1` 后很贴切；不适合仅一张首帧 | MIT，代码与多套 checkpoint 公开 |
| 两帧高斯融合/纠错 | [ReSplat](https://github.com/cvg/resplat) | 多视图、K/T、当前 GS 和渲染误差 | 每个 Gaussian 的参数更新 | 与“渲染 R 后根据误差融合新帧”高度对应；用共享循环模块做 gradient-free refinement | MIT，代码/权重公开 |
| 紧凑 GS / cache 降载 | [ZipSplat](https://github.com/cvg/ZipSplat) | 少量未标定位图 | 紧凑 GS | 适合减少在线 cache 的 Gaussian 数，作为多帧重建器而非首帧器 | 代码与权重公开 |
| 高分辨率最终 GS 导出 | [LGTM](https://github.com/apple/ml-lgtm) | 多视图 | 原生 4K textured Gaussians | 放在在线探索后的离线 consolidate/export 阶段 | 代码/checkpoint 公开 |
| 最贴合的相机受控生成器 | [DepthDirector](https://github.com/FREDZEL2020/DepthDirector) | 源视频/首帧内容流 + 目标轨迹下 warp depth 视角流 | 新相机轨迹视频 | 最关键升级：避免 RGB warp 的“inpainting trap”；高斯只需输出 depth/visibility，I/历史视频保持强内容约束 | Apache-2.0，代码、模型、数据公开 |
| 原生数值相机条件的视频模型 | [SCoPE](https://github.com/TencentARC/SCoPE) | 首帧、文本、数值相机轨迹 | 相机受控视频 | 当不想依赖 GS 渲染 R 时可替换生成模块；Plücker 射线直接进 Wan2.2 | 代码和权重公开；14B 较重，依赖条款需逐项核对 |
| 轻量相机控制适配 | [CameraNoise](https://github.com/gulucaptain/CameraNoise) | 首帧、相机轨迹、由几何流 warp 的扩散噪声 | 相机受控视频 | 对 Wan2.1 改动较小，适合快速实验；几何约束弱于显式 depth 视角流 | Apache-2.0，代码/权重公开 |
| 前馈多相机动态 4DGS | [NoPo4D](https://github.com/bralani/NoPo4D) | 未标定多相机视频 | 动态 Gaussians、K/T、depth、前后向 flow | 最贴合“几部普通相机拍摄后直接重建动态”的 Atlas-like 分支 | MIT，推理代码与 HF 权重已公开；项目很新，先做本地复现验收 |
| 长时多相机 4DGS | [ClipGStream](https://github.com/liangjie1999/ClipGStream) | 同步多相机长视频 | 可任意时空视角渲染的动态 GS | clip-stream 优化更适合任意长度和降低片段间闪烁；不是实时单图生成 | 代码公开；仓库许可需确认 |
| 动态对应和 3D scene flow | [Track4World](https://github.com/TencentARC/Track4World) | 单目视频 | 每像素世界点、2D/3D flow、相机位姿 | 给动静分解和跨时间 Gaussian identity/轨迹提供监督；不是 GS renderer | 代码/权重公开 |
| 长期实时世界 rollout | [ABot-World](https://github.com/amap-cvlab/ABot-World) | 图像/历史帧 + 动作 | 720p 长视频 rollout | 可借鉴因果蒸馏、LongForcing、服务；没有显式 GS，不能取代几何地图 | Apache-2.0，推理/权重/数据公开 |
| 最像 Atlas 的端到端研究方向 | [ABot-3DWorld 0](https://github.com/amap-cvlab/ABot-3DWorld) | 图像/轨迹等空间条件 | panorama + spatial point cloud，再生成/整理 GS | “空间生成原语 + 生成 + 显式 3D”在结构上最接近 Atlas | 截至本次检查，官方仓库主要是网页资产，尚不能当成可运行部件 |

## 建议的融合顺序

### V1：保持当前 WorldWarp 可运行

- TTT3R/CUT3R 产生 depth、K/T、点图。
- WorldWarp 在线 3D cache 负责静态背景。
- GS 渲染得到 RGB/depth/mask，Wan 补全目标视角。
- 每次只更新高置信静态区域；人物等动态区域不烘焙进静态 GS。

这是现在最短、已经在本机跑通的路径。

### V1.5：最值得先改的三处

1. **TTT3R → RayMap3R 包装层**：它复用相同的 CUT3R 权重，增加动态 staticness gate、重定位和 Sim(3) 对齐，接入成本最低。
2. **RGB 渲染控制 → DepthDirector 双流控制**：`I0/历史视频` 走内容流；由当前 GS 在目标位姿渲染的 `depth + visibility` 走视角流。RGB `R` 只作为辅助，不再承担主要控制，减少把空洞、拉伸纹理固化进生成结果。
3. **第二帧以后接 ReSplat/F4Splat**：F4Splat 负责少量视图前馈初始化，ReSplat 用 render error 给 Gaussian 参数作循环更新；再叠加几何置信度、可见性、重复点合并和预算裁剪。

### V2：动态独立分支

- 同步 3–5 相机：先用 NoPo4D 做 feed-forward 4DGS 原型；需要更长时间和更稳定的质量时用 ClipGStream。
- Track4World 提供世界坐标中的 dense tracking/scene flow，用于跨时间 Gaussian 关联、动静分解和轨迹正则。
- 输出拆成 `G_static` 与 `G_dynamic(t)`。相机变化只改变渲染矩阵；人物动作变化则查询/变形 `G_dynamic(t)`，而不是让视频模型每次重画后再塞回一个静态 GS。
- 只有“从单张图凭空想象未来动作”时才让视频模型生成时间内容；多相机真实动态重建优先走 4DGS。这与用户提出的 Atlas 动态理解一致，也更可控。

## 哪些项目不应直接替换主干

- **ABot-World**解决的是因果视频 rollout 和部署效率，不输出显式几何；适合做生成/serving 参考，不是 Atlas 3D 核心。
- **ABot-3DWorld 0**的论文框架非常像目标架构，但当前公开仓库不能直接运行，先跟踪而不是纳入交付依赖。
- **LGTM/G4Splat**更适合离线高质量 consolidate，而不是每一步都重建的在线循环。
- **SCoPE**相机条件更原生，但 14B 很重；在当前单机原型里，DepthDirector 5B 的接口更接近现有 `I + R + Wan` 设计。

## 最终选型

如果只选一套最贴切、能逐步落地的组合：

```text
静态生成：RayMap3R + WorldWarp cache + DepthDirector + ReSplat
少视图 GS：F4Splat（2 帧以后）
动态重建：NoPo4D（短/前馈）或 ClipGStream（长/优化）
动态对应：Track4World
最终高分辨率导出：LGTM
```

接口上可以拼接，但不是把仓库直接 `pip install` 后无缝串起来。需要统一四项契约：OpenCV/OpenGL 相机 convention、尺度/Sim(3)、depth 定义及无效值、Gaussian 参数格式与时间索引。第一阶段应先固定内部数据结构，再逐个做 adapter。
