> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/README.md)。本目录未复制视频或大型资产。

# 教室左转：三组参数对照

三组均已完整生成并验证：480×608、30 fps、321 帧、四段拼接共 10.7 秒，输入相机原地匀速左转 20°。原图、轨迹、内参、seed 32、50 步采样、提示词和 MapAnything/GaME 几何产物保持一致。

这轮更值得优先查看 **strength 0.6、5 帧上下文**：保真度小幅提升，三处接缝的运动补偿误差均下降。它仍没有解决所有新区域和文字失真，不能说全面超过原版。

## 视频

| 新版本 | 成片 | 与上一版串联结果并排比较 |
| --- | --- | --- |
| strength 0.6，上下文 5 帧 | [视频](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/context_5/classroom_pan_left_4chunks_10.7s.mp4) | [左上一版，右新版本](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/comparisons/context_5/classroom_side_by_side_10.7s.mp4) |
| strength 0.5，上下文 1 帧 | [视频](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/strength_050/classroom_pan_left_4chunks_10.7s.mp4) | [左上一版，右新版本](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/comparisons/strength_050/classroom_side_by_side_10.7s.mp4) |
| strength 0.65，上下文 1 帧 | [视频](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/strength_065/classroom_pan_left_4chunks_10.7s.mp4) | [左上一版，右新版本](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/comparisons/strength_065/classroom_side_by_side_10.7s.mp4) |

[五版本同步总览](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/overview/classroom_five_versions_10.7s.mp4)（1440×1312，约 54 MB）：上排为单独 WorldWarp、上一版串联、5 帧上下文；下排为 strength 0.5、strength 0.65、原图的解析投影参考。参考图黑色区域表示原图未覆盖，属于有意保留的参考标记。

[指标曲线](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/overview/metric_curves.png) · [8 秒细节对比](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/overview/details_240.jpg) · [末帧细节对比](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/overview/details_320.jpg) · [指标 CSV](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/overview/metrics.csv) · [完整 JSON](../../../../WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/overview/metrics.json)

## 结果与取舍

下表均从最终拼接 MP4 计算，数值越高/越低的方向在列名注明。保真度只评估原图可见区域，不包含新显露区域的外观质量。

| 版本 | 已知区域 PSNR ↑ | 已知区域 SSIM ↑ | 全片运动补偿帧间误差 ↓ | 最后一处接缝误差 ↓ |
| --- | ---: | ---: | ---: | ---: |
| 单独 WorldWarp | 20.67 dB | 0.692 | 1.529 | 3.716 |
| 上一版串联：0.6 / 1 帧 | 23.94 dB | 0.765 | 1.636 | 4.204 |
| 本轮：0.6 / 5 帧 | 24.27 dB | 0.783 | 1.527 | 3.394 |
| 本轮：0.5 / 1 帧 | 25.20 dB | 0.804 | 1.506 | 3.546 |
| 本轮：0.65 / 1 帧 | 22.93 dB | 0.731 | 1.697 | 4.083 |

- **5 帧上下文**：相比上一版串联，平均 PSNR 提高 0.33 dB，全片帧间误差降低 6.7%；三处接缝分别降低 9.5%、18.3%、19.3%。原图外区域的平均运动补偿误差从 1.367 降为 1.235，约降低 9.7%。本轮结果较均衡，但末段新区域的墙面纹理和部分桌椅仍有明显生成改写，文字依然失真。
- **strength 0.5**：已知区域的 PSNR/SSIM 最好，但从中段到末段，新显露的左侧出现明显暖色雾状模糊与淡化的桌椅。它的帧间误差也较低，不能把这种低误差直接视为视觉质量最好。
- **strength 0.65**：新区域相比 0.5 看起来更实，但相对上一版串联，原图结构保留和全片帧间误差均变差。本轮不建议把它作为这张图片的默认设置。

已检查首中尾、三处接缝关键帧和墙面/桌椅局部放大图。原图外区域没有真实参考，指标只能诊断连续性，不能证明补全内容正确。模糊、平坦纹理同样可能降低帧间误差；上述推荐综合了指标与关键帧观察，而不是单一分数排序。

## 5 帧上下文如何保持时长

首段仍生成 81 帧、使用 1 帧输入条件。后三段内部各处理 85 帧，其中前 5 帧条件来自上一段真实末尾画面。例如第二段内部目标为全局帧 76–160，条件为 76–80；在编码前去掉多出的前 4 帧，交付的分段仍为 80–160 共 81 帧。最终拼接再去掉一帧重叠，总长度保持 321 帧。

这没有对最终视频插帧、减速或重复画面。用于扩展原函数输入长度的前缀复制不进入历史条件；实际送入 VAE 的历史条件是上一段真实末尾 5 帧。原始 85 帧输出另保存在 `context_5/artifacts/*/raw_context_chunks/`，实际注入记录保存在实验目录的 `geometry_bridge_calls.json`。

四项窗口检查通过：实际历史帧对应关系、拼接后无缺失/重复时间、1 帧设置与原窗口一致、拒绝不符合 VAE 时间对齐的上下文数。5 帧组第一段的全部 81 帧与上一版逐像素一致，最大差值为 0，见 `context_first_chunk_control.json`。

5 帧组使用同一初始随机种子，但更长的内部窗口改变了潜变量形状及后续噪声的分配位置。这是保持同一最终时间网格时的上下文实验，不是逐像素相同噪声的对照；本轮每组只跑一个种子。

## 记录与复现

三组复用上一轮已经计算的 MapAnything 深度、GaME 检查点和 321 帧 RGB/alpha 渲染，每组完整重新生成四段 WorldWarp 视频。具体产物路径及 SHA-256 见 `reused_geometry_manifest.json`。本轮没有测试深度过滤、GaME 迭代次数或掩码腐蚀等其他参数，也没有新增世界反馈更新。

`configuration_checks.json` 证明每组配置仅改变了预定参数及输出目录。实际时间、显存、视频校验值见 `generation_validation.json`；三组视频阶段分别约 17.7、17.8、18.3 分钟，峰值 PyTorch 分配显存约 23.1 GiB，使用 GPU 1、2、0。运行完成后三张 GPU 均已释放。

成片与对比视频均已验证为 321 帧、10.7 秒。各版本 `inspection/` 内有解码检查、运动诊断、关键帧和 ffprobe 记录；`comparisons/` 内有逐帧指标和并排 MP4；`overview/` 另有对原图内外区域分别计算的帧间指标。保真度排除条件帧 0；新区域统计排除有效区域少于 128 像素的帧，两侧都使用 15×15 核腐蚀边界。

源码快照位于 `sources/`，校验值位于 `source_manifest.json`。完整日志在 `logs/`。在确认三张指定 GPU 可用后，用新的绝对输出目录复现：

```bash
cd /data4/sumai/GIL_ATLAS
WORLDWARP_TUNING_GPUS=0,1,2 bash WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/reproduce.sh /data4/sumai/GIL_ATLAS/WorldWarp_outputs/新的调参目录
```

复现入口的 shell 语法检查已通过；本次已实际执行其中对应生成、比较和汇总命令，未额外重复整轮生成。
