# jiaiL_atlas

把本地部署的 **WorldWarp、MapAnything、GaME** 及它们之间实际跑过的推理适配器放在一个仓库中。三个项目都是普通源码目录，包括所需的子模块源码；克隆本仓库后无需 `git submodule update`。上游来源、固定提交及本地改动记录在 [docs/upstream_sources.json](docs/upstream_sources.json)，版权声明和已有许可证保留。

面向 AI 工具的入口是 [AGENTS.md](AGENTS.md)、[机器可读管线表](pipelines/registry.json)和 [scripts/pipelines.py](scripts/pipelines.py)。例如可以对 AI 说：

> 使用 G 管线跑 Data/classroom.png，固定相机中心匀速向左转 20°，4 段合计 10.7 秒，保存全量中间结果。

> 使用 WorldWarp 原版左移管线跑 Data/bedroom.png，每帧沿 X 轴移动 −0.002 场景单位。

> 使用 MapAnything + GaME 管线跑我的一组现场照片，输出静态 GS 场景。

## 一条命令运行

先确认模型环境和权重已按 [环境说明](docs/ENVIRONMENT.md)配置。`list`、`describe`、`plan` 只需 Python 标准库，不加载模型。

```bash
python scripts/pipelines.py list
python scripts/pipelines.py describe G

# 先查看执行计划，不启动推理，也不创建输出目录
python scripts/pipelines.py plan --pipeline G \
  --input Data/classroom.png --output runs/classroom_G

# 确认 GPU 空闲后填写实际编号；这里的 1 只是命令示例
nvidia-smi
python scripts/pipelines.py run --pipeline G \
  --input Data/classroom.png --output runs/classroom_G --gpu 1
```

输出包含 `plan.json`、`status.json`、逐阶段 `logs/`，以及 `video/` 下的最终视频、相机、分段、几何和配置。执行失败返回非零退出码，完成后逐帧核对视频格式。查询进度：

```bash
python scripts/pipelines.py status runs/classroom_G
```

## 已明确的管线

| 管线 ID / 简称 | 实际数据流 | 历史反馈 / 上下文 | 产物 |
|---|---|---|---|
| `ww-rotate` / A | TTT3R → WorldWarp 原生 GS → WorldWarp | 原版，1 帧上下文 | 匀速左转视频 |
| `ww-translate` | TTT3R → WorldWarp 原生 GS → WorldWarp | 原版，1 帧上下文 | 匀速左平移视频 |
| `map-ww-gs` / F | MapAnything → WorldWarp 原生 GS → WorldWarp | 上一段 5 个均匀关键帧；5 帧连续上下文 | 左转视频 |
| `map-ww-anchor-gs` / G | MapAnything → WorldWarp 原生 GS → WorldWarp | F 加原图，原图权重 2 | 左转视频 |
| `map-ww-anchor-points` / H | MapAnything → 点云投影 → WorldWarp | 原图 + 历史；没有 GS 迭代拟合 | 左转视频 |
| `map-game-ww` / B | MapAnything → GaME 固定场景 → WorldWarp | 固定几何，1 帧上下文，strength .60 | 左转视频 |
| `map-game-ww-ctx5` / C | 同 B | 固定几何，5 帧上下文，strength .60 | 左转视频 |
| `map-game-ww-s050` / D | 同 B | 1 帧上下文，strength .50 | 左转视频 |
| `map-game-ww-s065` / E | 同 B | 1 帧上下文，strength .65 | 左转视频 |
| `mapanything` | 多视图 RGB → MapAnything | 单次联合几何推理 | RGB-D / 点图 / 点云 |
| `mapanything-game` | MapAnything → GaME | 全图静态 mask 适配器 | RGB-D + 静态 GS 场景 |

**视频统一入口目前明确支持 4 段合计 10.7 秒：321 帧、30 fps、480×608。** 每段交付前有 81 帧，后三段拼接时去掉边界重叠；F/G/H 和 C 的原始上下文窗口为 81、85、85、85 帧，A/B/D/E 的默认原始窗口每段为 81 帧。不能将这解释为每段 10.7 秒。原版底层脚本允许其他段数，但统一多项目适配器没有把未验证时长伪装成通用支持。

## 新数据和中间结果

视频管线每次接受一张图片，可以换成任何支持的图片路径。新的“参考目录”只准备输入图、请求相机和文本，**不要求先跑一遍原版 WorldWarp**，也不偷偷复用 classroom 的提示词。可用 `--prompt` 描述当前场景。

```bash
python scripts/pipelines.py run --pipeline G \
  --input /path/to/new_scene.png --output runs/new_scene_G --gpu 1 \
  --prompt "Photorealistic view of this room. Keep all objects stationary. Rotate the camera slowly left at a fixed center." \
  --capture full --posthoc

python scripts/pipelines.py run --pipeline ww-translate \
  --input Data/bedroom.png --output runs/bedroom_left --gpu 1 --dx -0.002

python scripts/pipelines.py run --pipeline mapanything-game \
  --input /path/to/scene_images --output runs/scene_geometry --gpu 1 \
  --source-kind observed --max-views 8
```

`--capture full` 支持 A/F/G/H，保存每步 GS 模型和训练渲染、实际几何条件和生成帧等；H 没有 GS 模型。`--posthoc` 仅适用于 F/G/H，另对成片全部 321 帧推理 MapAnything，属于事后诊断，不参与已完成视频的生成。全量记录可能产生数十至上百 GiB 数据，运行前检查目标磁盘空间。

## 文档与验证

- [管线、参数和自然语言调用说明](docs/PIPELINES.md)
- [AI 工具执行规范](AGENTS.md)
- [环境、权重和可迁移路径](docs/ENVIRONMENT.md)
- [历史实验与新入口的区别](docs/EXPERIMENTS.md)
- [代码来源与许可证范围](docs/THIRD_PARTY.md)
- [本次整理的检查记录](docs/VALIDATION.md)

代码仓库不包含 `conda_envs/`、模型权重、缓存、`WorldWarp_outputs/` 或 243 MiB 的离线报告包 `Reports/`。这些本地文件仍保留在服务器；下载代码仓库不等于下载全部实验视频。原有安装记录和研究 Markdown 作为历史材料保留，当前可执行契约以本 README、AGENTS 和管线表为准。

CPU 调用契约测试：

```bash
python -m pip install numpy pillow
python -m unittest discover -s scripts -p test_pipelines.py -v
```

这些测试检查计划、真实脚本参数、图片和相机准备、状态与失败处理；历史 GPU 视频推理另有完成记录。本次仓库整理没有重新宣称所有新入口都经过一次完整 GPU 长视频生成。
