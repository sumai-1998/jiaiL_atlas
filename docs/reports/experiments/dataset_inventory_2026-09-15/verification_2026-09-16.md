> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../Reports/dataset_inventory_2026-09-15/verification_2026-09-16.md)。本目录未复制视频或大型资产。

# 2026-09-16：本地 DL3DV 是否属于论文评测部分

本次新增结论：本地已有的 38 个场景，均属于 DL3DV 官方 140 场景 Benchmark。尚未发现证据能够确认它们属于 WorldWarp 论文表 2 实际参与指标统计的那一批场景。

## 比对依据

1. 从 [DL3DV 官方 Benchmark 预览页](https://dl3dv-10k.github.io/DL3DV-Benchmark-Preview/) 提取 140 个唯一的 64 位场景 hash。
2. 本地 TriSplat 的 140 场景索引与这 140 个 hash 完全相同，两个集合无差异。
3. 将前一天核查出的实际数据与官方集合求交集：原生图片和相机参数来源覆盖 19 个，Torch 分片来源覆盖 20 个，重复 1 个，共 38 个。按该次已核查库存，还缺 102 个场景。
4. 所有 38 个来源路径今天仍存在。每场景 304–414 帧，2026-09-15 抽查每场景首帧均为 480×270；本次不重复读取全部大分片。

官方仓库说明该 Benchmark 含 140 个场景，并提供 DL3DV 原论文各方法的性能结果：[官方说明](https://huggingface.co/datasets/DL3DV/DL3DV-Benchmark/blob/main/README.md)。因此，可以确认它们是 DL3DV 官方基准场景；不能据此推断 WorldWarp 使用了同一场景集合。

## WorldWarp 公开材料核查

- 论文 §5.1、§5.3 和表 2：写明使用 DL3DV，短期评测第 50 帧、长期第 200 帧；没有找到场景 hash、场景总数或对应起始帧/采样间隔清单。
- 补充材料 §7：给出生成与模型参数；未找到用于定位具体评测样本的清单。
- 上游仓库 main：0396b801c278546d01a6618a18e5a5c2a154c0a1；只有 main 分支，未发布 tag/release。公开 issue 1–3 未提供评测清单。
- examples 下有 20 个编号参考视频以及图像和 pose_cache，但没有找到它们与 DL3DV 原始场景 hash 的对应表，也没有证据说明这些 demo 等于表 2 的统计样本。
- 项目网页提供展示视频，没有找到场景编号清单。

来源：[论文](https://arxiv.org/html/2512.19678v1)、[上游代码](https://github.com/HyoKong/WorldWarp)、[项目页](https://hyokong.github.io/worldwarp-page/)。

## 不能混淆的集合

- DL3DV-Benchmark：官方 140 场景基准，本机确认有其中 38 个的低分辨率数据。
- DL3DV-Evaluation：另一个独立的 55 场景数据集，官方说明其场景不与 DL3DV-10K 重叠。[官方说明](https://huggingface.co/datasets/DL3DV/DL3DV-Evaluation)
- WorldWarp 的 DL3DV 指标子集：目前未取得确切定义。不能仅根据某目录名称叫 test、evaluation 或 benchmark 就指定它。

官方 Hugging Face 当前根目录有 141 个 hash 目录，比官方预览的 140 个多出 `0f8ac521439691fe429e9efbed8d5ded1cee35bcf52d47731fb60d5a2ff661a7`。本次以官方公开预览的 140 个编号为基准，没有把这个额外目录自动计入论文基准。CSV 内容下载返回 HTTP 401；本次利用公开可访问的目录元数据和官方预览完成编号核对，没有下载受限图片数据。

## 保存的清单

- [官方 140 场景编号](../../../../Reports/dataset_inventory_2026-09-15/dl3dv_official_140_scene_ids.txt)
- [本地已有 38 场景的路径和帧数](../../../../Reports/dataset_inventory_2026-09-15/existing_dl3dv_38_scenes.json)
- [已核查库存中缺少的 102 场景编号](../../../../Reports/dataset_inventory_2026-09-15/dl3dv_missing_102_scene_ids.txt)
- [机器可读的比对结果](../../../../Reports/dataset_inventory_2026-09-15/official_benchmark_membership_2026-09-16.json)
- [官方仓库公开根目录元数据快照](../../../../Reports/dataset_inventory_2026-09-15/official_hf_root_metadata_2026-09-16.json)

现有 38 场景可作为固定的 DL3DV 子集，供 WorldWarp 与组合管线在一致设置下比较。得到的结果应标明“DL3DV 官方 Benchmark 的 38 场景子集，480×270 来源图像”，不能标为 WorldWarp 原论文指标复现。要复现原表，还需要作者提供确切的场景与帧采样清单及评测实现/配置。
