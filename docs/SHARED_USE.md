# 同一服务器的多用户复用

推荐共享现有代码、Conda 环境和权重，由维护者更新；每个用户使用自己的输入、运行输出和编译缓存。无需重复下载模型或重新创建三套环境。

本机共享根目录是 `/data4/sumai/GIL_ATLAS`。以下命令由使用者以自己的 Linux 账号执行，不需要切换到 `sumai` 账号。

## 直接使用管线

共享启动器会选择现有解释器，不必先执行 `conda activate`。它保留调用者的当前工作目录，因此相对输入、输出路径按调用者的位置解释。

```bash
gil_root=/data4/sumai/GIL_ATLAS
gil_launcher="$gil_root/scripts/shared_pipeline.sh"

bash "$gil_launcher" list
bash "$gil_launcher" describe G

# 只创建输出的父目录，不预先创建此次运行目录。
mkdir -p "$HOME/GIL_ATLAS_runs"
gil_output="$HOME/GIL_ATLAS_runs/classroom_G_$(date +%Y%m%d_%H%M%S)"

bash "$gil_launcher" plan --pipeline G \
  --input "$gil_root/Data/classroom.png" --output "$gil_output"
bash "$gil_launcher" doctor --pipeline G \
  --input "$gil_root/Data/classroom.png" --output "$gil_output"

nvidia-smi
# 将 GPU_ID 替换为检查后选定的空闲 GPU 编号。
bash "$gil_launcher" run --pipeline G \
  --input "$gil_root/Data/classroom.png" --output "$gil_output" --gpu GPU_ID

bash "$gil_launcher" status "$gil_output"
```

自己图片的路径可直接传给 `--input`。输出也可以放在自己有写权限的数据盘目录；完整中间结果可能很大，运行前检查磁盘空间和配额。不要把其他用户的输出指向维护者的 `runs/`：该目录不向其他账号开放写权限。

管线 ID、平移/旋转区别及参数见 [PIPELINES.md](PIPELINES.md)。共享启动器只改变运行缓存的位置，不改变模型、相机、随机种子或采样参数。

论文评测仍使用同一入口下的 `benchmark` 子命令，例如：

```bash
bash "$gil_launcher" benchmark doctor \
  --manifest "$gil_root/runs/dl3dv_worldwarp_eval2_20260916_142500/selected_manifest.json" \
  --count 2 --output "$HOME/GIL_ATLAS_runs/benchmark_NEW_RUN" --gpu GPU_ID
```

同样先 plan、doctor，再用相同参数 run。GPU_ID 和 NEW_RUN 是占位符。DL3DV 源数据位于另一个用户的数据目录，还需确保使用者对清单中每个 `shard_path` 有读取权限；项目环境的共享不等于数据目录已获授权或已通过读取检查。

## 只使用某个 Conda 环境

已初始化 Conda 的用户可按绝对路径激活，不要求环境出现在自己的 `conda env list` 中：

```bash
conda activate /data4/sumai/GIL_ATLAS/conda_envs/worldwarp
python -c 'import torch; print(torch.__version__)'
```

另外两套环境分别为：

```text
/data4/sumai/GIL_ATLAS/conda_envs/mapanything
/data4/sumai/GIL_ATLAS/conda_envs/game
```

也可直接调用 `.../bin/python`。独立运行项目脚本时仍需自行设置源码路径、CUDA 工具链和缓存，所以执行现有管线优先使用共享启动器。Conda 的路径激活方式见[官方环境管理文档](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html#specifying-a-location-for-an-environment)。

## 权限、缓存与维护约定

| 内容 | 维护者 | 其他使用者 |
|---|---|---|
| 共享源码、三套环境、已下载权重 | 维护、更新 | 读取、执行 |
| 每个人自己的输出目录 | 由目录拥有者决定 | 各自写入 |
| 运行与编译缓存 | 各自拥有 | 各自写入，不混用 |
| 新依赖或实验性代码修改 | 更新共享版本或单独建环境 | 在个人环境/个人 checkout 中进行 |

2026-09-16 的本机检查发现，三套环境内文件具备其他用户读取权限，主要入口目录具备遍历权限。原 `WorldWarp/src/ttt3r/cut3r_512_dpt_4_64.pth` 为 `600`，已仅为这个公开预训练权重补齐读取权限至 `644`，没有开放共享环境的写权限。

`doctor` 现在检查配置项的存在、读取权限及解释器的执行权限；它仍不能代替完整模型加载和 CUDA 推理验证。权限、ACL、设备访问和配额以使用者自己的账号实际检查为准。

共享启动器默认设置：

```text
GIL_RUNTIME_CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/gil_atlas
```

统一运行器在其下按 `worldwarp`、`mapanything`、`game` 分开创建 Torch 扩展、Inductor、Triton、CUDA、HF 动态模块和 Matplotlib 缓存。新建的具体缓存目录权限为 `700`。启动器关闭用户 site-packages 和源码字节码写入，减少个人 Python 包干扰共享环境。

磁盘空间不足时可指定自己的缓存目录：

```bash
export GIL_RUNTIME_CACHE=/自己有写权限的目录/gil_atlas_cache
bash "$gil_launcher" doctor --pipeline G \
  --input "$gil_root/Data/classroom.png" --output "$gil_output"
```

模型缓存 `hf_cache/`、`.cache/torch_geometry/` 仍指向项目内已准备的共享资源，推理维持离线设置。新增模型或缺失缓存由维护者准备，不给所有用户开放整个环境、权重目录的写权限。第一次使用自己的编译缓存可能需要重新编译部分 CUDA 扩展。

共同开发时，各自 clone/checkout 仓库，通过分支和 PR 合并。修改依赖时创建个人环境；不要向共享环境执行 `pip install` 或 `conda install`。MapAnything 当前是 editable 安装，映射到本共享源码目录；需要修改自己的 MapAnything 源码时，在个人环境中重新安装自己的 checkout。仅克隆环境不会自动消除这类源码路径引用。

维护者升级共享依赖或切换共享源码版本前，先确认没有其他用户正在使用该版本运行任务。

保留现有部署路径。移动环境或直接复制到另一位置需要重新验证绝对路径、editable 安装和 CUDA 扩展，不能将“同机按原路径复用”等同于“任意迁移”。维护方式可参考 [Conda 多用户安装说明](https://docs.conda.io/projects/conda/en/stable/user-guide/configuration/admin-multi-user-install.html)。

## 本次验证范围

- 已检查三套环境、主要源码、权重与共享缓存的权限位；没有在环境中发现指向仓库外的软链接。
- 共享入口、相对路径与带特殊字符的参数转发、按环境隔离缓存、不可读权重拦截，以及原管线/评测 CPU 测试已验证。
- 三套解释器的 PyTorch、项目主要模块和已安装扩展导入，以及小型 CPU 张量运算已通过；未调用 CUDA 核函数或加载完整模型。
- 当前账号验证不能代替其他 Linux 账号的实际访问测试；本次没有冒用其他账号或重新运行长视频。
