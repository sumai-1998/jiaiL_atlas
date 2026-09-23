> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../presentations/atlas_four_chapter_polished_2026-09-07/WorldWarp_本地部署与演示.md)。本目录未复制视频或大型资产。

# 第四章配套：WorldWarp 本地部署与演示

配合 PPT 第 22–26 页使用。这里说明的是已存在的部署与实验；本次制作 PPT 没有重新启动服务、运行 GPU 生成或安装模型。

## 先讲清输入与输出

输入一张起始图，并指定相机轨迹、生成段数、分辨率与生成设置。WorldWarp 先利用几何预测、局部 GS 优化和目标视角渲染建立条件，再生成新视角视频。继续多段时会利用已有视频历史。

最终留下三类东西：

- 视频与关键帧：用于观察生成效果。
- 每段局部 GS、轨迹与渲染中间量：用于检查几何条件。
- 输入、参数、日志和源码快照：用于追溯与复现。

局部 GS 缓存不是四段新增内容已完整融合后的全局场景，输出视频也不自动等于可自由查询的 4D 资产。

## 本地部署在哪里

| 项目 | 路径 / 记录 |
|---|---|
| 源码 | `/data4/sumai/GIL_ATLAS/WorldWarp` |
| 独立 Conda | `/data4/sumai/GIL_ATLAS/conda_envs/worldwarp` |
| GUI 入口 | `/data4/sumai/GIL_ATLAS/run_worldwarp.sh` |
| 精确连续旋转入口 | `/data4/sumai/GIL_ATLAS/scripts/generate_worldwarp_rotation.py` |
| 环境与原始验收 | [WORLDWARP_SETUP.md](../../archive/WORLDWARP_SETUP.md) |

既有环境记录为 Python 3.12.14、PyTorch 2.7.1+cu126；启动脚本使用本地 CUDA 12.8 路径。WorldWarp 微调权重、Wan2.1-T2V-1.3B、TTT3R/CUT3R 几何权重和 Qwen2.5-VL-7B 均已有部署验收记录。本次没有重新加载全部模型验证环境。

## 交互启动

先检查资源，不要假定此前使用的 GPU 和端口仍为空闲：

```bash
nvidia-smi
ss -ltn
```

以下 GPU 0、7891 只是示例，确认可用后再执行：

```bash
cd /data4/sumai/GIL_ATLAS
CUDA_VISIBLE_DEVICES=0 GRADIO_SERVER_PORT=7891 ./run_worldwarp.sh
```

浏览器进入 `http://<服务器地址>:7891`，上传起始图，选择预设或自定义相机运动，设置生成参数后运行。更改端口不会影响生成方法。执行入口会选取已有 Conda 环境，不必先把多个项目的环境混装在一起。

## 本次 PPT 采用的真实教室案例

| 内容 | 已有记录 |
|---|---|
| 输入 | `Data/classroom.png`，1320×1681 |
| 预处理 | 保持比例缩放、轻微中心裁切至 480×608 |
| 相机控制 | 位置不动，OpenCV c2w 绕 Y 轴匀速左转，总计 −20° |
| 视频生成 | 4 段，每段 81 帧；后三段各去掉 1 帧重叠 |
| 最终输出 | H.264，480×608，30 fps，321 帧，10.7 秒，无音轨 |
| 参数 | strength 0.6，视频采样 50 步，每段 GS 优化 500 次，seed 32 |
| 实际运行记录 | 总耗时约 20.1 分钟；PyTorch 峰值分配显存约 33.2 GiB |

帧数为 `81 + 3 × 80 = 321`。−20° 和匀速是输入控制条件，不是从输出测出的标定相机真值。显存数字是该次 PyTorch 分配峰值，不是进程总显存，也不是其他设置的显存上限。

[独立视频](../../../../presentations/atlas_four_chapter_polished_2026-09-07/assets/WorldWarp_classroom_4chunks_10.7s.mp4) 已随 PPT 复制；第 24 页内嵌相同字节的 MP4，PDF 展示第 160 帧。当前环境没有实际测试 Office 播放，可单独用视频播放器演示。

## 重新运行相同案例的命令参考

以下只是可复制说明，本轮没有执行。先确认 GPU 0 可用，并为 `--output` 选择尚不存在的新目录；脚本会拒绝已有目录。该脚本的正向提示写的是教室场景，直接换其他图片时也应检查和调整提示，不能把它当成完全通用的场景命令。

```bash
cd /data4/sumai/GIL_ATLAS

export PYTHONNOUSERSITE=1
export HF_HOME=/data4/sumai/GIL_ATLAS/hf_cache
export HF_HUB_CACHE="${HF_HOME}/hub"
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,${NO_PROXY:-}"
export no_proxy="${NO_PROXY}"

CUDA_VISIBLE_DEVICES=0 /data4/sumai/GIL_ATLAS/conda_envs/worldwarp/bin/python \
  /data4/sumai/GIL_ATLAS/scripts/generate_worldwarp_rotation.py \
  --image /data4/sumai/GIL_ATLAS/Data/classroom.png \
  --output /data4/sumai/GIL_ATLAS/WorldWarp_outputs/classroom_pan_left_repeat_new \
  --chunks 4 \
  --width 480 \
  --height 608 \
  --total-angle-deg=-20 \
  --strength 0.6 \
  --gs-iterations 500 \
  --seed 32
```

脚本构造完整连续相机轨迹，再按段提取正确窗口；不是在每个 chunk 重新从零角度起步。`--width` 和 `--height` 必须为 16 的倍数，当前入口只允许 −90° 到 0° 之间的左转角度。使用相同 seed 与参数也不承诺跨软硬件逐像素完全复现；原案例的运行源码快照比事后工作树更适合用于精确溯源。

## 原始产物与验证

原始目录：[classroom_pan_left_2026-09-07](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/README.md)。

- [report.json](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/report.json)：状态、实际参数、分段时间与轨迹窗口。
- [requested_camera_trajectory.npz](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/requested_camera_trajectory.npz)：相机内参与完整轨迹。
- [inspection/validation.json](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/inspection/validation.json)：完整解码、接缝与运动诊断。
- [inspection/contact_sheet.jpg](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/inspection/contact_sheet.jpg)：关键帧与三处拼接预览。
- [source_manifest.json](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/source_manifest.json)：运行源码快照与 SHA-256。
- 每段 GS：`artifacts/2026-09-07_23-12-07/warped_images/chunk_000_3dgs.ply` 至 `chunk_003_3dgs.ply`。

已存在的检查覆盖旋转矩阵、固定位置 / 恒定角速度、左转投影方向、四段轨迹连续覆盖，以及 321 帧完整解码和三处拼接。本次制作另外读取 ffprobe 元数据并核对内嵌视频字节。未额外做新的生成质量 benchmark、几何真值对齐或完整 4D 验证。

## 讲回总体架构时怎样收尾

一句话：WorldWarp 已经给出可运行的几何引导生成起点；MapAnything 与 GaME 提供几何前端、地图后端的另一种组合基础。

下一阶段只聚焦一件事：固定时间，让两轮相机探索读写同一个世界。

1. 从持久 GS 地图渲染 WorldWarp 所需的几何条件。
2. 新帧与历史重叠帧联合重建，锚定同一坐标系。
3. 将可信候选写回同一 GaME 场景，第二轮真正读取第一轮新增内容。

这三项完成后，再扩展长程回看、资源预算、动态层与时间查询。当前四段视频和已通过的几何子链路，是这条复现路线的起点，不是这三个接口已经接通的证据。
