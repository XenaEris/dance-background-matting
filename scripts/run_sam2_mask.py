from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ffmpeg_utils import probe_video
from src.refine import refine_alpha_edge_band, refine_alpha_guided


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a SAM2 video-mask experiment.")
    parser.add_argument("--video", required=True, help="Input video to segment.")
    parser.add_argument("--prompts", required=True, help="JSON prompt file with points and labels.")
    parser.add_argument("--output-mask", default="outputs/sam2_mask.mp4", help="Mask preview MP4.")
    parser.add_argument("--output-alpha-dir", default="work/sam2_alpha", help="Directory for alpha npy files.")
    parser.add_argument("--work-dir", default="work/sam2_frames", help="Temporary frame directory.")
    parser.add_argument("--model-id", default="facebook/sam2-hiera-large", help="SAM2 Hugging Face model id.")
    parser.add_argument("--checkpoint", help="Local SAM2 checkpoint path. If set, skips Hugging Face download.")
    parser.add_argument("--model-config", default="configs/sam2.1/sam2.1_hiera_l.yaml")
    parser.add_argument("--max-seconds", type=float, default=10.0)
    parser.add_argument("--refine", action="store_true", help="Apply alpha refinement to masks.")
    parser.add_argument("--refine-mode", choices=["guided", "edge-band"], default="guided")
    parser.add_argument("--guided-radius", type=int, default=8)
    parser.add_argument("--guided-eps", type=float, default=1e-4)
    parser.add_argument("--edge-erode", type=int, default=2)
    parser.add_argument("--edge-dilate", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video = Path(args.video)
    prompts = _load_prompts(Path(args.prompts))
    work_dir = Path(args.work_dir)
    alpha_dir = Path(args.output_alpha_dir)
    mask_video = Path(args.output_mask)

    info = probe_video(video)
    duration = min(info.duration, args.max_seconds)
    frame_count = int(duration * info.fps)

    _prepare_clean_dir(work_dir)
    _prepare_clean_dir(alpha_dir)
    mask_video.parent.mkdir(parents=True, exist_ok=True)

    print(f"extracting {frame_count} frames to {work_dir}")
    _extract_frames(video, work_dir, duration)

    frame_paths = sorted(work_dir.glob("*.jpg"))
    if not frame_paths:
        raise RuntimeError("No frames were extracted.")

    if args.checkpoint:
        print(f"loading SAM2 model from checkpoint: {args.checkpoint}")
    else:
        print(f"loading SAM2 model: {args.model_id}")
    predictor = _load_sam2_predictor(args.model_id, args.checkpoint, args.model_config)

    import torch

    use_cuda = torch.cuda.is_available()
    autocast_device = "cuda" if use_cuda else "cpu"
    with torch.inference_mode():
        autocast_ctx = torch.autocast(autocast_device, dtype=torch.bfloat16) if use_cuda else _NullContext()
        with autocast_ctx:
            state = predictor.init_state(video_path=str(work_dir))

            for prompt in prompts:
                if int(prompt["frame_idx"]) >= frame_count:
                    print(
                        f"skipping prompt at frame {prompt['frame_idx']} "
                        f"because only {frame_count} frames are being processed"
                    )
                    continue
                _add_prompt(predictor, state, prompt)

            masks_by_frame: dict[int, np.ndarray] = {}
            for frame_idx, object_ids, masks in predictor.propagate_in_video(state):
                if frame_idx >= frame_count:
                    break
                masks_by_frame[frame_idx] = _merge_masks(masks)
                if frame_idx % max(int(info.fps), 1) == 0:
                    print(f"sam2 propagated {frame_idx}/{frame_count} frames")

    print(f"writing alpha npy files to {alpha_dir}")
    _write_alpha_files(
        masks_by_frame=masks_by_frame,
        frame_paths=frame_paths,
        alpha_dir=alpha_dir,
        refine=args.refine,
        refine_mode=args.refine_mode,
        guided_radius=args.guided_radius,
        guided_eps=args.guided_eps,
        edge_erode=args.edge_erode,
        edge_dilate=args.edge_dilate,
    )

    print(f"writing mask preview video to {mask_video}")
    _write_mask_preview(alpha_dir, mask_video, info.width, info.height, info.fps)
    print(f"wrote {mask_video.resolve()}")


def _load_sam2_predictor(model_id: str, checkpoint: str | None, model_config: str):
    try:
        from sam2.sam2_video_predictor import SAM2VideoPredictor
    except ImportError as exc:
        raise RuntimeError("SAM2 is not installed. Install it before running this experiment.") from exc

    if checkpoint:
        from sam2.build_sam import build_sam2_video_predictor

        return build_sam2_video_predictor(model_config, checkpoint)

    return SAM2VideoPredictor.from_pretrained(model_id)


def _load_prompts(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    prompts = data.get("objects")
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("Prompt JSON must contain a non-empty 'objects' list.")
    return prompts


def _add_prompt(predictor, state, prompt: dict) -> None:
    frame_idx = int(prompt["frame_idx"])
    obj_id = int(prompt["obj_id"])
    points = np.asarray(prompt["points"], dtype=np.float32)
    labels = np.asarray(prompt["labels"], dtype=np.int32)

    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Prompt points must be [[x, y], ...].")
    if len(points) != len(labels):
        raise ValueError("Prompt points and labels must have the same length.")

    if hasattr(predictor, "add_new_points_or_box"):
        predictor.add_new_points_or_box(
            inference_state=state,
            frame_idx=frame_idx,
            obj_id=obj_id,
            points=points,
            labels=labels,
        )
    else:
        predictor.add_new_points(
            inference_state=state,
            frame_idx=frame_idx,
            obj_id=obj_id,
            points=points,
            labels=labels,
        )


def _merge_masks(masks) -> np.ndarray:
    import torch

    if isinstance(masks, torch.Tensor):
        tensor = masks.detach().float().cpu()
        if tensor.ndim == 4:
            tensor = tensor[:, 0]
        merged = (tensor > 0).any(dim=0).numpy()
    else:
        merged = np.asarray(masks)
        if merged.ndim > 2:
            merged = np.any(merged > 0, axis=0)
    return merged.astype(np.float32)


def _write_alpha_files(
    masks_by_frame: dict[int, np.ndarray],
    frame_paths: list[Path],
    alpha_dir: Path,
    refine: bool,
    refine_mode: str,
    guided_radius: int,
    guided_eps: float,
    edge_erode: int,
    edge_dilate: int,
) -> None:
    import cv2

    previous = None
    for idx, frame_path in enumerate(frame_paths):
        alpha = masks_by_frame.get(idx)
        if alpha is None:
            alpha = previous if previous is not None else np.zeros((1, 1), dtype=np.float32)
        if refine:
            image_bgr = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            if refine_mode == "guided":
                alpha = refine_alpha_guided(image_rgb, alpha, radius=guided_radius, eps=guided_eps)
            elif refine_mode == "edge-band":
                alpha = refine_alpha_edge_band(
                    image_rgb,
                    alpha,
                    guided_radius=guided_radius,
                    guided_eps=guided_eps,
                    erode_px=edge_erode,
                    dilate_px=edge_dilate,
                )
            else:
                raise ValueError(f"Unknown refine mode: {refine_mode}")
        previous = alpha
        np.save(alpha_dir / f"{idx:05d}.npy", alpha.astype(np.float32))


def _write_mask_preview(alpha_dir: Path, output: Path, width: int, height: int, fps: float) -> None:
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-s",
            f"{width}x{height}",
            "-r",
            f"{fps:.6f}",
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    assert process.stdin is not None
    for alpha_file in sorted(alpha_dir.glob("*.npy")):
        alpha = np.load(alpha_file)
        process.stdin.write(np.clip(alpha * 255.0, 0, 255).astype(np.uint8).tobytes())
    process.stdin.close()
    process.wait()
    if process.returncode != 0:
        raise RuntimeError("Failed to encode mask preview video.")


def _extract_frames(video: Path, frame_dir: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(video),
            "-q:v",
            "2",
            str(frame_dir / "%05d.jpg"),
        ],
        check=True,
    )


def _prepare_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


if __name__ == "__main__":
    main()
