from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.composite import composite_videos


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Composite a person video onto a clean background.")
    parser.add_argument("--human", required=True, help="Input video containing the person.")
    parser.add_argument("--background", required=True, help="Clean background video.")
    parser.add_argument("--output", default="outputs/result.mp4", help="Output MP4 path.")
    parser.add_argument("--work-dir", default="work/demo", help="Temporary work directory.")
    parser.add_argument("--max-seconds", type=float, default=10.0, help="Limit output duration for demos.")
    parser.add_argument("--no-harmonize", action="store_true", help="Disable foreground color adjustment.")
    parser.add_argument("--backend", choices=["diff", "rvm"], default="diff", help="Matting backend.")
    parser.add_argument("--rvm-model", choices=["mobilenetv3", "resnet50"], default="mobilenetv3")
    parser.add_argument("--rvm-downsample-ratio", type=float, default=None)
    parser.add_argument("--alpha-gain", type=float, default=1.0, help="Multiply alpha before compositing.")
    parser.add_argument("--alpha-bias", type=float, default=0.0, help="Add to alpha before compositing.")
    parser.add_argument("--background-mode", choices=["loop", "stretch"], default="loop")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = composite_videos(
        human_path=Path(args.human),
        background_path=Path(args.background),
        output_path=Path(args.output),
        work_dir=Path(args.work_dir),
        max_seconds=args.max_seconds,
        harmonize=not args.no_harmonize,
        backend=args.backend,
        rvm_model=args.rvm_model,
        rvm_downsample_ratio=args.rvm_downsample_ratio,
        alpha_gain=args.alpha_gain,
        alpha_bias=args.alpha_bias,
        background_mode=args.background_mode,
    )
    print(f"wrote {output.resolve()}")


if __name__ == "__main__":
    main()
