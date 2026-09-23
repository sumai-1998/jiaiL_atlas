# WorldWarp 本地部署记录

更新时间：2026-09-05

## 当前状态

WorldWarp 已部署到可启动、可加载全部模型的状态：

- 源码：`/data4/sumai/GIL_ATLAS/WorldWarp`
- 上游提交：`0396b801c278546d01a6618a18e5a5c2a154c0a1`
- Conda 环境：`/data4/sumai/GIL_ATLAS/conda_envs/worldwarp`
- 一键启动脚本：`/data4/sumai/GIL_ATLAS/run_worldwarp.sh`
- Hugging Face 缓存：`/data4/sumai/GIL_ATLAS/hf_cache`

源码的两个 Git submodule（`fused-ssim` 和 `simple-knn`）均已拉取并编译。

## 启动

指定一张空闲 GPU 和端口：

```bash
CUDA_VISIBLE_DEVICES=1 GRADIO_SERVER_PORT=7891 \
  /data4/sumai/GIL_ATLAS/run_worldwarp.sh
```

浏览器访问：

```text
http://<服务器地址>:7891
```

如需进入环境调试：

```bash
conda activate /data4/sumai/GIL_ATLAS/conda_envs/worldwarp
cd /data4/sumai/GIL_ATLAS/WorldWarp
```

默认 7890 端口在部署验收时已被机器上的其他进程占用，所以启动脚本允许通过 `GRADIO_SERVER_PORT` 选择端口；未指定时仍使用 7890。

## 环境和模型

核心环境：

- Python 3.12.14
- PyTorch 2.7.1+cu126
- torchvision 0.22.1+cu126
- torchaudio 2.7.1+cu126
- flash-attn 2.8.3.post1
- PyTorch3D 0.7.9
- gsplat 1.5.3
- Gradio 5.49.1
- Open3D 0.19.0
- diffusers 0.35.1
- transformers 4.56.1

本地权重：

- `WorldWarp/ckpt/worldwarp_latest.ckpt`：约 2.65 GB
- `WorldWarp/src/ttt3r/cut3r_512_dpt_4_64.pth`：约 3.17 GB
- `WorldWarp/ckpt/Wan-AI/Wan2.1-T2V-1.3B-Diffusers`：完整 31 个文件，约 27 GB
- `WorldWarp/ckpt/Qwen/Qwen2.5-VL-7B-Instruct`：完整 16 个文件，约 15.5 GB

`WorldWarp/ckpt` 总计约 46 GB，CUT3R 权重约 3 GB。所有 Safetensors 分片都已逐个打开检查，目录内没有残留的 `.incomplete` 文件。

## 已完成的 GPU 验收

- FlashAttention、`simple-knn`、cuRoPE：真实 CUDA kernel 前向通过。
- TTT3R/CUT3R：两帧随机图像真实前向通过，产生有限值的深度、相机位姿和内参；峰值显存约 7.2 GiB。
- WorldWarp Wan Transformer：14.19 亿参数，项目 checkpoint `strict=True` 完整匹配；加载显存约 2.65 GiB。
- Wan VAE：完成 RGB → latent → RGB 的实际编解码，形状和数值均正常。
- Wan UMT5 文本编码器：完整加载成功，显存约 10.6 GiB。
- Qwen2.5-VL-7B：项目内的提示扩写类完成一次实际生成，峰值显存约 15.5 GiB。
- Gradio 全栈：在一张 RTX A6000 上同时加载所有模型成功，页面返回 HTTP 200；启动后显存约 17.7 GiB。
- 完整端到端：通过 Gradio API 上传仓库示例 `000.png`，执行 `PAN_LEFT_SLOW`、1 chunk、100 次 GS 优化；顺利完成 81 帧 TTT3R、5 万高斯训练、目标视角/mask 渲染、Wan 50 步采样和 MP4 合成。输出为 H.264、720×480、30 fps、81 帧。
- `pip check`：无依赖冲突。

端到端验收产物保存在：

```text
/data4/sumai/GIL_ATLAS/WorldWarp_outputs/smoke_test_2026-09-05/
```

其中包括 81 帧视频、对应的 5 万 Gaussian PLY、相机轨迹图、调度图、配置和 caption。中间帧已人工检查，不是空白帧或损坏视频。

这里的“可运行”指安装、checkpoint、编译扩展、各核心模型真实前向、完整 GUI 启动以及一段完整视频生成均已验收。尚未对不同分辨率、轨迹和多 chunk 长视频执行系统性的质量与吞吐 benchmark。

## 为可用性做的两个小修复

1. `pose_control.py`：官方默认把 Qwen2.5-VL checkpoint 送进 `AutoModelForCausalLM` 的文本分支，会导致模型类型不匹配，并被 GUI 捕获后静默关闭提示扩写。现在会读取 `model_type`，对 Qwen2.5-VL 使用正确的模型类；已做实际文本生成验证。
2. `gradio_demo.py`：把硬编码的 7890 改为支持 `GRADIO_SERVER_PORT`，避免共享服务器端口冲突。

这两处是工作树中有意保留的本地改动，可用以下命令查看：

```bash
cd /data4/sumai/GIL_ATLAS/WorldWarp
git diff -- gradio_demo.py pose_control.py
```

## 注意事项

- 上游仓库根目录当前没有 LICENSE 文件。虽然依赖项目各自有许可证，但在进一步分发、产品化或商用 WorldWarp 本体前，需要先向作者确认授权。
- 上游 README 提示完整生成约需 40 GB 显存。RTX A6000 具备 48 GB，但实际峰值仍随分辨率、帧数和配置变化。
- 第一次进入 GS rasterization 时，gsplat 会即时编译 CUDA 扩展；本次约耗时 127 秒，缓存完成后后续启动不会重复这一步。
- 不建议把 Conda 环境或几十 GB checkpoint 提交进 Git；部署脚本使用绝对路径指向本机资源。
