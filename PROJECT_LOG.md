# 项目进度日志：视频前景抠像与背景合成 Demo

日期：2026-06-03

最近更新：2026-06-09

阶段更新：2026-06-10

阶段更新：2026-06-15

阶段更新：2026-06-23

## 当前目标

本项目当前阶段不是训练一个新模型，而是先搭建一个可运行的命令行 demo：

```text
人物视频 human.mp4 + 无人背景 bg.mp4 -> 合成结果 result.mp4
```

第一版目标是验证完整技术链路：

1. 读取用户人物视频。
2. 使用视频抠像模型分离人物。
3. 将人物合成到指定背景视频上。
4. 保留原人物视频音频。
5. 导出 MP4 结果。

## 当前项目结构

```text
F:\研究组项目\舞蹈背景
├── README.md
├── PROJECT_LOG.md
├── requirements.txt
├── scripts
│   └── run_demo.py
├── src
│   ├── __init__.py
│   ├── composite.py
│   ├── ffmpeg_utils.py
│   └── matting.py
├── outputs
└── work
```

核心文件说明：

- `scripts/run_demo.py`：命令行入口。
- `src/matting.py`：抠像后端，目前支持 `diff` 和 `rvm`。
- `src/composite.py`：逐帧读取、抠像、调色、合成、编码。
- `src/ffmpeg_utils.py`：视频信息探测和音频合成。
- `outputs/`：输出结果目录。
- `work/`：临时处理目录。

## 当前使用方式

在 PowerShell 中进入项目目录：

```powershell
cd "F:\研究组项目\舞蹈背景"
```

运行当前推荐版本：

```powershell
python .\scripts\run_demo.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_rvm_resnet_10s.mp4" `
  --backend rvm `
  --rvm-model resnet50 `
  --rvm-downsample-ratio 0.25 `
  --alpha-gain 1.8 `
  --max-seconds 10
```

输出文件：

```text
F:\研究组项目\舞蹈背景\outputs\result_rvm_resnet_10s.mp4
```

## 当前工作流

当前处理流程如下：

```text
human.mp4
  |
  | 1. FFmpeg 读取人物视频帧
  v
逐帧 RGB 图像
  |
  | 2. RVM 模型预测人物 alpha mask
  v
人物透明度遮罩
  |
  | 3. alpha 增强
  |    当前推荐参数：--alpha-gain 1.8
  v
增强后遮罩
  |
  | 4. 简单光照/颜色和谐化
  v
调整后人物前景
  |
  | 5. 与 bg.mp4 对应帧逐帧合成
  v
无声合成视频
  |
  | 6. 从 human.mp4 提取原始音频并合回
  v
最终 result.mp4
```

背景视频处理方式：

- 当前要求人物视频和背景视频分辨率一致。
- 如果背景视频比人物视频短，代码会循环读取背景视频帧。
- 当前 demo 默认只处理 `--max-seconds` 指定的时长。

## 当前用到的模型

当前主力模型是 **RVM: Robust Video Matting**。

使用方式：

```text
--backend rvm
```

当前测试过两个 RVM 版本：

```text
mobilenetv3
resnet50
```

推荐当前 demo 使用：

```text
--rvm-model resnet50
```

原因：

- `resnet50` 比 `mobilenetv3` 更重，但复杂边缘和困难帧通常更稳定。
- 当前素材中人物有皇冠、金色服装、运动模糊，轻量模型更容易漏抠或半透明。

模型加载方式：

- 通过 PyTorch Hub 加载 `PeterL1n/RobustVideoMatting`。
- 第一次运行会下载模型代码和权重。
- 后续运行会使用本地缓存。

本机缓存位置通常为：

```text
C:\Users\51227\.cache\torch\hub\
C:\Users\51227\.cache\torch\hub\checkpoints\
```

## 与“小模型”的关系

当前 RVM 不是本项目自己训练的小模型，而是成熟的预训练视频抠像模型。

可以这样理解：

```text
RVM mobilenetv3：轻量小模型，速度快，质量略弱。
RVM resnet50：中等规模预训练模型，质量更稳，速度稍慢。
SAM2 等大模型：泛化能力更强，但部署更重，未必直接输出高质量 alpha。
自研小模型：后期用项目数据训练或微调，最贴合固定场景，但需要数据和标注。
```

当前阶段推荐：

```text
Demo 阶段：RVM resnet50
速度优先：RVM mobilenetv3
后期优化：采集项目数据，考虑微调或训练专用小模型
```

## 已完成内容

1. 搭建了命令行 demo 项目结构。
2. 实现了 FFmpeg 视频信息探测。
3. 实现了逐帧读取人物视频和背景视频。
4. 实现了背景视频循环读取。
5. 实现了 `diff` 背景差分基线后端。
6. 接入了 RVM 抠像后端。
7. 支持 `mobilenetv3` 和 `resnet50` 两种 RVM 模型。
8. 实现了 alpha 增强参数：

```text
--alpha-gain
--alpha-bias
```

9. 实现了简单前景亮度/颜色和谐化。
10. 实现了合成视频编码。
11. 实现了从人物视频合回原始音频。
12. 已生成 10 秒 RVM demo：

```text
outputs/result_rvm_resnet_10s.mp4
```

## 当前效果判断

整体链路已经跑通，可以作为第一版 demo。

有利条件：

- `human.mp4` 和 `bg.mp4` 都是 720x1280。
- 两个视频都是 30fps。
- 都是竖屏。
- 场景和机位大体接近。
- 人物主体明显。
- 当前机器已有 PyTorch + CUDA，RVM 可以正常运行。

当前较好效果：

- 人物静止或清晰时，合成效果较稳定。
- 第 9 秒附近效果明显较好。
- 音频可以正常保留。
- 输出视频格式正常。

## 当前缺点和风险

### 1. 运动模糊导致人物半透明

第 5 秒附近原始人物视频严重虚焦/运动模糊，RVM 对人物 alpha 判断偏低，导致人物在合成后出现半透明、幽灵感。

已尝试：

```text
--alpha-gain 1.8
```

可以改善一部分，但不能完全解决。

原因：

- 输入视频本身人物边界不清晰。
- 皇冠、衣服、背景灯光颜色接近。
- 快速运动时，RVM 对透明度估计会变保守。

### 2. 头饰和细节边缘容易损失

皇冠结构很细，属于视频抠像难点。RVM 可以保留部分轮廓，但不保证每一帧都完整。

### 3. 人物和背景亮度仍不完全匹配

当前只有简单的亮度和颜色调整，不是真正的图像和谐化模型。

后续如果要更自然，需要做：

- 边缘光模拟。
- 色温匹配。
- 局部对比度调整。
- 前景/背景曝光协调。

### 4. 还没有自动画面对齐

当前要求人物视频和背景视频分辨率一致，并且机位大体接近。

如果用户上传的视频角度、缩放、裁剪差异明显，当前版本会穿帮。

后续需要加入：

- OpenCV 特征匹配。
- 单应性变换。
- 基于塔轮廓或关键点的自动对齐。

### 5. 还没有网页系统

当前只是命令行 demo，没有前端上传页面、任务队列、进度条和下载接口。

后续可扩展为：

```text
FastAPI 后端
React/Vue 前端
任务队列 Celery/RQ
Redis 状态管理
文件上传和结果下载
```

### 6. 性能仍需优化

当前逐帧 Python 管道可以跑通 demo，但不是最终生产级性能。

后续优化方向：

- 批量推理。
- GPU 显存优化。
- 减少 CPU/GPU 数据拷贝。
- 使用更快的编码参数。
- 根据业务选择 `mobilenetv3` 或 `resnet50`。

## 下一步建议

短期建议：

1. 固化当前命令行 demo。
2. 加入 mask 后处理：

```text
alpha 阈值压实
边缘羽化
时间平滑
小区域清理
```

3. 针对第 5 秒这类模糊帧做专门优化。
4. 输出对比视频，方便比较 `mobilenetv3`、`resnet50`、不同 alpha 参数。

中期建议：

1. 做 FastAPI 上传接口。
2. 做简单网页：

```text
上传人物视频
选择背景视频
显示处理进度
预览结果
下载 MP4
```

3. 加入任务队列，避免长任务阻塞接口。
4. 加入自动视频时长处理和背景循环策略。

长期建议：

1. 收集更多项目真实视频。
2. 建立测试集。
3. 标注困难帧。
4. 评估是否微调一个项目专用小模型。
5. 引入更强的分割/抠像组合方案，例如 SAM2 + matting refinement。

## 2026-06-09 更新：SAM2 实验路线已开始

新增目标：

```text
保留 RVM 基线，同时新增 SAM2 路线，用于处理头冠、手部、长指甲等复杂细节。
```

新增文件：

```text
configs/prompts/human_sam2_points.json
scripts/run_sam2_mask.py
scripts/composite_from_alpha.py
scripts/run_sam2_pipeline.py
src/refine.py
experiments/COMPARISON_LOG.md
```

新增能力：

1. 从人物视频抽帧。
2. 使用 SAM2 根据提示点生成视频 mask。
3. 将 SAM2 mask 保存为 `.npy` alpha 序列。
4. 输出 mask 预览视频。
5. 可选使用 OpenCV guided filter 软化 mask。
6. 使用外部 alpha 序列合成视频。

已生成 SAM2 实验结果：

```text
outputs/sam2_mask_3s.mp4
outputs/result_sam2_alpha_3s.mp4
outputs/sam2_mask_6s.mp4
outputs/result_sam2_alpha_6s.mp4
```

当前观察：

```text
SAM2 对头冠和手部的保持明显优于 RVM。
SAM2 输出本质是 hard mask，不是天然 alpha。
guided filter 可以软化边缘，但当前半径下边缘偏厚。
裙摆、背景装饰和人物边界还需要进一步控制。
```

环境注意：

```text
当前 PyTorch：2.3.0+cu121
SAM2 官方推荐：PyTorch 2.5.1+
当前没有升级 PyTorch，避免破坏已跑通的 RVM 环境。
SAM2 能运行，但会出现 CUDA extension / flash attention 相关 warning。
```

下一步：

```text
1. 对比 SAM2 hard mask 与 guided-filter mask。
2. 调整 guided filter 半径。
3. 增加关键帧提示点。
4. 尝试 SAM2 mask 与 RVM alpha 融合。
5. 汇总 RVM vs SAM2 vs SAM2+refine 对比。
```

一键运行 SAM2 当前流程：

```powershell
python .\scripts\run_sam2_pipeline.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_sam2_pipeline_6s.mp4" `
  --output-mask ".\outputs\sam2_mask_pipeline_6s.mp4" `
  --max-seconds 6
```

## 2026-06-10 更新：SAM2 阶段成果确认

当前阶段成果：

```text
SAM2 路线效果良好，已明显修复 RVM 阶段衣服延展缺失、头冠细节缺失的问题。
```

当前主要缺点：

```text
人物略微发虚。
```

初步原因：

```text
1. guided filter 半径偏大，alpha 软边过宽。
2. SAM2 mask 偏厚，经过软化后边缘更糊。
3. 合成前景没有做锐化补偿。
```

下一步解决方向：

```text
1. 降低 guided filter 半径。
2. 对比 no-refine hard mask。
3. 实现 hard-core + narrow soft edge 的 edge-band refinement。
4. 对人物区域做轻微 unsharp mask 锐化。
```

详细阶段报告：

```text
STAGE_REPORT_2026-06-10.md
```

## 2026-06-15 更新：edge-band 清晰版

本轮完成：

```text
实现 edge-band refinement，减少 guided filter 导致的人物整体虚化。
```

核心改动：

```text
src/refine.py:
  新增 refine_alpha_edge_band()

scripts/run_sam2_mask.py:
  新增 --refine-mode edge-band
  新增 --edge-erode / --edge-dilate

scripts/composite_from_alpha.py:
  新增 --foreground-sharpen / --sharpen-radius

scripts/run_sam2_pipeline.py:
  一键流程支持 edge-band 和 foreground sharpen
```

输出：

```text
outputs/result_sam2_edgeband_6s.mp4
outputs/result_sam2_edgeband_10s.mp4
outputs/sam2_mask_edgeband_10s.mp4
outputs/result_sam2_edgeband_choke1_10s.mp4
outputs/result_sam2_edgeband_choke2_10s.mp4
```

推荐当前版本：

```text
outputs/result_sam2_edgeband_choke2_10s.mp4
```

说明：

```text
完整 15.5 秒版本在当前 Windows 环境下超过 10 分钟超时，未生成有效结果。
当前交付 10 秒优化版。
后续完整片建议分段处理或迁移到 WSL/官方推荐 PyTorch 环境。
```

### 黑边修正

用户指出：

```text
人物身体外侧有黑边，底部青绿色三角装饰是背景部分，不应作为人物缺陷处理。
```

已修正处理方向：

```text
1. 不再把底部青绿色三角形装饰视为裙摆问题。
2. 新增 alpha choke，在合成阶段轻微收缩 alpha，清理外侧黑边。
```

新增参数：

```text
--alpha-choke
--alpha-choke-feather
```

当前推荐：

```text
--alpha-choke 2
--alpha-choke-feather 0.5
```

## 2026-06-23 更新：背景拉伸

新增能力：

```text
--background-mode stretch
```

用途：

```text
把背景视频拉慢/拉快到目标人物视频时长，避免背景循环时产生跳变。
```

新增脚本：

```text
scripts/stretch_background.py
```

已验证：

```text
bg.mp4: 10.43s -> 15.50s
outputs/背景拉伸_匹配human_15秒.mp4
```

合成链路 smoke test：

```text
outputs/背景拉伸合成_smoke_1秒_v2.mp4
```

五条新任务建议统一使用：

```text
--background-mode stretch
```

详细记录：

```text
SUMMARY_2026-06-23.md
```
