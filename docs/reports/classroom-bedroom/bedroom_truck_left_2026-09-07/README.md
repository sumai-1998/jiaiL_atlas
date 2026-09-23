> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/bedroom_truck_left_2026-09-07/README.md)。本目录未复制视频或大型资产。

# 卧室：匀速向左平移，4 段

视频：`bedroom_truck_left_4chunks_10.7s.mp4`

- 输入：`/data4/sumai/GIL_ATLAS/Data/bedroom.png`。
- 输出：H.264，480×608，30 fps，321 帧，10.7 秒，无音轨。
- 原图为 1320×1660，保持比例缩放并轻微中心裁切到 480×608；没有横向拉伸。
- 四段分别生成 81 帧，后三段各去掉 1 帧重叠后拼接。
- 预先构造完整直线轨迹：OpenCV c2w 相机 X 每帧减少 0.002 场景单位，Y/Z 不变、旋转为单位矩阵；总位移 0.64 场景单位。这不是经过标定的米制距离。
- 使用 `slice_chunk_trajectory` 提取正确的前段/当前段窗口，避免第三段起复用早期轨迹；完整轨迹没有分段重建或重新分配帧数。
- Strength 0.6，50 步扩散采样，每段 500 次 GS 优化，seed 32。
- 使用 GPU 0；生成耗时约 20.3 分钟，PyTorch 峰值分配显存约 33.2 GiB。

## 验证

4 项 CPU 轨迹回归检查通过，包括连续帧覆盖、上下文重叠和实际 GUI 预设/自定义方法的四段索引。

最终视频完整解码 321 帧，ffprobe 确认 10.700000 秒。三处拼接及首/中/尾帧已查看。特征跟踪的各段水平运动中位数均为正、垂直分量接近零，符合静态场景中相机左移的图像运动方向。

匀速指输入的相机条件；生成图像的像素速度并不严格恒定，光流也不是标定后的相机运动测量。后半段出现了少量新增墙面装饰，其他纹理也有生成变化，因此该输出不能视为原场景的精确几何真值。

- `report.json`：实际生成参数、各段路径、耗时、轨迹窗口。
- `requested_camera_trajectory.npz`：完整输入相机轨迹和内参。
- `inspection/contact_sheet.jpg`：关键帧与拼接处预览。
- `inspection/validation.json`：解码、拼接差异和特征跟踪记录。
- `inspection/ffprobe.json`：视频格式与帧数验证。
- `source_manifest.json`：运行源码及最终视频的 SHA-256。
- 完整日志：`/data4/sumai/GIL_ATLAS/setup_logs/bedroom_truck_left_2026-09-07.log`。

生成入口：`/data4/sumai/GIL_ATLAS/scripts/generate_worldwarp_translation.py`，使用 `conda_envs/worldwarp/bin/python`，运行环境与 `run_worldwarp.sh` 相同。输入参数如下：

```text
--image /data4/sumai/GIL_ATLAS/Data/bedroom.png
--output /data4/sumai/GIL_ATLAS/WorldWarp_outputs/新的输出目录
--chunks 4 --width 480 --height 608 --dx=-0.002
--strength 0.6 --gs-iterations 500 --seed 32
```
