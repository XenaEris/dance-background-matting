from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.composite import (
    _FrameReader,
    _FrameWriter,
    _alpha_composite,
    _harmonize_foreground,
)
from src.ffmpeg_utils import mux_audio, probe_video
from src.ffmpeg_utils import make_duration_matched_background
from src.refine import choke_alpha


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Composite video using precomputed alpha npy files.")
    parser.add_argument("--human", required=True)
    parser.add_argument("--background", required=True)
    parser.add_argument("--alpha-dir", required=True)
    parser.add_argument("--output", default="outputs/result_from_alpha.mp4")
    parser.add_argument("--work-dir", default="work/composite_from_alpha")
    parser.add_argument("--max-seconds", type=float, default=10.0)
    parser.add_argument("--alpha-gain", type=float, default=1.0)
    parser.add_argument("--alpha-bias", type=float, default=0.0)
    parser.add_argument("--alpha-choke", type=int, default=0)
    parser.add_argument("--alpha-choke-feather", type=float, default=0.6)
    parser.add_argument("--foreground-sharpen", type=float, default=0.0)
    parser.add_argument("--sharpen-radius", type=float, default=1.0)
    parser.add_argument("--background-mode", choices=["loop", "stretch"], default="loop")
    parser.add_argument("--no-harmonize", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    human_path = Path(args.human)
    background_path = Path(args.background)
    alpha_dir = Path(args.alpha_dir)
    output_path = Path(args.output)
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    human_info = probe_video(human_path)
    bg_info = probe_video(background_path)
    if (human_info.width, human_info.height) != (bg_info.width, bg_info.height):
        raise ValueError("Human and background videos must have the same resolution.")

    duration = min(human_info.duration, args.max_seconds)
    frame_count = int(duration * human_info.fps)
    alpha_files = sorted(alpha_dir.glob("*.npy"))[:frame_count]
    if not alpha_files:
        raise RuntimeError(f"No alpha npy files found in {alpha_dir}")

    silent_output = work_dir / "silent_result.mp4"
    effective_background_path = background_path
    loop_background = True
    if args.background_mode == "stretch":
        effective_background_path = make_duration_matched_background(
            background_path,
            work_dir / "background_stretched.mp4",
            target_duration=duration,
            fps=human_info.fps,
        )
        loop_background = False

    human_reader = _FrameReader(human_path, human_info.width, human_info.height)
    bg_reader = _FrameReader(effective_background_path, bg_info.width, bg_info.height, loop=loop_background)
    writer = _FrameWriter(silent_output, human_info.width, human_info.height, human_info.fps)

    try:
        for index, alpha_file in enumerate(alpha_files):
            human = human_reader.read()
            background = bg_reader.read()
            if human is None or background is None:
                break

            alpha = np.load(alpha_file).astype(np.float32)
            alpha = np.clip(alpha * args.alpha_gain + args.alpha_bias, 0.0, 1.0)
            if args.alpha_choke > 0:
                alpha = choke_alpha(alpha, pixels=args.alpha_choke, feather=args.alpha_choke_feather)
            foreground = (
                _harmonize_foreground(human, background, alpha)
                if not args.no_harmonize
                else human
            )
            if args.foreground_sharpen > 0:
                foreground = _sharpen_foreground(
                    foreground,
                    alpha,
                    amount=args.foreground_sharpen,
                    radius=args.sharpen_radius,
                )
            frame = _alpha_composite(foreground, background, alpha)
            writer.write(frame)
            if index % max(int(human_info.fps), 1) == 0:
                print(f"composited {index}/{len(alpha_files)} frames")
    finally:
        human_reader.close()
        bg_reader.close()
        writer.close()

    mux_audio(silent_output, human_path, output_path, duration)
    print(f"wrote {output_path.resolve()}")


def _sharpen_foreground(
    foreground: np.ndarray,
    alpha: np.ndarray,
    amount: float,
    radius: float,
) -> np.ndarray:
    import cv2

    fg = foreground.astype(np.float32)
    blurred = cv2.GaussianBlur(fg, (0, 0), sigmaX=max(radius, 0.1))
    sharpened = np.clip(fg + amount * (fg - blurred), 0, 255)
    mask = (alpha[..., None] > 0.05).astype(np.float32)
    mixed = sharpened * mask + fg * (1.0 - mask)
    return np.clip(mixed, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    main()
