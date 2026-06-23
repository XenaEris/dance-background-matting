# 阶段报告：SAM2 路线阶段成果与人物虚化问题

日期：2026-06-10

## 阶段结论

本阶段的 SAM2 路线验证成功。

相比上一阶段的 RVM 方案，当前 SAM2 方案已经明显改善了复杂细节缺失问题，尤其是：

- 金色服装边缘和延展区域保留更完整。
- 头冠细节整体保持更好。
- 手部动作区域比 RVM 更稳定。
- 人物主体不再出现明显被“吞掉”的问题。

当前可认为：

```text
RVM：适合作为快速基线。
SAM2：更适合当前素材中的复杂头冠、服装延展、手部细节。
```

## 当前最佳运行方式

一键运行 SAM2 当前流程：

```powershell
cd "F:\研究组项目\舞蹈背景"

python .\scripts\run_sam2_pipeline.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_sam2_pipeline_full.mp4" `
  --output-mask ".\outputs\sam2_mask_pipeline_full.mp4" `
  --max-seconds 15.5
```

如果只做快速检查，可以把 `--max-seconds` 改成：

```text
6
10
15.5
```

说明：

- `human.mp4` 时长约 15.5 秒。
- `bg.mp4` 时长约 10.43 秒。
- 当前代码会循环背景视频以覆盖完整人物视频。

## 当前工作流

当前 SAM2 一键脚本内部流程：

```text
human.mp4
  |
  | 1. FFmpeg 抽帧
  v
逐帧 JPG
  |
  | 2. SAM2 根据提示点追踪人物
  v
逐帧 hard mask
  |
  | 3. Guided Filter 边缘软化
  v
soft alpha 序列
  |
  | 4. 使用 alpha 合成到 bg.mp4
  v
无声合成视频
  |
  | 5. 合回 human.mp4 原音频
  v
最终 MP4
```

核心文件：

```text
scripts/run_sam2_pipeline.py
scripts/run_sam2_mask.py
scripts/composite_from_alpha.py
src/refine.py
configs/prompts/human_sam2_points.json
```

## 已解决的问题

### 1. 衣服延展缺失

上一版 RVM 容易把服装边缘、裙摆延展、装饰区域当作背景吞掉。

当前 SAM2 通过提示点和视频目标追踪，可以更稳定地锁定人物整体区域，因此该问题已明显改善。

### 2. 头冠复杂边缘缺失

RVM 对细小、多孔隙、亮金色结构不稳定。

SAM2 对这类结构的“目标归属”判断更强，因此头冠完整度更好。

### 3. 手部细节保持

通过在关键帧加入手部提示点，SAM2 对手部动作段的保持明显优于 RVM。

## 当前主要缺点：人物略虚化

当前唯一明显缺点是：人物整体看起来略微发虚，不够锐。

初步判断原因不是单一模型问题，而是由以下几项叠加造成：

### 1. Guided Filter 软化半径偏大

当前 refinement 使用 guided filter 把 SAM2 hard mask 变成 soft alpha。

这个步骤能减少硬边和锯齿，但如果半径偏大，会让 alpha 过渡带变宽，人物边缘会显得发虚。

### 2. SAM2 mask 本身偏“厚”

SAM2 的目标是稳定分割和追踪，不是生成精细 alpha。

它保守地把人物周边区域也纳入 mask 后，再经过软化，就容易出现边缘厚、边界糊的问题。

### 3. 前景没有做锐化补偿

合成时前景直接来自原视频帧。经过 alpha 软化后，边缘视觉锐度下降，但当前没有做局部锐化补偿。

## 可能解决方案

建议下一步采用“硬核心 + 窄软边 + 前景锐化”的组合方案。

### 方案核心

不要让整个人物都被大范围软化，只在边缘窄区域做柔和过渡：

```text
SAM2 hard mask
  |
  | 1. 腐蚀得到人物硬核心
  | 2. 膨胀得到外边界
  | 3. 外边界 - 硬核心 = 窄边缘过渡区
  v
只在窄边缘区做 guided filter / blur
```

最终 alpha：

```text
人物内部：alpha = 1.0，保持清晰
边缘窄带：alpha = soft alpha，柔和过渡
背景区域：alpha = 0.0
```

这样可以避免当前“整个人物边缘过度发虚”的问题。

### 同时增加前景锐化

对人物区域做轻微 unsharp mask：

```text
foreground_sharp = foreground + amount * (foreground - gaussian_blur(foreground))
```

但只作用在人物区域，不锐化背景。

建议参数：

```text
sharpen_amount: 0.25 ~ 0.45
sharpen_radius: 1.0 ~ 1.5
edge_soft_radius: 3 ~ 5
```

## 下一步实验计划

### 实验 A：降低 guided filter 半径

当前默认：

```text
--guided-radius 8
```

建议测试：

```powershell
--guided-radius 3
--guided-radius 5
```

目标：

```text
减少边缘过宽导致的虚化。
```

### 实验 B：关闭 refinement 对照

运行：

```powershell
python .\scripts\run_sam2_pipeline.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_sam2_no_refine_10s.mp4" `
  --output-mask ".\outputs\sam2_mask_no_refine_10s.mp4" `
  --max-seconds 10 `
  --no-refine
```

目标：

```text
确认虚化主要来自 guided filter，还是来自 SAM2 mask 本身。
```

### 实验 C：新增 hard-core alpha refinement

新增一个 alpha 后处理模式：

```text
--refine-mode edge-band
```

预计逻辑：

```text
1. SAM2 mask 生成 hard mask
2. erode 得到 hard core
3. dilate 得到 soft band
4. 只在 soft band 中使用 guided filter
5. hard core 强制 alpha = 1
```

目标：

```text
既保留 SAM2 的完整人物范围，又避免整个人物变虚。
```

### 实验 D：人物区域轻微锐化

在合成前对人物前景做轻微锐化：

```text
--foreground-sharpen 0.35
```

目标：

```text
补偿合成后人物边缘和服装纹理的视觉锐度损失。
```

## 推荐优先级

下一步建议按以下顺序做：

```text
1. 先跑 guided-radius 3 / 5 对照
2. 跑 no-refine 对照
3. 实现 edge-band refinement
4. 再加 foreground sharpen
5. 最后输出 RVM / SAM2 / SAM2-edge-band 对比报告
```

## 当前阶段评价

本阶段成果是成功的。

最关键的业务问题“服装延展、头冠、手部细节容易丢失”已经通过 SAM2 路线明显改善。

剩余的人物虚化问题更像是后处理参数和 alpha refinement 策略问题，不是路线错误。下一步通过缩窄软边、保留硬核心、增加前景锐化，预计可以进一步改善。

## 2026-06-15 更新：edge-band 优化已实现

本轮目标：

```text
减少人物整体虚化，同时保留 SAM2 对服装延展、头冠、手部的细节优势。
```

已实现：

```text
1. 新增 edge-band alpha refinement。
2. 人物内部 hard core 强制 alpha = 1.0。
3. 只在窄边缘带做 guided filter。
4. 合成阶段新增人物前景 unsharp mask 锐化。
5. 一键 pipeline 默认 refine-mode 改为 edge-band。
```

涉及文件：

```text
src/refine.py
scripts/run_sam2_mask.py
scripts/composite_from_alpha.py
scripts/run_sam2_pipeline.py
```

当前推荐参数：

```text
--refine-mode edge-band
--guided-radius 5
--edge-erode 2
--edge-dilate 3
--foreground-sharpen 0.30
--sharpen-radius 1.0
```

已生成结果：

```text
outputs/result_sam2_edgeband_6s.mp4
outputs/sam2_mask_edgeband_6s.mp4
outputs/result_sam2_edgeband_10s.mp4
outputs/sam2_mask_edgeband_10s.mp4
```

10 秒版本信息：

```text
duration: 10.0s
resolution: 720x1280
fps: 30
video codec: H.264
audio codec: AAC
size: about 5.0 MB
```

观察结论：

```text
人物内部比 guided-only 版本更实、更清晰。
头冠、服装延展、手部仍然保持较好。
5.5 秒手部段效果可用。
9 秒清晰帧效果稳定。
人物外缘仍可能带入原视频黑色背景边，需要做轻微 alpha choke。
```

完整 15.5 秒版本尝试：

```text
结果：未完成
原因：当前 Windows + SAM2 环境下完整 15.5 秒任务超过 10 分钟超时。
处理：先交付 10 秒优化版；完整版本后续建议分段处理或切到 WSL/更稳定的 PyTorch 2.5.1+ 环境。
```

当前推荐运行命令：

```powershell
python .\scripts\run_sam2_pipeline.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_sam2_edgeband_10s.mp4" `
  --output-mask ".\outputs\sam2_mask_edgeband_10s.mp4" `
  --work-root ".\work\sam2_edgeband_10s" `
  --max-seconds 10 `
  --refine-mode edge-band `
  --guided-radius 5 `
  --edge-erode 2 `
  --edge-dilate 3 `
  --foreground-sharpen 0.30 `
  --sharpen-radius 1.0
```

下一步建议：

```text
1. 针对裙摆底部做局部 mask 约束。
2. 尝试 edge-erode=1 / edge-dilate=2，减少边缘带厚度。
3. 将完整视频改为分段处理后拼接。
4. 在 WSL 或新环境中升级 PyTorch/SAM2，减少 Windows extension warning 和长任务不稳定。
```

## 2026-06-15 更新：黑边问题修正

用户反馈：

```text
1. 人物身体外包了一层黑边，像原视频背景没有清理干净。
2. 底部青绿色三角形装饰属于背景，不应作为“裙摆问题”纳入缺陷判断。
```

判断：

```text
黑边来自 alpha mask 略厚，把原视频人物外侧的黑背景像素也带入了合成。
这不是裙摆问题，也不是背景装饰问题。
```

已实现：

```text
src/refine.py:
  新增 choke_alpha()

scripts/composite_from_alpha.py:
  新增 --alpha-choke
  新增 --alpha-choke-feather

scripts/run_sam2_pipeline.py:
  一键流程支持 alpha choke，默认 --alpha-choke 1
```

已生成对照：

```text
outputs/result_sam2_edgeband_choke1_10s.mp4
outputs/result_sam2_edgeband_choke2_10s.mp4
```

推荐当前去黑边版本：

```text
outputs/result_sam2_edgeband_choke2_10s.mp4
```

推荐参数：

```text
--alpha-choke 2
--alpha-choke-feather 0.5
```

说明：

```text
alpha-choke 会轻微收缩人物 alpha，优先清掉外侧黑边。
如果后续发现头冠或指甲被吃掉，可以退回 --alpha-choke 1。
底部青绿色三角形装饰后续不再作为人物抠像缺陷处理。
```

推荐运行命令：

```powershell
python .\scripts\run_sam2_pipeline.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_sam2_edgeband_choke2_10s.mp4" `
  --output-mask ".\outputs\sam2_mask_edgeband_10s.mp4" `
  --work-root ".\work\sam2_edgeband_10s" `
  --max-seconds 10 `
  --refine-mode edge-band `
  --guided-radius 5 `
  --edge-erode 2 `
  --edge-dilate 3 `
  --alpha-choke 2 `
  --alpha-choke-feather 0.5 `
  --foreground-sharpen 0.30 `
  --sharpen-radius 1.0
```
