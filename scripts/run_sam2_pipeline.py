from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SAM2 mask generation and compositing in one command.")
    parser.add_argument("--human", required=True, help="Input video containing the person.")
    parser.add_argument("--background", required=True, help="Clean background video.")
    parser.add_argument("--prompts", default="configs/prompts/human_sam2_points.json")
    parser.add_argument("--output", default="outputs/result_sam2_pipeline.mp4")
    parser.add_argument("--output-mask", default="outputs/sam2_mask_pipeline.mp4")
    parser.add_argument("--work-root", default="work/sam2_pipeline")
    parser.add_argument("--max-seconds", type=float, default=6.0)
    parser.add_argument("--model-id", default="facebook/sam2-hiera-large")
    parser.add_argument("--checkpoint", help="Local SAM2 checkpoint path. If set, skips Hugging Face download.")
    parser.add_argument("--model-config", default="configs/sam2.1/sam2.1_hiera_l.yaml")
    parser.add_argument("--no-refine", action="store_true", help="Disable guided-filter refinement.")
    parser.add_argument("--refine-mode", choices=["guided", "edge-band"], default="edge-band")
    parser.add_argument("--guided-radius", type=int, default=8)
    parser.add_argument("--guided-eps", type=float, default=1e-4)
    parser.add_argument("--edge-erode", type=int, default=2)
    parser.add_argument("--edge-dilate", type=int, default=3)
    parser.add_argument("--alpha-gain", type=float, default=1.0)
    parser.add_argument("--alpha-bias", type=float, default=0.0)
    parser.add_argument("--alpha-choke", type=int, default=1)
    parser.add_argument("--alpha-choke-feather", type=float, default=0.6)
    parser.add_argument("--foreground-sharpen", type=float, default=0.25)
    parser.add_argument("--sharpen-radius", type=float, default=1.0)
    parser.add_argument("--background-mode", choices=["loop", "stretch"], default="stretch")
    parser.add_argument("--no-harmonize", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.work_root)
    frame_dir = root / "frames"
    alpha_dir = root / "alpha"
    composite_work = root / "composite"

    run_mask_cmd = [
        sys.executable,
        "scripts/run_sam2_mask.py",
        "--video",
        args.human,
        "--prompts",
        args.prompts,
        "--output-mask",
        args.output_mask,
        "--output-alpha-dir",
        str(alpha_dir),
        "--work-dir",
        str(frame_dir),
        "--model-id",
        args.model_id,
        "--model-config",
        args.model_config,
        "--max-seconds",
        str(args.max_seconds),
        "--guided-radius",
        str(args.guided_radius),
        "--guided-eps",
        str(args.guided_eps),
        "--refine-mode",
        args.refine_mode,
        "--edge-erode",
        str(args.edge_erode),
        "--edge-dilate",
        str(args.edge_dilate),
    ]
    if args.checkpoint:
        run_mask_cmd.extend(["--checkpoint", args.checkpoint])
    if not args.no_refine:
        run_mask_cmd.append("--refine")

    composite_cmd = [
        sys.executable,
        "scripts/composite_from_alpha.py",
        "--human",
        args.human,
        "--background",
        args.background,
        "--alpha-dir",
        str(alpha_dir),
        "--output",
        args.output,
        "--work-dir",
        str(composite_work),
        "--max-seconds",
        str(args.max_seconds),
        "--alpha-gain",
        str(args.alpha_gain),
        "--alpha-bias",
        str(args.alpha_bias),
        "--alpha-choke",
        str(args.alpha_choke),
        "--alpha-choke-feather",
        str(args.alpha_choke_feather),
        "--foreground-sharpen",
        str(args.foreground_sharpen),
        "--sharpen-radius",
        str(args.sharpen_radius),
        "--background-mode",
        args.background_mode,
    ]
    if args.no_harmonize:
        composite_cmd.append("--no-harmonize")

    print("step 1/2: generating SAM2 alpha")
    subprocess.run(run_mask_cmd, check=True)

    print("step 2/2: compositing final video")
    subprocess.run(composite_cmd, check=True)

    print(f"wrote {Path(args.output).resolve()}")
    print(f"mask preview {Path(args.output_mask).resolve()}")


if __name__ == "__main__":
    main()
