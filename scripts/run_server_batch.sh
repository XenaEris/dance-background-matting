#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PATH="$HOME/bin/ffmpeg-static:$PATH"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

CHECKPOINT="${CHECKPOINT:-checkpoints/sam2_hiera_large.pt}"
MODEL_CONFIG="${MODEL_CONFIG:-configs/sam2/sam2_hiera_l.yaml}"
MAX_SECONDS="${MAX_SECONDS:-16}"

mkdir -p output outputs work logs

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffprobe not found. Add static ffmpeg to PATH first." >&2
  exit 1
fi

if [[ ! -f "$CHECKPOINT" ]]; then
  echo "checkpoint not found: $CHECKPOINT" >&2
  exit 1
fi

if [[ ! -f input/bg.mp4 ]]; then
  echo "background not found: input/bg.mp4" >&2
  exit 1
fi

for i in 1 2 3 4 5; do
  human="input/${i}.mp4"
  output="output/task${i}.mp4"
  mask="output/task${i}_mask.mp4"
  work_root="work/task${i}_sam2_large"
  log="logs/task${i}.log"

  if [[ ! -f "$human" ]]; then
    echo "missing input: $human" >&2
    exit 1
  fi

  echo "===== task ${i} started: $(date '+%F %T') =====" | tee "$log"
  python scripts/run_sam2_pipeline.py \
    --human "$human" \
    --background input/bg.mp4 \
    --output "$output" \
    --output-mask "$mask" \
    --work-root "$work_root" \
    --max-seconds "$MAX_SECONDS" \
    --model-id facebook/sam2-hiera-large \
    --checkpoint "$CHECKPOINT" \
    --model-config "$MODEL_CONFIG" \
    --background-mode stretch \
    --refine-mode edge-band \
    --guided-radius 5 \
    --edge-erode 2 \
    --edge-dilate 3 \
    --alpha-choke 2 \
    --alpha-choke-feather 0.5 \
    --foreground-sharpen 0.30 \
    --sharpen-radius 1.0 2>&1 | tee -a "$log"
  echo "===== task ${i} finished: $(date '+%F %T') =====" | tee -a "$log"
done

echo "all tasks finished: $(date '+%F %T')"
