# 项目报告与研究文档总目录

整理日期：2026-09-23。这里集中收录本项目编写的研究、流程、评测、部署历史与演示 Markdown；上游项目文档不在此次整理范围内。

**建议从当前研究方案和实际流程开始阅读。** 历史材料按原日期保留，早期结论需结合后续基线失败复核理解。

- [世界模型核心机理与研究定位](research/世界模型_核心机理与研究定位报告_2026-09-22.md)
- [静态 GS 世界闭环：可行性与实施方案](research/静态GS世界闭环_可行性与实施方案_2026-09-22.md)
- [WorldCrafter 架构与借鉴](research/WorldCrafter_架构与借鉴分析_2026-09-22.md)
- [GAE 架构与借鉴](research/GAE_架构与借鉴分析_2026-09-22.md)
- [WorldWarp 实际完整流程](technical/WORLDWARP_DETAILED_WORKFLOW.md)
- [五场景评测总结与结论边界](technical/WORLDWARP_PIPELINE_EVALUATION_SUMMARY.md)

独立报告已迁入这里；带媒体的实验包和演示包保留原位置，本目录收录其 Markdown 副本。媒体链接指向原包，**只下载此目录不能离线播放全部视频**；需要离线图文阅读时下载对应完整原报告包。归档副本是本次快照，后续修改原报告时需同步副本。

操作文档仍以 [管线说明](../PIPELINES.md)、[环境说明](../ENVIRONMENT.md)、[AI 执行指南](../../AGENTS.md)为准；[工作日记](../../sumai-work-log.md)保留根目录作为持续台账。

## 研究定位与技术方案

- [GAE：几何原生潜空间的架构与本项目借鉴分析](research/GAE_架构与借鉴分析_2026-09-22.md) — `research`
- [WorldCrafter：源码架构与本项目借鉴分析](research/WorldCrafter_架构与借鉴分析_2026-09-22.md) — `research`
- [WorldWarp 主导的类 Atlas 管线：从单张 GT 首帧到连续新视角视频](research/WorldWarp_单GT首帧到类Atlas闭环_完整流程_2026-09-14.md) — `research`
- [WorldWarp 类 Atlas 流程：小研究课题与模块替代路线](research/WorldWarp_类Atlas流程_小研究课题与模块替代路线_2026-09-14.md) — `research`
- [世界模型的核心机理、模型表征与研究定位](research/世界模型_核心机理与研究定位报告_2026-09-22.md) — `research`
- [从少量真实图像到持续扩展的静态 GS 世界：可行性与实施方案](research/静态GS世界闭环_可行性与实施方案_2026-09-22.md) — `research`

## 实际流程与评测总结

- [WorldWarp 详细推理流程：从首帧到分段视频](technical/WORLDWARP_DETAILED_WORKFLOW.md) — `technical`
- [WorldWarp 原版与组合管线评测总结](technical/WORLDWARP_PIPELINE_EVALUATION_SUMMARY.md) — `technical`

## 历史调研与部署记录

- [Atlas 综合版：开源组装清单与接口说明](archive/ATLAS_OPEN_SOURCE_ASSEMBLY_2026-09-06.md) — `archive`
- [Atlas 架构二次校准](archive/ATLAS_REVIEW_2026-09-06.md) — `archive`
- [Atlas 架构第三版：整体复核与更新说明](archive/ATLAS_REVIEW_V3_2026-09-06.md) — `archive`
- [Atlas 几何回写模块：本地安装与使用](archive/GEOMETRY_SETUP.md) — `archive`
- [Atlas 极简复刻：开源组件更新调研](archive/OPEN_SOURCE_COMPONENT_UPDATE_2026-09-05.md) — `archive`
- [WorldWarp 本地部署记录](archive/WORLDWARP_SETUP.md) — `archive`

## 图文实验报告

- [Classroom：从一张图片到完整视频的中间结果说明](experiments/classroom_system_walkthrough_2026-09-14/README.md) — `classroom_system_walkthrough_2026-09-14`
- [WorldWarp 数据集库存与下载体积核查](experiments/dataset_inventory_2026-09-15/README.md) — `dataset_inventory_2026-09-15`
- [2026-09-16：本地 DL3DV 是否属于论文评测部分](experiments/dataset_inventory_2026-09-15/verification_2026-09-16.md) — `dataset_inventory_2026-09-15`
- [F/G/H：同五个 DL3DV 场景的配对评测](experiments/dl3dv_FGH_eval5_2026-09-17_225018/README.md) — `dl3dv_FGH_eval5_2026-09-17_225018`
- [WorldWarp 原版基线再次审计（2026-09-21）](experiments/dl3dv_baseline_audit_20260921/README.md) — `dl3dv_baseline_audit_20260921`
- [DL3DV 控制相机核查（2026-09-18）](experiments/dl3dv_camera_audit_20260918/README.md) — `dl3dv_camera_audit_20260918`
- [DL3DV 五场景：WorldWarp 与三项目组合配对评测](experiments/dl3dv_map_game_ww_eval5_2026-09-16_174900/README.md) — `dl3dv_map_game_ww_eval5_2026-09-16_174900`
- [MapAnything + GaME + WorldWarp：DL3DV 本地 5 场景基准](experiments/dl3dv_map_game_ww_eval5_2026-09-16_174900/hybrid_details.md) — `dl3dv_map_game_ww_eval5_2026-09-16_174900`
- [雕像场景：WorldWarp 三组实算调试（2026-09-21）](experiments/dl3dv_statue_tuning_20260921/README.md) — `dl3dv_statue_tuning_20260921`
- [WorldWarp：DL3DV 本地 2 场景基准](experiments/dl3dv_worldwarp_eval2_2026-09-16_142500/README.md) — `dl3dv_worldwarp_eval2_2026-09-16_142500`
- [WorldWarp：DL3DV 本地 3 场景基准](experiments/dl3dv_worldwarp_eval3_2026-09-16_112915/README.md) — `dl3dv_worldwarp_eval3_2026-09-16_112915`
- [建筑与雕像：WorldWarp 基线重验](experiments/dl3dv_worldwarp_recheck_20260918/README.md) — `dl3dv_worldwarp_recheck_20260918`

## 运行报告

- [F: MapAnything + WorldWarp (rolling_gs)：已完成并精简保存](runs/dl3dv_F_eval5_20260917_225018/README.md) — `dl3dv_F_eval5_20260917_225018`
- [G: MapAnything + WorldWarp (anchor_gs)：已完成并精简保存](runs/dl3dv_G_eval5_20260917_225018/README.md) — `dl3dv_G_eval5_20260917_225018`
- [H: MapAnything + WorldWarp (anchor_points)：已完成并精简保存](runs/dl3dv_H_eval5_20260917_225018/README.md) — `dl3dv_H_eval5_20260917_225018`
- [MapAnything + GaME + WorldWarp：DL3DV 本地 5 场景基准](runs/dl3dv_map_game_ww_eval5_20260916_174900/README.md) — `dl3dv_map_game_ww_eval5_20260916_174900`
- [WorldWarp / dataset-camera diagnostic：DL3DV 本地 1 场景基准](runs/dl3dv_statue_s035_20260921/README.md) — `dl3dv_statue_s035_20260921`
- [WorldWarp / dataset-camera diagnostic：DL3DV 本地 1 场景基准](runs/dl3dv_statue_s050_20260921/README.md) — `dl3dv_statue_s050_20260921`
- [WorldWarp / dataset-camera diagnostic：DL3DV 本地 1 场景基准](runs/dl3dv_worldwarp_calibrated_diagnostic_20260918_1443/README.md) — `dl3dv_worldwarp_calibrated_diagnostic_20260918_1443`
- [WorldWarp：DL3DV 本地 2 场景基准](runs/dl3dv_worldwarp_eval2_20260916_142500/README.md) — `dl3dv_worldwarp_eval2_20260916_142500`
- [WorldWarp：DL3DV 本地 3 场景基准](runs/dl3dv_worldwarp_eval3_20260916_112915/README.md) — `dl3dv_worldwarp_eval3_20260916_112915`
- [WorldWarp：DL3DV 本地 1 场景基准](runs/dl3dv_worldwarp_recheck_20260918_1438/README.md) — `dl3dv_worldwarp_recheck_20260918_1438`

## classroom / bedroom 历史实验

- [卧室：匀速向左平移，4 段](classroom-bedroom/bedroom_truck_left_2026-09-07/README.md) — `bedroom_truck_left_2026-09-07`
- [README](classroom-bedroom/classroom_all_comparison_2026-09-08/README.md) — `classroom_all_comparison_2026-09-08`
- [教室历次视频合集](classroom-bedroom/classroom_history_2026-09-08/README.md) — `classroom_history_2026-09-08`
- [教室匀速左转：MapAnything → GaME → WorldWarp](classroom-bedroom/classroom_hybrid_pan_left_2026-09-07/README.md) — `classroom_hybrid_pan_left_2026-09-07`
- [教室左转：三组参数对照](classroom-bedroom/classroom_hybrid_tuning_2026-09-08/README.md) — `classroom_hybrid_tuning_2026-09-08`
- [README](classroom-bedroom/classroom_intermediates_2026-09-14/README.md) — `classroom_intermediates_2026-09-14`
- [教室：原地匀速向左旋转，4 段](classroom-bedroom/classroom_pan_left_2026-09-07/README.md) — `classroom_pan_left_2026-09-07`
- [Classroom：WorldWarp + MapAnything，去除 GaME](classroom-bedroom/classroom_worldwarp_mapanything_2026-09-08/README.md) — `classroom_worldwarp_mapanything_2026-09-08`

## 演示与讲稿

- [Atlas：四章递进讲解版](presentations/atlas_four_chapter_polished_2026-09-07/README.md) — `atlas_four_chapter_polished_2026-09-07`
- [第四章配套：WorldWarp 本地部署与演示](presentations/atlas_four_chapter_polished_2026-09-07/WorldWarp_本地部署与演示.md) — `atlas_four_chapter_polished_2026-09-07`
- [Atlas：四章递进讲稿](presentations/atlas_four_chapter_polished_2026-09-07/逐页讲稿.md) — `atlas_four_chapter_polished_2026-09-07`
- [Atlas：从整体到细节 · 讲解版](presentations/atlas_framework_clear_2026-09-07/README.md) — `atlas_framework_clear_2026-09-07`
- [Atlas：从整体到细节 — 逐页讲稿](presentations/atlas_framework_clear_2026-09-07/逐页讲稿.md) — `atlas_framework_clear_2026-09-07`
- [Atlas：框架与三个项目详解版](presentations/atlas_framework_projects_2026-09-07/README.md) — `atlas_framework_projects_2026-09-07`
- [WorldWarp、MapAnything、GaME：当前能做什么，能替代什么](presentations/atlas_framework_projects_2026-09-07/三个项目_当前能力与替换范围.md) — `atlas_framework_projects_2026-09-07`
- [Atlas 框架与三个项目详解 — 逐页讲稿](presentations/atlas_framework_projects_2026-09-07/逐页讲稿.md) — `atlas_framework_projects_2026-09-07`
- [Atlas：框架解析与复现路径](presentations/atlas_framework_reproduction_2026-09-06/README.md) — `atlas_framework_reproduction_2026-09-06`
- [Atlas：框架解析与复现路径 — 逐页讲解备注](presentations/atlas_framework_reproduction_2026-09-06/讲解备注.md) — `atlas_framework_reproduction_2026-09-06`
- [Atlas：以我的架构假设为主线](presentations/atlas_hypothesis_first_2026-09-07/README.md) — `atlas_hypothesis_first_2026-09-07`
- [WorldWarp、MapAnything、GaME：当前能做什么，能替代什么](presentations/atlas_hypothesis_first_2026-09-07/三个项目_当前能力与替换范围.md) — `atlas_hypothesis_first_2026-09-07`
- [Atlas：以我的架构假设为主线 — 逐页讲稿](presentations/atlas_hypothesis_first_2026-09-07/逐页讲稿.md) — `atlas_hypothesis_first_2026-09-07`

文件搬迁与副本来源见 [manifest.json](manifest.json)。
