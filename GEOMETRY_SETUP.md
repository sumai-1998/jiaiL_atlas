# Atlas 几何回写模块：本地安装与使用

安装日期：2026-09-06 至 2026-09-07。**已完成安装、权重下载校验与小样本 GPU 验证。** 完整清单见 `setup_logs/geometry_install/manifest.json`。

## 安装范围

对应现有系统图和开源组装图中的这一段：

`RGB 图像（真实观测 / GS 渲染 / 生成候选） → MapAnything → pointmap + depth + K + pose → GaME → 持久化 GS 场景 → 再渲染`

这里落实的是两个项目及最小本地适配器，不是声称复现了 Atlas 的官方内部实现。RGB 来源不同不改变张量接口，但会改变几何可靠性；生成 / 渲染候选不是新的真实观测。

| 组件 | 本地位置 | 功能 |
|---|---|---|
| [MapAnything](https://github.com/facebookresearch/map-anything) | `MapAnything/` | 多视角 RGB 推理 pointmap、深度、相机内外参；支持几何条件输入 |
| [GaME](https://github.com/VladimirYugay/GaME) | `GaME/` | 接收有位姿的 RGB-D 和实例掩码，增补、优化、删除 Gaussians，保存场景 |
| Open3D 0.19.0 | 两个 Conda 环境内 | 点云操作、RGB-D 反投影、导出与体素合并 |
| gsplat 1.5.3 | MapAnything 环境内 | 独立的可微 GS 渲染工具；GaME 核心仍用自己的 FlashSplat rasterizer |
| 三个本地 CUDA 扩展 | GaME 环境内 | `diff_gaussian_rasterization`、`flashsplat_rasterization`、`simple_knn` |
| Faiss GPU 1.8.0 | GaME 环境内 | GPU 最近邻检索；按上游安装建议配齐，不是该快照核心建图路径的必需 import |

没有安装 HY 初始化器、Spatia 视频生成、SAM3 或 4D 动态分支。本轮目标是几何回写部分；SAM3 的访问授权也没有被自动申请。

## 两个独立 Conda 环境

工作根目录：`/data4/sumai/GIL_ATLAS`

| 环境 | Python | PyTorch | NumPy | 激活路径 |
|---|---|---|---|---|
| MapAnything | 3.12.14 | 2.5.1+cu124 | 2.2.6 | `/data4/sumai/GIL_ATLAS/conda_envs/mapanything` |
| GaME | 3.10.21 | 2.5.1+cu124 | 1.26.4 | `/data4/sumai/GIL_ATLAS/conda_envs/game` |

二者不能直接合并成同一个环境：MapAnything 的 Rerun 0.24.1 要求 NumPy 2，而旧 Faiss 的 Python 绑定需要 NumPy 1。通过普通 NPZ / PLY 文件交换，不跨环境传递 Python 对象。

```bash
conda activate /data4/sumai/GIL_ATLAS/conda_envs/mapanything
# 或
conda activate /data4/sumai/GIL_ATLAS/conda_envs/game
```

CUDA 扩展使用本机 `/usr/local/cuda-12.4` 与 GaME 环境中的 GCC / G++ 12.4 编译，目标为本机 A6000 的 `sm_86`。PyTorch 自带 cu124 运行库，不要求修改系统默认 CUDA，也没有修改原有 WorldWarp 环境。

## Checkpoint 与缓存

| 用途 | 位置 | 大小 / 说明 |
|---|---|---|
| MapAnything 默认权重 | `checkpoints/mapanything/model.safetensors` | 4,914,062,480 bytes，CC-BY-NC-4.0 |
| MapAnything Apache 权重 | `checkpoints/mapanything-apache/model.safetensors` | 4,914,062,480 bytes，Apache-2.0 |
| 每个模型的下载核验记录 | 对应目录的 `local_manifest.json` | 固定 HF revision、完整 SHA-256、tensor 数与形状 |
| DINOv2 代码缓存 | `.cache/torch_geometry/hub/facebookresearch_dinov2_main/` | 为 MapAnything 的 Torch Hub 依赖预缓存源码；完整 MapAnything 权重已含 encoder 参数，不再重复下载 DINOv2 大权重 |
| LPIPS 的 AlexNet 权重 | `.cache/torch_geometry/hub/checkpoints/alexnet-owt-7be5be79.pth` | GaME 图像指标所用，不是 GS 生成模型 |

GaME **没有一个通用的预训练“RGB → 场景 GS” checkpoint**。它从当前输入初始化、优化自己的 Gaussians，生成的 `checkpoints/checkpoint.pth` 是当前场景的状态。不要把这个场景状态与 MapAnything 的预训练权重混为一谈。

默认权重的 SHA-256：`981f060c64664dff3272b5f5a823d350abe71a2f144444db4cfc325f3ed5a3a0`。

Apache 权重的 SHA-256：`fa06c0fdccefc5048e072c85935d5789b1e36b307f3859033c17f9dcb9fd5201`。

GaME 主仓库与其第三方 rasterizer 的许可证并不等价；包含 Inria 派生的非商业研究用途代码。需要商用时，应逐项核对，不能因为替换成 Apache MapAnything 权重就认为整条链路可商用。

## 最小使用方法

无需激活环境，包装脚本会使用正确的 Python。以下 GPU 编号只是本次测试示例；运行前自行检查 `nvidia-smi`，并替换为当时空闲的 GPU。

### 1. 图像转 pointmap / 融合点云

```bash
cd /data4/sumai/GIL_ATLAS
CUDA_VISIBLE_DEVICES=5 ./run_mapanything.sh \
  --images /absolute/path/to/images \
  --output /data4/sumai/GIL_ATLAS/geometry_outputs/my_scene/geometry \
  --source-kind rendered --max-views 8
```

可将 `--images` 改为多个图像文件；`--variant apache` 切换 Apache 权重。`--source-kind` 按真实来源选择 `observed`、`rendered` 或 `generated`。

输出：

- `pointmaps.npz`：逐帧世界坐标 pointmap 与有效掩码。
- `posed_rgbd.npz`：RGB、z-depth、有效掩码、K、OpenCV c2w、置信度。
- `pointcloud_fused.ply`：在该次联合推理的共享坐标系内，按默认 0.02 场景单位体素合并的彩色点云。
- `report.json`：输入来源、有效点数、耗时、显存等。

此处的点云“融合”是共享坐标系下的体素聚合，不是跨独立推理批次的回环优化或长期 SLAM。尺寸 / scale 由模型预测，尚未用真实标定验证。批次内导出要求处理后的图像尺寸一致。

### 2. RGB-D 融合为 GS 场景

```bash
CUDA_VISIBLE_DEVICES=5 ./run_game.sh \
  --rgbd /data4/sumai/GIL_ATLAS/geometry_outputs/my_scene/geometry/posed_rgbd.npz \
  --output /data4/sumai/GIL_ATLAS/geometry_outputs/my_scene/gs \
  --max-views 3 --max-width 224 --iterations 20
```

这是安装验证 / 静态场景适配入口，默认尺寸和迭代数刻意较小。GaME 原生代码每个关键帧还会执行 50 次 warmup；`--iterations` 不是该帧的总迭代数。

输出：`gaussians.ply`、`checkpoints/checkpoint.pth`、`configs.json`、各视角 `render_*.png` 与 `report.json`。脚本还会重新加载保存的场景 checkpoint 检查 GS 数量。

当前适配器每帧使用一个全图静态 mask，**不是自动实例分割或运动分割**。真实动态 / 多时段场景应换成实例掩码，并校准深度变化阈值。原生数据集入口仍保留在 `GaME/run.py`。

### 一个必须保留的接口校准

统一中间文件使用 **OpenCV c2w**，进入 GaME 前必须执行 `w2c = inverse(c2w)`。

GaME 当前源码的部分注释写了 c2w，但其实际数据加载器、RGB-D 反投影和渲染实现使用的是 **w2c**。本地适配器遵循可执行代码，显式转换；没有为迎合错误注释而改动上游实现。

另外，GaME 原生相机助手把主点默认为居中。`scripts/game_camera_adapter.py` 在本地适配器进程内替换这个助手，使用完整零 skew 的 K，并匹配 rasterizer 的半像素映射；没有改动上游源文件。解析投影测试与直接 OpenCV 投影的最大差异为 `3.82e-6` 像素。该数值只证明坐标接口一致，不证明模型预测准确。

## 验证记录

本机 GPU 5，NVIDIA RTX A6000。两个环境均通过 `pip check`；gsplat 通过 CUDA 前向 / 反向；GaME 三个 CUDA 扩展可用，simple-knn 和 Faiss 完成 GPU 运算，LPIPS / AlexNet 对相同图像的结果为 0。

新测试根目录：`geometry_outputs/install_smoke_2026-09-07/`。没有覆盖之前的 WorldWarp 输出或图示。

| 测试 | 输出子目录 | 实测结果 |
|---|---|---|
| 三帧解析 RGB-D → GaME | `game_fixture/` | 15,297 个 GS；3 个关键帧；渲染与 checkpoint 重载通过 |
| 三帧既有 WorldWarp 图像 → 默认 MapAnything | `mapanything_default/` | 84,245 个合并点；518×336；端到端 34.43 秒；PyTorch 峰值分配显存 7.24 GiB |
| 上述预测 RGB-D → GaME | `game_worldwarp/` | 18,991 个 GS；后续两帧分别新增 2,843 / 1,712 个 seeds，再经优化 / 剪枝 |
| 上述 GS 的三帧渲染图 → Apache MapAnything | `mapanything_apache_rendered/` | 52,992 个合并点；端到端 28.18 秒；PyTorch 峰值分配显存 7.24 GiB |
| 渲染图重建得到的 RGB-D → 新 GaME 场景 | `game_from_rendered/` | 18,968 个 GS；后续两帧新增 2,877 / 1,517 个 seeds；渲染与 checkpoint 重载通过 |

因此已经实际执行了 **GS 渲染图 → pointmap / posed RGB-D → 多帧 GS 融合 → 新场景导出 / 再渲染**，不只测试 import。三个 GaME 测试均使用 20 次额外优化 + 每帧原生 50 次 warmup、低分辨率输入；它们是安装验证，不是质量或速度基准。

第二轮创建了独立场景，用来验证渲染图确实可走通这段管线；**没有将两次 MapAnything 独立推理的坐标直接合并为一个长期世界**。这也不是已经跑通完整 Atlas AR 循环。

每个目录有 `report.json`；GS 目录有 `gaussians.ply`、`render_000.png` 至 `render_002.png`、`checkpoints/checkpoint.pth`。可优先查看 [最终渲染图](geometry_outputs/install_smoke_2026-09-07/game_from_rendered/render_001.png) 和 [最终 GS](geometry_outputs/install_smoke_2026-09-07/game_from_rendered/gaussians.ply)。

## 可复现记录

`setup_logs/geometry_install/` 保存两个环境的 Conda explicit 清单、pip freeze、源码 commit 和测试汇总。约束文件分别是 `scripts/mapanything_constraints.txt`、`scripts/geometry_constraints.txt`。pip freeze 是审计清单，不应脱离 Conda 环境直接安装其中的 Conda-only Faiss 条目。

固定源码：MapAnything `3d10cf7a3016fc0f9bb13a071ee66c47b10be0d9`；GaME `1c971d65d29952789fa4a2ebb342580d41acbbff`；DINOv2 代码缓存 `7764ea0f912e53c92e82eb78a2a1631e92725fc8`。GaME 上游跟踪了部分 simple-knn 编译缓存 / object 文件，本地编译重建了它们；算法源文件未修改。

三个本地 CUDA 扩展编译后的 wheel 保存在 `setup_logs/geometry_wheels/`，适用于本次 Python 3.10、PyTorch 2.5.1、CUDA 12.4、A6000 环境，不作为跨平台通用 wheel。

模型下载 / 校验入口：`scripts/download_geometry_ckpts.py`。环境检查入口：`scripts/check_geometry_env.py`。安装清单生成入口：`scripts/snapshot_geometry_install.py`。

## 接回完整 Atlas 假设框架前还需要什么

这一安装提供了可运行的几何重建和 GS 写回基础。完整循环仍需实现：固定世界坐标锚、跨批次尺度 / 位姿对齐、可见性与新增区域判断、生成候选的置信度审核、旧资产保护和版本回退。新图像应与相邻历史关键帧联合重建；不能把每个独立批次的预测坐标直接拼到同一个世界中。

GaME 当前直接使用输入 pose，没有自动替你完成相机跟踪和回环。动态时间建模也不在本次静态适配器的验证范围内。
