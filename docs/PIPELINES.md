# 推理管线与调用契约

本文件说明当前可执行入口；历史来源见 [EXPERIMENTS.md](EXPERIMENTS.md)。机器读取 [registry.json](../pipelines/registry.json)，人或 AI 调用 `python scripts/pipelines.py`。

其他 Linux 账号复用本机安装时，使用 `bash /共享项目路径/scripts/shared_pipeline.sh` 加相同子命令和参数；见 [SHARED_USE.md](SHARED_USE.md)。该入口隔离个人运行缓存，模型参数保持一致。

## 1. 发现与执行接口

| 子命令 | 行为 | 是否加载模型 |
|---|---|---|
| `list` | 输出 JSON 管线表、别名、默认值和历史验证范围 | 否 |
| `describe G` | 输出一个管线的定义 | 否 |
| `plan --pipeline ... --input ... --output ...` | 输出阶段 argv、参数、预期时长；不写文件 | 否 |
| `doctor`，参数同 plan | 检查解释器、权重路径、ffmpeg / ffprobe | 否 |
| `run`，参数同 plan，另需 `--gpu` | 按计划串行执行阶段，记录日志和状态 | 是 |
| `status RUN_DIR` | 读取运行状态 JSON | 否 |
| `benchmark plan/doctor/run --manifest INVENTORY.json --count 3 --output NEW_RUN --gpu GPU_ID` | DL3DV 真实轨迹、论文配置的本地 WorldWarp 评测 | 仅 run 加载 |

同一项目的模型依赖可能需要特定 Python / PyTorch / CUDA，不把三个项目强行塞进一个环境。每个阶段选择相应解释器；F/G/H 的视频进程内部会用 MapAnything 解释器估几何。运行过程在 `logs/worldwarp.log` 和 `video/geometry/chunk_NNN/mapanything.log` 可追踪。

### DL3DV 本地评测入口

`benchmark` 是独立契约，不修改 A–H 的 321 帧配置。它使用原版 WorldWarp：TTT3R → 原生 GS → 扩散；5 段 49 帧、后续重叠 5 帧，共 225 帧，720×480，strength 0.8、GS 500 步、采样 50 步、CFG 5、seed 32。按补充材料 §7 先从参考视频估计控制相机，生成阶段仅使用第一张真实图及生成历史；参考视频深度不能用于生成。

输入为已审计的场景清单，当前读取 pixelSplat `.torch` 格式，按 scene ID 排序取前 `count` 个场景；每场景需至少 225 帧，按时间戳排序取前 225 帧。不支持把不完整场景静默跳过或混入训练图片。首图计为第 1 帧，端点评测第 50 / 200 帧。保存 PNG、两种相机、逐帧图像指标、独立 DUSt3R 位姿、并排视频和自包含 README。3 场景 FID 只能作诊断；这不是 WorldWarp 官方划分或官方分数复现。

指定场景时，先把所选条目完整复制到独立清单的 `scenes` 数组，保留原 `scene_id`、`format`、`shard_path`、`frames` 等字段，可用 `selection_description` 记录选取理由；再把 `--manifest` 指向该清单，`--count` 设为实际场景数（至少 2）。输出报告保存所选清单及相应复跑命令，避免误跑回原清单的前三个场景。

指标依赖用 `scripts/worldwarp_benchmark_constraints.txt` 约束安装，避免升级 NumPy 破坏原 CUDA 扩展 ABI。另需独立官方 DUSt3R 源码（含 CroCo），用 `--dust3r-root` 指定；默认本机 `/data4/sumai/eval_tools/dust3r`，权重 `checkpoints/dust3r/DUSt3R_ViTLarge_BaseDecoder_512_dpt.pth`，以及 LPIPS / Inception 缓存。源码与权重均不提交本仓库。`doctor` 仍只是路径检查，完整推理验收以运行状态和报告为准。

## 2. 三类视频几何来源

**A 原版与原版平移：**先由 TTT3R 获取输入序列的深度和内部位姿，WorldWarp 自带 GS 负责拟合 / 渲染，再执行视频扩散。下一段沿用原版选帧与 1 帧上下文。平移参数 `--dx` 是每帧位移，单位为场景预测单位，不能直接当厘米。

**F/G/H：**首段只给 MapAnything 原图，后续段从上一段局部 0/20/40/60/80 抽 5 个关键帧。G/H 额外加入原图，删除全局 0 的重复；来源数量 1/5/6/6。F 数量 1/5/5/5。G/F 用每源最多 5 万点、总数上限 35 万点初始化原生 GS，每段重新拟合；H 做双线性点云投影、每来源 z-buffer 和融合。原图权重为 2，生成来源为 1，首段单图权重为 1。MapAnything 预测的相机保留作诊断，下游保持请求 K/c2w。

**B/C/D/E 三项目：**MapAnything 从原图估密集深度，GaME 接收该 RGB-D，用全图静态 mask 拟合固定场景；然后渲染 321 个目标视角，RGB / alpha 供每一段 WorldWarp 使用。没有生成历史回写到这个场景。B 为 ctx1/.60，C 为 ctx5/.60，D 为 ctx1/.50，E 为 ctx1/.65。统一入口调用共享的上下文适配器；旧 B/D/E 的专用脚本仍保留作为历史实现。

## 3. 输入、运动、时长和参数

| 参数 | 默认 / 范围 | 影响 |
|---|---|---|
| `--pipeline` | 必填；支持 ID、A–H 和注册别名 | 选择几何来源和视频组合 |
| `--input` | 视频 1 张图片；几何多张图片或目录 | 真实输入数据；视频目录批处理需逐图运行 |
| `--output` | 必填，必须是新目录 | 防止覆盖已有结果 |
| `--gpu` | run 必填，例如 `1` 或 `GPU-...` | 只选择一张 GPU，不自动占用固定编号 |
| `--prompt` | 通用“保留输入场景 + 静态运动”英文提示 | 为新场景提供文本条件，避免复用 classroom 内容 |
| `--angle` | −20；严格在 (−90,0) | 纯旋转管线总 Y 轴转角 |
| `--dx` | −0.002，必须为负 | 仅原版左平移每帧 X 位移 |
| `--chunks` | 统一入口目前固定 4 | 全部版本对齐到 321 帧 / 10.7 秒 |
| `--strength` | A/B/C/F/G/H=.60，D=.50，E=.65；[0,1] | 有效区域的扩散日程强度，不是 RGB 混合百分比 |
| `--context-frames` | 按注册值；适配器允许 1/5/9/13/17/21/25，A / 左移固定 1 | 后续段连续上下文，非几何关键帧数 |
| `--gs-iterations` | 500，正整数 | 原生 GS 每段迭代；GaME 主拟合迭代，另有 50 步预热；H 不做 GS |
| `--sampling-steps` | 50，正整数 | 视频采样步数 |
| `--cfg` | 5，非负有限数 | 文本 classifier-free guidance |
| `--seed` | 32 | 视频与 A 原版拟合的种子；F/G 桥接渲染器目前固定使用 32，GaME 静态适配器固定 0 |
| `--capture` | `standard` / `full` | full 仅 A/F/G/H，保存每次迭代和逐帧条件 |
| `--posthoc` | 默认关闭，仅 F/G/H | 成片后全部帧的额外 MapAnything 推理 |
| `--max-views` | 8 | 几何管线读取图像数上限；GaME 可能只接纳其中部分关键帧 |
| `--source-kind` | observed / rendered / generated / unknown | 几何管线的来源标记，应按图片实际来源指定 |
| `--map-variant` | default / apache | 仅几何管线可切换权重；视频适配器固定 default |

若参数表写了“仅某分支”，不要把它当作其他分支的效果开关。新数据带来的视觉质量没有统一保证；更大旋转角、更多上下文和不同 strength 可以执行，不代表这些组合都已完成质量对照。

视频采用 480×608（宽×高）、30 fps。相机 K 固定为 `fx=fy=576, cx=240, cy=304`，不是原照片真实标定。4 段的最终全局帧号为 0–320；前 81 帧，后三段各新增 80 帧，合计 10.7 秒。第一 / 最后一帧时间戳为 0 / 10.6667 秒。

## 4. 可直接交给 AI 的任务与命令

**任务：使用 G 管线跑 classroom，保存完整中间结果。**

```bash
python scripts/pipelines.py run --pipeline G --input Data/classroom.png \
  --output runs/classroom_G_full --gpu 1 --capture full --posthoc
```

**任务：使用 F 和 H 各跑一遍自己的客厅图片，比较 GS 与点云。** 为两次执行选择不同输出目录；顺序执行并检查每次结果。

```bash
python scripts/pipelines.py run --pipeline F --input /path/living_room.png \
  --output runs/living_F --gpu 1
python scripts/pipelines.py run --pipeline H --input /path/living_room.png \
  --output runs/living_H --gpu 1
```

**任务：复现 D 类配置，三项目管线采用 1 帧上下文、strength .50。**

```bash
python scripts/pipelines.py run --pipeline D --input Data/classroom.png \
  --output runs/classroom_D --gpu 1
```

如果明确要把 5 帧上下文与 .50 强度结合，使用 C 加 `--strength 0.5`，这是另一个配置组合，不能称为原来 D 的默认配置。

**任务：对现场多图估深，然后输出静态高斯场景，不生成视频。**

```bash
python scripts/pipelines.py run --pipeline mapanything-game \
  --input /path/scene_images --output runs/scene_GS --gpu 1 \
  --source-kind observed --max-views 8 --gs-iterations 500
```

这些 GPU 编号是占位示例，执行前检查资源。`run` 要求输入文件真实存在、输出目录不存在；`plan` 和 `doctor` 也会进行这些基本参数检查。

## 5. 新数据不需要历史基线

`pipeline_reference.py` 接收这次输入图和 caption，只产生：

```text
reference/
  input_prepared.png
  requested_camera_trajectory.npz
  reference.json
  captions/chunk_000.txt ... chunk_003.txt
```

底层脚本原有 `--baseline` 参数现在可以接收这份 reference，也兼容旧视频报告。新的 reference **没有分段 MP4，也没有所谓“已经生成过的基线视频”**。历史提示词复用与新文本条件在报告中分别标记。统一入口会使用本次 prompt 作为直接 caption，免去 Qwen 描述生成；不是说 Qwen 在项目其他入口被删除。

## 6. 输出和全量记录

```text
RUN/
  plan.json               管线 ID、实际参数、每阶段命令
  status.json             running / complete / failed / interrupted
  preflight.json          启动前路径检查
  caption.txt
  logs/STAGE.log
  reference/              相机 / 文本参考（旋转视频）
  video/                  视频报告、相机、分段、最终 MP4
    geometry/chunk_NNN/    F/G/H 每段 Map RGB-D / 渲染
    mapanything_all_generated_frames/  仅 --posthoc，事后诊断
  traces/                 仅 --capture full
  geometry/               独立几何 / GaME 管线的 RGB-D
  scene/                  GaME 场景（若使用）
  guidance/               GaME 固定轨迹渲染（若使用）
```

A/F/G 的 `full` 包含每次优化模型（初始 0 + 更新后 1…N）、实际训练 RGB/alpha/depth、逐次 JSONL 损失、逐帧几何 RGB/alpha、VAE 前 RGB / 二值掩码 / latent mask、编码前 PNG。F/G/H 另保存实际参与建模的 MapAnything 原生输出；A 另补最后一段 TTT3R。H 没有 GS 拟合记录。没有每一步扩散采样 latent 或每步解码画面。

`full` 的损失原始格式是 JSONL；原 classroom 专用核验器还会导出 CSV 和损失图，但它要求原先那套多版本归档布局，不能直接对单个统一运行目录套用。需要汇总单个新运行时按其 `manifest.json` 读取，不伪称 CSV 已自动产生。

GaME 视频和 standalone 几何分支目前统一入口提供标准记录；历史的 GaME 全迭代捕获仍可以通过 `run_classroom_trace_variant.py --trace-variant game` 对指定 RGB-D 单独执行。没有把不兼容的全量选项默默忽略。

## 7. 检查结果而不是只看进程结束

`status.json` 仅在所有阶段返回 0，且最终视频解码计数 / 尺寸 / fps 或几何产物检查通过后变为 `complete`。stdout 打印最终结构化结果。状态文件写入采用临时文件替换，避免读到一半 JSON。

当前 `doctor` 是只读路径检查；它没有测量空闲显存、检查所有权重分片或运行 CUDA kernel。原部署验证与本次 CPU 路由测试分别记录，不混作新数据的 GPU 质量保证。推理失败查看对应日志，保留现场，用新的运行目录修复后重试。
