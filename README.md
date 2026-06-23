# Automated Video Matting Demo

This repository starts with a command-line demo for compositing a person video
onto a clean background video.

## Current demo

The first implementation supports two matting backends:

- `diff`: a background-difference baseline that runs without downloading model
  weights.
- `rvm`: Robust Video Matting via PyTorch Hub, intended for the real demo.

```powershell
python .\scripts\run_demo.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result.mp4" `
  --backend diff
```

For the RVM backend:

```powershell
python .\scripts\run_demo.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --output ".\outputs\result_rvm.mp4" `
  --backend rvm `
  --alpha-gain 1.6
```

The pipeline:

1. Reads both videos.
2. Loops or trims the background to match the requested duration.
3. Estimates a foreground alpha mask.
4. Applies simple mask cleanup and color harmonization.
5. Writes a temporary silent video.
6. Muxes the original human-video audio back into the final MP4.

The first RVM run downloads model files. Use `--rvm-model resnet50` if quality is
more important than speed; the default is `mobilenetv3`.

## SAM2 mask experiment

SAM2 is optional and currently experimental. It is used to generate a tracked
hard mask first; that mask can then be inspected or composited separately.

One-command SAM2 pipeline:

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
  --alpha-choke 2 `
  --alpha-choke-feather 0.5 `
  --foreground-sharpen 0.30 `
  --sharpen-radius 1.0 `
  --background-mode stretch
```

The separate two-step commands are still useful for debugging mask quality.

Stretch the background only:

```powershell
python .\scripts\stretch_background.py `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --match-video "C:\Users\51227\Downloads\human.mp4" `
  --output ".\outputs\背景拉伸_匹配人物视频.mp4"
```

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

Then composite from the generated alpha files:

```powershell
python .\scripts\composite_from_alpha.py `
  --human "C:\Users\51227\Downloads\human.mp4" `
  --background "C:\Users\51227\Downloads\bg.mp4" `
  --alpha-dir ".\work\sam2_alpha_3s" `
  --output ".\outputs\result_sam2_alpha_3s.mp4" `
  --max-seconds 3
```
