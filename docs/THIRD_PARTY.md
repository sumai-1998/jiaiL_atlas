# 第三方源码来源

本仓库将现有工作区三个 Git 项目的源码整合为普通目录，保留其版权头、作者信息和已有许可证。没有把三者改称同一个原创项目，也没有给全部第三方代码重新授权。

| 目录 | 原始仓库 | 固定提交 |
|---|---|---|
| WorldWarp | https://github.com/HyoKong/WorldWarp | `0396b801c278546d01a6618a18e5a5c2a154c0a1` |
| MapAnything | https://github.com/facebookresearch/map-anything | `3d10cf7a3016fc0f9bb13a071ee66c47b10be0d9` |
| GaME | https://github.com/VladimirYugay/GaME | `1c971d65d29952789fa4a2ebb342580d41acbbff` |
| WorldWarp/src/fused-ssim | https://github.com/rahul-goel/fused-ssim | `98126b7781f9e563234c92d2bf08ee0994f4f175` |
| WorldWarp/src/simple-knn | https://github.com/camenduru/simple-knn | `60f461f4a56b7967e5d8045bf92f8c33f36976d0` |

机器可读记录见 [upstream_sources.json](upstream_sources.json)。导入时 WorldWarp 已有提示模型加载、端口配置和分段相机的本地修复；GaME 的工作树差异主要是本地编译产物，这些 build / 二进制文件没有纳入统一仓库。

MapAnything 的 [LICENSE](../MapAnything/LICENSE)、GaME 的 [LICENSE](../GaME/LICENSE)、WorldWarp 内部组件和 GaME rasterizer 的各自许可证继续适用。例如 GaME 子目录中存在单独的 Inria 派生许可，不能只按顶层文件概括所有嵌套代码。导入的 WorldWarp 顶层未提供独立 LICENSE 文件，保留其 README 与内部组件已有声明，不补造授权条款。模型权重许可与源码许可分别处理；权重没有上传本仓库。

原工作区 `.git` 目录和子模块指针已从这三个目录移出，Git 元数据备份位于服务器工作区外的 `.git-metadata-backups/GIL_ATLAS_20260914_204940/`；该备份不在仓库中。所有需要构建的源码直接受根 Git 管理，`.gitmodules` 历史声明也随备份保留。
