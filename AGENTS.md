# AI 工具执行指南

本仓库把 WorldWarp、MapAnything、GaME 源码平铺整合。用户说“使用 xx 管线跑 xxx 数据”时，应落到 `scripts/pipelines.py` 的实际执行，不只回答命令。先阅读 `pipelines/registry.json` 与 `docs/PIPELINES.md`；不必通读三个上游仓库。

## 将用户意图映射到管线

| 用户表述 | ID |
|---|---|
| WorldWarp 原版、A、固定中心向左旋转 | `ww-rotate` |
| WorldWarp 匀速向左平移、bedroom 左移 | `ww-translate` |
| MapAnything + WorldWarp、原图约束 GS、G | `map-ww-anchor-gs`（未指定组合时的默认入口，不表示质量必然最好） |
| 滚动历史 GS、F | `map-ww-gs` |
| MapAnything + 点云 + WorldWarp、不做 GS 优化、H | `map-ww-anchor-points` |
| MapAnything + GaME + WorldWarp、B | `map-game-ww` |
| 三项目 5 帧上下文、C | `map-game-ww-ctx5` |
| 三项目 strength .50 / .65、D / E | `map-game-ww-s050` / `map-game-ww-s065` |
| 只估深 / 点云、多图几何 | `mapanything` |
| MapAnything + GaME、输出静态三维模型 | `mapanything-game` |

“左移 / 平移”和“左转 / 旋转”是两种运动，不能替换。统一入口中的 F/G/H 与 GaME 视频分支只支持纯旋转；不能直接改个提示词就声称支持平移。输入只给 `classroom` / `bedroom` 时可定位到 `Data/classroom.png` / `Data/bedroom.png`。对一组图片：几何管线将它们视为同一场景的多视图；视频批处理则为每张图分别创建一个运行目录，按 GPU 资源串行执行。

## 正常执行步骤

1. 检查输入存在；用 `list` / `describe` 确认管线和实际限制。用户已授权的推理无需额外重复询问许可。
2. 创建唯一的**计划路径名称**，如 `runs/classroom_G_YYYYMMDD_HHMMSS`；此时不要预先创建目录，因为运行器拒绝已有目录。
3. 用 `plan` 查看所有阶段和参数；用 `doctor` 检查本地环境 / 权重路径。二者都不推理。`doctor` 只做路径检查，不代表 CUDA 核函数或模型推理已经验收。
4. 读取 `nvidia-smi` 与 `df -h`，选有足够显存的空闲 GPU；传 `--gpu`。不要假定旧实验用过的 GPU 现在仍空闲，不要终止其他人的任务。没有可用资源时报告实际阻碍。
5. 执行 `run`，保留终端进程并持续检查 `status.json` 和日志，直到完成或具体失败。用户需要长任务时不要仅启动后台进程就宣称完成。
6. 运行器完成后会核对成片 321 帧、30 fps、480×608；再抽看实际画面。报告最终文件路径、实际时长、采用的管线与参数、是否保存全量中间结果，以及遇到的真实限制。

标准模板：

```bash
python scripts/pipelines.py plan --pipeline G --input Data/classroom.png --output runs/UNIQUE_RUN
python scripts/pipelines.py doctor --pipeline G --input Data/classroom.png --output runs/UNIQUE_RUN
python scripts/pipelines.py run --pipeline G --input Data/classroom.png --output runs/UNIQUE_RUN --gpu GPU_ID
python scripts/pipelines.py status runs/UNIQUE_RUN
```

所有路径参数按独立 argv 传递。提示词可能含引号或 shell 字符，不用字符串拼接执行 shell。运行失败保留输出目录与日志，换新目录重试；当前没有安全恢复完整扩散状态的 resume 接口，不删除已有成果来绕过检查。

## 必须保持准确的契约

- 视频标准配置为 **4 段合计 10.7 秒**，不是 4×10.7 秒。若用户明确要 42.8 秒，当前统一入口不支持，必须说明并实现 / 验证扩展后才能交付，不能偷偷改为 10.7 秒。
- DL3DV 的 `benchmark` 子命令是独立评测契约：225 帧、720×480、5 段、strength .8、后续上下文 5。原版为 `--method worldwarp`；三项目配对评测为 `--method map-game-ww --baseline-runs ...`，复用同组基线图像 / 相机，只用首图建固定 GaME 场景并校准深度尺度。其 SE3 轨迹支持不扩展到普通 A–H 入口，不得混称历史 B .6/ctx1；具体方法及验证记录见 `docs/PIPELINES.md` 和 `sumai-work-log.md`。
- F/G/H 的独立 DL3DV 评测已接入 `benchmark --method map-ww-gs / map-ww-anchor-gs / map-ww-anchor-points --baseline-runs ...`：225 帧、SE3、.8；几何关键帧为局部 0/12/24/36/48。首图单独 TTT3R 仅校准全局深度单位，后续几何为 MapAnything；不把此适配称为旧 classroom 配置。精简存储时先完成无损评分与核验，再清理本次运行的 PNG / 大型中间文件，保留数值、配置和日志。
- 默认 480×608、30 fps、50 步采样、CFG 5、seed 32，匀速左转总角度 −20°。A/B/D/E 上下文 1，F/G/H 和 C 上下文 5。D/E 历史上只改变 strength，不能默默换成 ctx5。
- 5 个均匀历史关键帧用于几何，5 个连续末尾帧用于视频上下文；它们不是同一组选帧。
- G/F 每段重新估几何、重新拟合原生 GS。没有跨段持久的 GaME 全局地图。H 不做 GS 优化。
- 三项目视频分支只拟合一次 GaME 固定场景，全图静态 mask，没有 SAM / 动态实例更新。上下文适配器仍可能加载上游 TTT3R 对象，但几何推理使用 GaME 渲染。
- 生成历史帧不是新增的真实观测。纯旋转没有平移视差，不足以单独证明深度准确度。
- `--capture full` 支持 A/F/G/H；逐次 GS 渲染 n 使用模型 n−1，保存模型 n 是更新后的状态。没有逐去噪步 latent / 解码图。
- `--posthoc` 是 F/G/H 成片之后的 321 帧 MapAnything 诊断，不能描述成实际生成输入。默认没有此额外推理。
- 新数据使用 `--prompt` 或通用场景提示。新准备的 reference 只有图像、相机、caption，没有预先生成的基线视频。不要把所有输入都写成 classroom。
- 历史脚本 `run_worldwarp_mapanything_variants.py`、`run_classroom_intermediate_capture.py` 含固定旧实验路径 / GPU，属于历史复现入口；通用新数据优先使用统一 CLI。

## 环境和代码修改

三套 Python 默认在仓库根目录 `conda_envs/{worldwarp,mapanything,game}/bin/python`，可通过 `GIL_WORLDWARP_PYTHON`、`GIL_MAPANYTHING_PYTHON`、`GIL_GAME_PYTHON` 覆盖。权重与缓存不在 Git 中，见 `docs/ENVIRONMENT.md`。几何跨环境用 NPZ / PLY 传递，K 与 OpenCV c2w 为公共接口，进 GaME 前转为 w2c。

源码无嵌套 `.git` 或 Git submodule，不重新 `git init` 三个子目录；不要删除许可证、第三方源码或上游来源记录。新推理产物写入 `runs/` 等已忽略目录，不提交模型、环境、凭据或实验大文件。

修改路由、接口、相机或分段逻辑时运行对应 CPU 测试；区分“测试通过”和“完整 GPU 推理验证”。不要为仅整理文档而重新跑所有长视频。若修改影响核心数值结果，应明确说明并做必要的实算验证。

## 工作记录

用户要求持续记录本目录的工作，台账为 [sumai-work-log.md](sumai-work-log.md)。完成实质性的推理、评测、管线变更或归档任务后，更新日期与进度，按任务记录输入、管线 / 参数、实际结果路径、验证范围、耗时及限制；失败或受阻的执行也如实记录。区分历史回填、计划和已完成实验，不把启动进程、CPU 测试或旧视频当成新的完整 GPU 验证。保留既有运行路径和结论；仅解释问题时不必新增实验记录。
