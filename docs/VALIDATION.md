# 本次仓库整理的验证范围

日期：2026-09-14。

## 执行入口

`test_pipelines.py` 的 8 项 CPU 测试通过，检查：

- 全部 11 个 ID 能生成不依赖旧 classroom 目录的计划。
- A–H 的实际历史默认值正确；D/E 为 1 帧上下文，C 为 5 帧。
- 计划中的参数与真实底层脚本的 argparse 声明一致，含 full capture 和 posthoc 路由。
- 不支持的段数、非法强度、上下文和捕获组合明确失败。
- 用一张新造的测试图实际准备 480×608 输入、321 个相机与新 caption，逐像素 / 逐角度检查，并验证移动参考目录后仍可读取。
- 模拟阶段成功 / 失败，实际创建日志和状态文件，核对退出码与最终状态；没有调用 GPU 模型。
- 缺少依赖时不创建运行目录。
- 带空格路径和 shell 特殊字符提示词作为独立 argv 传递。

运行命令：

```bash
conda_envs/worldwarp/bin/python -m unittest discover -s scripts -p test_pipelines.py -v
conda_envs/worldwarp/bin/python -m unittest discover -s scripts -p test_worldwarp_hybrid_context.py -v
conda_envs/worldwarp/bin/python -m unittest discover -s scripts -p test_worldwarp_rotation.py -v
```

另运行 4 项扩展上下文映射测试和 4 项匀速旋转 / 分段相机测试，共 16 项通过。修改过的 Python 文件语法编译和三个 shell 入口语法检查通过。本机 C 管线的 `doctor` 路径检查为 ready；该检查不等于模型前向或新视频质量验证。

## Git 整合

三个项目与两个原 WorldWarp 子模块的 `.git` 已从工作目录移出；原 Git 元数据和未提交补丁备份到工作区外。原 `.gitmodules` 声明随备份保留。统一仓库根目录使用一个 Git，vendor 源码直接追踪，保留许可证和上游版本记录。

提交前检查不包含子模块 gitlink、模型权重、Python 环境、缓存、历史推理输出和新报告媒体目录，检查大文件和可能的凭据。推送后核对远端 main 指向实际提交；结果在交付消息中给出。

## 计算验证的边界

本次修改集中在参数入口、路径、文本输入与编排，没有重新运行所有 10.7 秒 GPU 长视频。历史 A/F/G/H 和旧 GaME 视频结果证明对应底层组合曾实际运行；新入口有 CPU 路由、参考准备和失败处理验证。若在新机器或新参数下运行，应以该次 `status.json`、日志、成片核验和实际画面为准。
