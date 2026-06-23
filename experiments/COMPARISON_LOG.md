# 对比实验记录

日期：2026-06-09

## 实验目的

在保留当前 RVM demo 的基础上，新增 SAM2 路线，用于验证它是否能更稳定地保留：

- 羽毛状/多孔隙头冠
- 手部边缘
- 长指甲等细小结构

当前判断：

```text
RVM 适合快速人像 alpha 抠像。
SAM2 更适合目标追踪和复杂部件保持。
SAM2 输出硬 mask，需要后续 refinement 才适合最终合成。
```

## 当前基线

### RVM resnet50

命令：

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

观察：

- 人物清晰时效果可用。
- 头冠、手部和细小边缘可能被吞。
- 滤镜虚化段不作为主要问题评价。

## SAM2 实验计划

### 阶段 1：只生成 mask

目标：

```text
human.mp4 -> SAM2 mask 视频
```

判断重点：

- 头冠是否被稳定追踪。
- 手部快速移动时是否丢失。
- 背景灯光是否被误选为人物。
- mask 是否闪烁。

命令：

```powershell
python .\scripts\run_sam2_mask.py `
  --video "C:\Users\51227\Downloads\human.mp4" `
  --prompts ".\configs\prompts\human_sam2_points.json" `
  --output-mask ".\outputs\sam2_mask_3s.mp4" `
  --output-alpha-dir ".\work\sam2_alpha_3s" `
  --work-dir ".\work\sam2_frames_3s" `
  --max-seconds 3 `
  --refine
```

### 阶段 2：mask refinement

目标：

```text
SAM2 hard mask + 原图 -> soft alpha
```

候选方法：

- OpenCV guided filter
- trimap + 图像 matting 模型
- SAM2 mask 与 RVM alpha 融合

### 阶段 3：合成对比

输出三版：

```text
RVM only
SAM2 hard mask
SAM2 + refined alpha
```

对比指标：

- 头冠完整度
- 手部/指甲完整度
- 边缘自然度
- 闪烁程度
- 背景误抠
- 处理耗时

从 SAM2 alpha 合成命令：

```powershell
python .\scripts\composite_from_alpha.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --alpha-dir ".\work\sam2_alpha_3s" `
  --output ".\outputs\result_sam2_alpha_3s.mp4" `
  --max-seconds 3
```

## 环境记录

当前 Windows Python 环境：

```text
Python 3.11
PyTorch 2.3.0+cu121
torchvision 0.18.0+cu121
CUDA available: True
```

SAM2 官方建议：

```text
Linux/WSL
PyTorch >= 2.5.1
torchvision >= 0.20.1
```

当前处理策略：

- 不升级现有 PyTorch，避免破坏已跑通的 RVM demo。
- 先以可选依赖方式安装 SAM2。
- 如果 SAM2 运行失败，记录为环境问题，后续切到 WSL 或独立 conda 环境。

## 2026-06-09 实施记录

已新增文件：

```text
configs/prompts/human_sam2_points.json
scripts/run_sam2_mask.py
scripts/composite_from_alpha.py
scripts/run_sam2_pipeline.py
src/refine.py
experiments/COMPARISON_LOG.md
```

已安装/验证：

```text
opencv-contrib-python-headless==4.10.0.84
numpy==1.26.4
sam2==1.1.0
hydra-core
iopath
huggingface_hub
```

第一次 3 秒 SAM2 测试：

```text
结果：失败
原因：3 秒测试只抽取 90 帧，但 prompt JSON 包含 frame_idx=165 的补点。
处理：已修改脚本，自动跳过超出当前处理帧数的提示点。
```

第二次 3 秒 SAM2 测试：

```text
结果：成功
输出：
  outputs/sam2_mask_3s.mp4
  work/sam2_alpha_3s/
  outputs/result_sam2_alpha_3s.mp4
观察：
  第 0 帧提示点可以稳定锁住人物主体和头冠。
  头冠整体完整度优于 RVM。
  guided filter 后 mask 边缘变软，但也偏厚，需要后续调半径或改成 trimap matting。
```

6 秒 SAM2 测试：

```text
结果：成功
输出：
  outputs/sam2_mask_6s.mp4
  work/sam2_alpha_6s/
  outputs/result_sam2_alpha_6s.mp4
关键帧：
  outputs/sam2_mask_6s_frame55.jpg
  outputs/result_sam2_alpha_6s_frame55.jpg
观察：
  第 165 帧手部补点生效。
  5.5 秒附近手部和头冠保留明显好于 RVM。
  手部/长指甲方向比继续调 RVM 更有前景。
  但 SAM2 mask 偏厚，裙摆和背景装饰边界仍需优化。
  SAM2 不是最终 alpha，需要后接 refinement。
```

RVM 回归验证：

```text
命令：1 秒 mobilenetv3 smoke test
结果：成功
说明：新增 SAM2/OpenCV 依赖没有破坏原有 RVM demo。
```

## 当前阶段结论

```text
RVM：适合作为快速基线和低成本处理模式。
SAM2：更适合复杂饰品、头冠、手部和指甲追踪。
当前 SAM2 + guided filter：主体更完整，但边缘偏厚，不够自然。
下一步重点：调 prompt、调 guided filter 参数，并尝试 SAM2 mask + RVM alpha 融合。
```

## 下一轮实验建议

1. 生成无 `--refine` 的 SAM2 hard mask，对比 guided filter 是否过度扩散。
2. 调小 guided filter 半径，例如 `--guided-radius 3`、`5`。
3. 为第 9 秒清晰正面帧增加补点，比较长时段稳定性。
4. 做融合方案：

```text
final_alpha = max(RVM_alpha, SAM2_mask_refined * local_confidence)
```

5. 如果 SAM2 在 Windows 上继续有 CUDA extension warning，后续转 WSL/独立 conda 环境，升级到官方推荐的 PyTorch 2.5.1+。

## 一键运行入口

已新增一键脚本：

```powershell
python .\scripts\run_sam2_pipeline.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_sam2_pipeline_6s.mp4" `
  --output-mask ".\outputs\sam2_mask_pipeline_6s.mp4" `
  --max-seconds 6
```

该脚本内部执行：

```text
1. run_sam2_mask.py 生成 SAM2 alpha
2. composite_from_alpha.py 合成最终视频
```
