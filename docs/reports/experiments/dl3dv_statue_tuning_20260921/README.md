> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../Reports/dl3dv_statue_tuning_20260921/README.md)。本目录未复制视频或大型资产。

# 雕像场景：WorldWarp 三组实算调试（2026-09-21）

**结论：三组均已完成 225 帧生成和图像评分；前两组位姿评分完成，第三组位姿评分报错。三组均未达到接近论文效果的质量要求；不是成功 baseline。** 首段主体保留改善，后期仍有构图/视角偏差、模糊或几何遮挡。

[完整同步对比视频](../../../../Reports/dl3dv_statue_tuning_20260921/comparison.mp4)：2160×960、30 fps、225 帧、7.5 秒。上排 GT / 上次原版内参修正 / 上次标定相机 .8；下排本次滚动 .50 / 滚动 .35 / 固定首图几何 .35。

| 视频 | 配置 |
|---|---|
| [GT](../../../../Reports/dl3dv_statue_tuning_20260921/GT.mp4) | 相同的真实 225 帧 |
| [upstream_mean](../../../../Reports/dl3dv_statue_tuning_20260921/upstream_mean.mp4) | TTT3R 参考相机、滚动几何、strength .8 |
| [calibrated_s080](../../../../Reports/dl3dv_statue_tuning_20260921/calibrated_s080.mp4) | 标定相机、滚动几何、strength .8 |
| [calibrated_s050](../../../../Reports/dl3dv_statue_tuning_20260921/calibrated_s050.mp4) | 本次：标定相机、滚动几何、strength .50 |
| [calibrated_s035](../../../../Reports/dl3dv_statue_tuning_20260921/calibrated_s035.mp4) | 本次：标定相机、滚动几何、strength .35 |
| [first_image_s035](../../../../Reports/dl3dv_statue_tuning_20260921/first_image_s035.mp4) | 本次：标定相机、每段仅首图建模、strength .35 |

所有新视频均为 TTT3R → 原生 GS → WorldWarp；没有使用 MapAnything 或 GaME，没有微调视频模型。固定首图版本每段重新拟合 GS，生成历史仅用于上下文和文本，不是全局增量地图。标定相机/调参都是诊断协议，不能视为论文原版 .8 复现。

## 指标

| 配置 | 帧 | PSNR ↑ | SSIM ↑ | LPIPS ↓ | R_dist ↓ rad | t_dist ↓ |
|---|---:|---:|---:|---:|---:|---:|
| upstream_mean | 50 | 11.144 | 0.3580 | 0.5586 | 0.1627 | 0.1141 |
| upstream_mean | 200 | 11.066 | 0.4064 | 0.7157 | 0.2623 | 0.0737 |
| calibrated_s080 | 50 | 11.175 | 0.3618 | 0.5661 | 0.1935 | 0.1164 |
| calibrated_s080 | 200 | 10.972 | 0.4197 | 0.7512 | 0.1934 | 0.6119 |
| calibrated_s050 | 50 | 13.679 | 0.4514 | 0.4079 | 0.0308 | 0.0139 |
| calibrated_s050 | 200 | 12.246 | 0.4615 | 0.7411 | 0.1086 | 0.2653 |
| calibrated_s035 | 50 | 14.389 | 0.4677 | 0.3842 | 0.0319 | 0.0674 |
| calibrated_s035 | 200 | 12.214 | 0.4522 | 0.7804 | 0.1873 | 0.4137 |
| first_image_s035 | 50 | 14.240 | 0.4539 | 0.3807 | 0.0311 | 0.0647 |
| first_image_s035 | 200 | 11.330 | 0.4662 | 0.7714 | N/A | N/A |

单场景端点 FID 均为 N/A；全视频 FID 仅作诊断，不能与论文或五场景端点 FID 混比。像素指标来自编码前 PNG；R/t 使用独立 DUSt3R，退化图像的相机估计也可能不可靠。不能只按其中一个指标宣称成功。

| 配置 | 224 帧 FID（诊断） |
|---|---:|
| upstream_mean | 113.639 |
| calibrated_s080 | 113.775 |
| calibrated_s050 | 102.827 |
| calibrated_s035 | 115.385 |
| first_image_s035 | 131.513 |

第三组 DUSt3R 在第 200 帧窗口 PnP 初始化报 OpenCV point_coordinate_variance 断言；该端点 R/t 为 N/A，原运行 status.json 保留 failed，详细日志见 evidence/first_image_s035/pose_failure.log。

## 实际画面

![第 50 帧](../../../../Reports/dl3dv_statue_tuning_20260921/comparison_050.jpg)

![第 200 帧](../../../../Reports/dl3dv_statue_tuning_20260921/comparison_200.jpg)

![第 225 帧](../../../../Reports/dl3dv_statue_tuning_20260921/comparison_225.jpg)

- 滚动 .50/.35：首段保留雕像和基座比原 .8 更好；随段数增加，主体尺度、构图与背景仍偏移，后期模糊。
- 固定首图 .35：中期仍能保留雕像，但首图不可见区域缺少可信几何，背景补全错误；第 200 帧出现严重近处几何遮挡。
- 所有失败和完整轨迹均保留；没有更换成更短、更慢的轨迹，没有删失败帧，也没有使用后续真实 RGB/深度为生成补充场景观测。
- 本场景已用于反复调试，是开发案例，不是独立测试集。不同方法后续自动 caption 随自己的历史变化，不是严格固定文本的单因素实验。

## 参数、耗时与验证

共同参数：720×480、49 帧/段、5 段、后续上下文 5、GS 500 次、每来源最多 5 万点、采样 50 步、CFG 5、seed 32。标定平移沿用参考 TTT3R 轨迹拟合的正标量单位换算；目标旋转、内参和帧顺序不做事后调整。

| 本次运行 | 从 prepare 到完成/失败的墙钟时间 |
|---|---:|
| calibrated_s050 | 29.24 分钟 |
| calibrated_s035 | 29.24 分钟 |
| first_image_s035 | 23.04 分钟 |

三组部分并行，不能把单组耗时相加当作总墙钟时间。15 项 benchmark CPU 测试、11 项管线测试通过；三组各有真实完整视频生成、225 帧格式核验和实际加载权重核验；第三组评分流程失败，未冒称全流程成功。所有新数据集相机与 225 张 GT 配对逐项一致。固定首图分支五段实际目标索引去重后恰为 0–224，源图 ID 始终为 0。

原运行保留无损生成 PNG、每段最终 GS、caption、日志和配置；两组滚动版本另存被动深度/相机/渲染诊断，固定首图版本存实际几何请求。没有逐 GS 迭代模型或逐去噪 latent。报告媒体采用普通硬链接，复制整个报告目录即可离线观看；运行脚本仍需服务器模型与原数据。

[数值对照 JSON](../../../../Reports/dl3dv_statue_tuning_20260921/metrics_comparison.json)；[文件核验](../../../../Reports/dl3dv_statue_tuning_20260921/verification.json)。evidence/ 保存本次配置、评分、状态和质量验收记录；code/ 与 fixed_first_code/ 保存相应阶段源码快照。

本次没有找到已经验证能达到用户所需质量的完整修复。
