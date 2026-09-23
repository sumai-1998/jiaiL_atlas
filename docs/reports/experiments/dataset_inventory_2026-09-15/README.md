> Markdown 归档副本，整理于 2026-09-23。原报告与媒体：[原始文档](../../../../Reports/dataset_inventory_2026-09-15/README.md)。本目录未复制视频或大型资产。

# WorldWarp 数据集库存与下载体积核查

检查日期：2026-09-15。此目录只保存库存、场景路径和检查记录，没有复制数据集图片，也没有运行视频推理。

## WorldWarp 精确验证子集

核对 WorldWarp 论文、上游 GitHub 文件树与相关 issue、Hugging Face 模型仓库后，未找到论文验证场景清单、对应帧采样清单或专用数据下载包。不能把以下常见测试集自动等同于 WorldWarp 论文实验使用的子集。

- [WorldWarp 论文](https://arxiv.org/html/2512.19678v1)
- [上游代码](https://github.com/HyoKong/WorldWarp)
- [模型仓库](https://huggingface.co/imsuperkong/worldwarp)

## 可明确核实的下载体积

| 数据版本 | 大小 | 说明 |
|---|---:|---|
| RealEstate10K：pixelSplat 的 re10k_test_only.zip | 55,604,889,849 字节，55.60 GB / 51.79 GiB | HTTP HEAD 实测；这是预处理测试集压缩包，解压后的空间另计。来源帧为 640×360，不等于 WorldWarp 精确子集。 |
| DL3DV 官方 140 场景 benchmark：只下载 images_4 | 官方标注 100–150 GB | 960×540 图像版本；不能认定 WorldWarp 使用了这 140 个场景。 |
| DL3DV 官方 140 场景 benchmark：全部分辨率及附带文件 | 官方标注约 2.1 TB | 仅做小规模验证通常无需下载整个版本。 |

RealEstate10K 原站的 720 MB 包只有轨迹/时间戳等元数据，不能代替真实 RGB 图像数据。

来源：[pixelSplat 下载说明](https://github.com/dcharatan/pixelsplat#acquiring-datasets)、[test ZIP](http://schadenfreude.csail.mit.edu:8000/re10k_test_only.zip)、[分辨率说明](https://github.com/cvg/resplat/blob/main/DATASETS.md)、[Re10K 原站](https://google.github.io/realestate10k/download.html)、[DL3DV benchmark 说明](https://huggingface.co/datasets/DL3DV/DL3DV-Benchmark/blob/main/README.md)。精确字节数见 [download_size_metadata.json](../../../../Reports/dataset_inventory_2026-09-15/download_size_metadata.json)。

## 本机已找到的 DL3DV

| 位置 | 磁盘占用 | 实际内容 |
|---|---:|---|
| /data2/wangzhongtao/Project/Dataset/DL3DV-10K | 43.29 GiB | 581 个场景，193,192 张图；581 份 transforms.json 引用的图像均存在且文件非空。按本地 140 场景索引比对，覆盖 7 个测试场景。 |
| /data2/wangzhongtao/Project/Dataset/DL3DV-10K_mini | 76.48 GiB | 10,221 个场景目录，但只有 1,000 个目录含图片，999 个同时含位姿；999 份位姿引用的图像均存在且文件非空。覆盖本地测试索引中的 19 个场景。其余大量目录为空，不能称为完整 10K 下载。 |
| /data4/zhaoruijie/TriSplat/data/dl3dv/test | 约 1.64 GiB | 索引列出 140 场景 / 47 分片，实际有 7 分片、20 场景，缺 40 分片。已安全加载全部现有分片并抽查每场景首张图。共 6,959 帧。 |

这些来源存在重复。按 `/data4/zhaoruijie/TriSplat/data/dl3dv/test/index.json` 比对并去重，一共有 **38 个已有测试场景**，每场景 304–414 帧。38 个场景的首帧均实测为 **480×270**。

场景路径、分片和帧数已保存于 [existing_dl3dv_38_scenes.json](../../../../Reports/dataset_inventory_2026-09-15/existing_dl3dv_38_scenes.json)。这是本地可用场景库存，**不是 WorldWarp 官方验证清单，也不是已经接入统一 CLI 的评测配置**。

检查边界：原生目录检查了位姿引用的图像是否存在且非空，没有对每张图做解码或与远端校验和比对；分片使用 `torch.load(..., weights_only=True)` 加载，并检查每场景一张图及相机张量形状。因此这份记录证明已有内容可读及文件配套程度，不等于远端整套数据逐字节下载验收。

相机适配时需要保留原始元数据：`transforms.json` 的相机图像尺寸可能对应原始分辨率，而实际图像在 `images_8` 下；应按真实图像尺寸缩放内参，并转换源数据的相机坐标约定。现有固定旋转 CLI 不能直接代表真实测试视频轨迹。

## 文件

- [local_directory_audit.json](../../../../Reports/dataset_inventory_2026-09-15/local_directory_audit.json)：目录、图片、位姿与测试索引覆盖统计。
- [local_frame_presence_audit.json](../../../../Reports/dataset_inventory_2026-09-15/local_frame_presence_audit.json)：所有位姿文件引用图像的存在性检查。
- [local_torch_audit.json](../../../../Reports/dataset_inventory_2026-09-15/local_torch_audit.json)：7 个分片中实际场景、帧数、图片尺寸、相机张量形状。
- [existing_dl3dv_38_scenes.json](../../../../Reports/dataset_inventory_2026-09-15/existing_dl3dv_38_scenes.json)：去重后的现有测试场景来源。
- [download_size_metadata.json](../../../../Reports/dataset_inventory_2026-09-15/download_size_metadata.json)：下载文件体积与来源。

## RealEstate10K 与服务器搜索范围

在已检查范围内，未找到 RealEstate10K 的实际图片/视频下载或测试集压缩包；找到的是代码、评测索引和权重名称。

已完成对 /data0–/data5、/home、/mnt、/media、/opt、/srv 的目录名称检索：检查 47,724 个目录，目录遍历深度 4（检查名称到第 5 层），跳过常见环境和无关数据内容。另单独检查 /data0/my_nfs/shared_data 和 /data5/GIL-NFS，遍历 78,054 个目录到第 5 层，未找到额外候选。主搜索遇到 119 个不可访问目录，共享目录搜索遇到 83 个，可能有重叠。已找到的 DL3DV 目录另做了上文的深入核查。

更深的广泛扫描曾进入大量无关 CO3D、音频和 COLMAP 产物，因此已停止。上述未找到结论不覆盖无权限、改名、更深未搜索目录或压缩包内部。详见 [server_search_scope.json](../../../../Reports/dataset_inventory_2026-09-15/server_search_scope.json)。

## 2026-09-16 追加核查

已将本地场景 hash 与 DL3DV 官方公开预览逐一比对，确认本地 140 场景索引与官方预览完全一致，已有 38 个场景均属于官方基准。WorldWarp 实际用于表 2 的子集仍未能确定。详见 [追加核查说明](../../../../Reports/dataset_inventory_2026-09-15/verification_2026-09-16.md)。
