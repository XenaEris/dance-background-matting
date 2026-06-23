from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ffmpeg_utils import make_duration_matched_background, probe_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stretch a background video to match a target duration.")
    parser.add_argument("--background", required=True)
    parser.add_argument("--output", default="outputs/background_stretched.mp4")
    parser.add_argument("--target-duration", type=float, default=None)
    parser.add_argument("--match-video", default=None, help="Use this video's duration and fps as the target.")
    parser.add_argument("--fps", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_duration = args.target_duration
    fps = args.fps

    if args.match_video:
        info = probe_video(args.match_video)
        target_duration = info.duration
        fps = info.fps

    if target_duration is None:
        raise ValueError("Provide either --target-duration or --match-video.")

    output = make_duration_matched_background(
        args.background,
        args.output,
        target_duration=target_duration,
        fps=fps,
    )
    print(f"wrote {output.resolve()}")


if __name__ == "__main__":
    main()

