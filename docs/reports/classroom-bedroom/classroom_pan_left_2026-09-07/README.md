> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/classroom_pan_left_2026-09-07/README.md)。本目录未复制视频或大型资产。

# 教室：原地匀速向左旋转，4 段

视频：`classroom_pan_left_4chunks_10.7s.mp4`

- 输入：`/data4/sumai/GIL_ATLAS/Data/classroom.png`。
- 输出：H.264，480×608，30 fps，321 帧，10.7 秒，无音轨。
- 原图 1320×1681，保持比例缩放并轻微中心裁切到 480×608。
- 四段各生成 81 帧，后三段各去掉 1 帧重叠后拼接。
- 输入相机轨迹：OpenCV c2w 绕 Y 轴匀速左转，总计 -20°，每帧 -0.0625°（-1.875°/秒），所有相机位置均为原点。每段增加 5°，没有分段重置角度或加减速。
- Strength 0.6，50 步视频采样，每段 500 次 GS 优化，seed 32。
- GPU 0；总生成耗时约 20.1 分钟，PyTorch 峰值分配显存约 33.2 GiB。

## 验证

4 项 CPU 旋转检查通过：旋转矩阵正交性、位置固定与角速度恒定、左转投影方向、四段轨迹连续覆盖。

最终视频完整解码 321 帧；ffprobe 确认 10.700000 秒。首中尾帧与三处拼接已查看，教室主体保持连续，逐渐显露左侧区域。四段图像特征的水平运动中位数分别约为 0.638、0.620、0.676、0.660 像素/帧，方向均符合相机左转，速度较稳定。

匀速与角度描述的是输入相机条件；图像特征运动用于诊断，不等同于校准后的实际相机角速度。新显露区域与局部纹理由模型生成，未验证精确几何或墙面文字的一致性。

- `report.json`：实际参数、各段路径、耗时、轨迹窗口。
- `requested_camera_trajectory.npz`：完整相机轨迹和内参。
- `camera_trajectory.png`：角度随时间变化。
- `inspection/contact_sheet.jpg`：关键帧与拼接处预览。
- `inspection/validation.json`：解码、拼接差异和特征跟踪记录。
- `inspection/ffprobe.json`：格式与帧数验证。
- `sources/` 和 `source_manifest.json`：运行源码快照及 SHA-256。
- 完整日志：`/data4/sumai/GIL_ATLAS/setup_logs/classroom_pan_left_2026-09-07.log`。

生成入口：`/data4/sumai/GIL_ATLAS/scripts/generate_worldwarp_rotation.py`，使用 `conda_envs/worldwarp/bin/python`，环境设置与 `run_worldwarp.sh` 相同。参数：

```text
--image /data4/sumai/GIL_ATLAS/Data/classroom.png
--output /data4/sumai/GIL_ATLAS/WorldWarp_outputs/新的输出目录
--chunks 4 --width 480 --height 608 --total-angle-deg=-20
--strength 0.6 --gs-iterations 500 --seed 32
```
