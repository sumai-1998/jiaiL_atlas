# 环境、权重与目录迁移

同一服务器的其他 Linux 用户直接复用现有安装，见 [多用户使用说明](SHARED_USE.md)。入口为 `bash scripts/shared_pipeline.sh ...`，运行结果放在各自目录。

统一命令把三个已部署项目连接起来，不包含预训练权重或可搬到任意系统运行的 CUDA 二进制。原服务器是 Linux / NVIDIA RTX A6000。当前安装版本从三个解释器读取，见 [environment_snapshot.json](environment_snapshot.json)。

| 环境 | Python | PyTorch | NumPy | 主要用途 |
|---|---|---|---|---|
| worldwarp | 3.12.14 | 2.7.1+cu126 | 1.26.4 | 视频 VAE、Transformer、TTT3R、原生 GS |
| mapanything | 3.12.14 | 2.5.1+cu124 | 2.2.6 | MapAnything 几何预测 |
| game | 3.10.21 | 2.5.1+cu124 | 1.26.4 | GaME 场景拟合与 CUDA rasterizer |

## 默认目录和覆盖变量

在仓库根目录放置：

```text
conda_envs/worldwarp/bin/python
conda_envs/mapanything/bin/python
conda_envs/game/bin/python

WorldWarp/ckpt/worldwarp_latest.ckpt
WorldWarp/ckpt/Wan-AI/Wan2.1-T2V-1.3B-Diffusers/
WorldWarp/ckpt/Qwen/Qwen2.5-VL-7B-Instruct/       GUI / 自动 caption 入口使用
WorldWarp/src/ttt3r/cut3r_512_dpt_4_64.pth
checkpoints/mapanything/model.safetensors
checkpoints/mapanything-apache/model.safetensors  可选，仅几何入口切换
hf_cache/
.cache/torch_geometry/
```

解释器不在此处时可以覆盖：

```bash
export GIL_WORLDWARP_PYTHON=/your/envs/worldwarp/bin/python
export GIL_MAPANYTHING_PYTHON=/your/envs/mapanything/bin/python
export GIL_GAME_PYTHON=/your/envs/game/bin/python

python scripts/pipelines.py doctor --pipeline G \
  --input Data/classroom.png --output runs/check_example
```

运行器依据脚本所在位置定位仓库，不固定 `/data4/sumai/GIL_ATLAS`。也会把对应源码目录放入 PYTHONPATH；若移动了源码或重新建环境，应重新做 editable 安装和本地扩展编译，不复制旧 `.so` 冒充跨机器可用。

CUDA 编译环境默认 WorldWarp `/usr/local/cuda-12.8`，MapAnything/GaME `/usr/local/cuda-12.4`，目录存在时使用。可分别覆盖 `GIL_CUDA_WORLDWARP`、`GIL_CUDA_MAPANYTHING`、`GIL_CUDA_GAME`。这与 PyTorch wheel 自带的运行库版本不是同一个概念。

## 新机器安装顺序

1. 创建三套对应 Python 环境；安装表中对应的 PyTorch / torchvision / NumPy。
2. WorldWarp 按 [上游安装部分](../WorldWarp/README.md)安装 `requirements.txt`、FlashAttention、PyTorch3D，编译 `WorldWarp/src/fused-ssim`、`WorldWarp/src/simple-knn` 和 `WorldWarp/src/ttt3r/croco/models/curope`。这些源码已包含在统一仓库，跳过克隆 WorldWarp / 拉子模块的步骤。
3. MapAnything 在其解释器内安装 `pip install -e ./MapAnything`，结合 [本地约束文件](../scripts/mapanything_constraints.txt)与快照补齐 Open3D 等几何适配依赖。只运行本仓库基本推理不需要装全套研究 benchmark 的可选模型。
4. GaME 按 [上游依赖说明](../GaME/README.md)与 [本地约束](../scripts/geometry_constraints.txt)安装要求，编译 `GaME/submodules/{diff-gaussian-rasterization,flashsplat-rasterization,simple-knn}`。保留各子目录内的第三方源码和头文件。
5. 下载权重和必要 Torch Hub / 指标缓存，随后运行路径检查、环境脚本和小规模 GPU 验证。不要直接用长视频代替安装排错。

安装命令应在相应解释器内执行；不要在同一环境里交替安装三种 PyTorch 版本。原服务器的详细排错和 GPU 验收记录仍在 [WORLDWARP_SETUP.md](reports/archive/WORLDWARP_SETUP.md)与 [GEOMETRY_SETUP.md](reports/archive/GEOMETRY_SETUP.md)，其中绝对路径、历史输出和“当时空闲的 GPU”均为历史记录，需要换成新机器位置。

## 模型来源

WorldWarp 及 Wan / Qwen / CUT3R 权重下载入口保留在 [WorldWarp README](../WorldWarp/README.md)。统一 CLI 使用明确 caption，不需要启动 Qwen 描述生成；A 需要 TTT3R，当前 GaME 视频上下文适配器也会加载上游 TTT3R 对象，但不调用它来提供几何。F/G/H 的加载路径不加载 TTT3R 模型。

MapAnything 有固定 revision 和 SHA256 校验脚本：

```bash
conda_envs/mapanything/bin/python scripts/download_geometry_ckpts.py --variant default
# 可选
conda_envs/mapanything/bin/python scripts/download_geometry_ckpts.py --variant apache
```

脚本保存来源记录并检查权重，不把权重写进 Git。GaME 本身不需要一个通用的预训练场景权重；`scene/checkpoints/checkpoint.pth` 是对输入场景拟合出来的结果。

推理阶段设置 HF / Transformers 离线模式，避免一次运行临时更换模型版本。Torch Hub 或指标模块仍可能需要已准备的代码 / 权重缓存；`doctor` 不覆盖所有间接缓存检查，缺少缓存时依实际日志补齐。

## 代码仓库和本地实验的边界

`.gitignore` 忽略环境、权重、缓存、构建输出、凭据、`runs/`、历史推理输出、演示报告包。源码中的上游示例图片 / 视频与小型 Data 输入仍可追踪。部署到另一台机器要准备环境和权重；复制详细离线报告到手机 / 电脑阅读则无需这些推理依赖，这是两个不同的使用场景。
