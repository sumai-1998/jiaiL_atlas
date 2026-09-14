# 历史实验与统一入口的关系

这里记录本地已运行过的组合，不把新写的命令路由本身称为新一轮质量实验。原始完整实验输出在服务器 `WorldWarp_outputs/`，没有上传 Git。

| 历史标签 | 当前 ID | 本地证据目录 |
|---|---|---|
| 原版 bedroom 左平移 | `ww-translate` | bedroom 左移实验及 `generate_worldwarp_translation.py` |
| A classroom 原版左转 | `ww-rotate` | `classroom_pan_left_2026-09-07/`、9 月 14 日 `original/` |
| B Map → GaME → WW | `map-game-ww` | `classroom_hybrid_pan_left_2026-09-07/video/` |
| C 5 帧连续上下文 | `map-game-ww-ctx5` | `classroom_hybrid_tuning_2026-09-08/context_5/` |
| D strength .50、ctx1 | `map-game-ww-s050` | 同上 `strength_050/` |
| E strength .65、ctx1 | `map-game-ww-s065` | 同上 `strength_065/` |
| F 滚动几何 + 原生 GS | `map-ww-gs` | `classroom_worldwarp_mapanything_2026-09-08/rolling_gs/`、9 月 14 日重跑 |
| G 原图约束 + 原生 GS | `map-ww-anchor-gs` | 同上 `anchor_gs/`、9 月 14 日重跑 |
| H 原图约束 + 点云 | `map-ww-anchor-points` | 同上 `anchor_points/`、9 月 14 日重跑 |
| 几何安装 / 静态场景拟合 | `mapanything` / `mapanything-game` | `geometry_outputs/` 与历史 geometry installation 日志 |

2026-09-14 完整归档根目录为 `WorldWarp_outputs/classroom_intermediates_2026-09-14/`。A/F/G/H 各 321 帧、30 fps、10.7 秒，核验通过；总记录包括 6,550 次 GS 更新、6,564 个模型快照、405 个 TTT3R 推理帧、52 个实际 MapAnything 视图、963 个事后诊断帧和 321 帧 GaME 独立渲染。

那次 GaME 只是重建旧共用静态场景并补齐模型 / 渲染记录，没有再用重建场景生成 B/C/D/E 视频。不能把它与旧 B/C/D/E 成片合称一次实际端到端运行。

详细自包含图文报告在服务器 `Reports/classroom_system_walkthrough_2026-09-14/`，内有 README、离线 HTML、86 张 PNG 和 17 个 MP4。约 243 MiB 的报告包与约 311 GiB 的完整中间归档是不同目录，二者都不随本源码仓库上传。

## 新入口做了什么变化

- 将历史路径依赖改为可准备的图像 / 相机 / 文本 reference，换图无需先生成 A 视频。
- 新输入默认使用场景通用提示，支持 `--prompt`；旧历史 caption 不会自动跟着 classroom 脚本套用。
- 仍保持各组合的主要几何 / 分段逻辑，统一视频交付尺寸、帧数和输出状态。
- 原版平移成片文件名改成由输入名和实际段数 / 时长构造，避免新数据仍命名为 bedroom。
- 原 shell 入口改成相对脚本位置定位，支持解释器覆盖。
- B/D/E 的新统一入口使用共用 context adapter 的 `context=1` 配置；历史 `generate_worldwarp_hybrid.py` 仍在，必要时可做旧实现对照。D/E 的 context=1 已从各自旧 `artifacts/*/config.yaml` 核对，不能误当成 C 的 ctx5。

因此新入口的默认参数对应历史实验系列，但新 prompt、不同输入、环境数值非确定性等都会影响结果，不保证与旧 MP4 逐像素相同。此前 PSNR / SSIM / 时间误差属于其当时视频；没有把那些数值当作新入口的新评测。

## 历史脚本的用途

`run_classroom_intermediate_capture.py` 是那次四版本、多 GPU、GaME 补录与全部帧诊断的编排器，包含明确的旧路径和固定 GPU；`run_worldwarp_mapanything_variants.py` 也是历史并行实验入口。它们保留用于追溯，不作为 AI 对新输入的默认执行入口。

`validate_classroom_intermediates.py` 核验的是指定多版本归档布局，不是通用单运行目录。新入口自身提供完成状态、成片探测和输出检查。要导出新运行的自包含报告，应按其实际中间文件另行制作，不把旧报告链接改名后当作新结果。
