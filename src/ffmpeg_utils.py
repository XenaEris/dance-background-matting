from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool


def run_command(args: list[str]) -> None:
    process = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(args)
            + "\n\nSTDOUT:\n"
            + process.stdout
            + "\n\nSTDERR:\n"
            + process.stderr
        )


def probe_video(path: str | Path) -> VideoInfo:
    args = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height,avg_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise RuntimeError(process.stderr)

    data = json.loads(process.stdout)
    video_stream = next(s for s in data["streams"] if s.get("codec_type") == "video")
    has_audio = any(s.get("codec_type") == "audio" for s in data["streams"])
    fps_raw = video_stream.get("avg_frame_rate", "30/1")
    numerator, denominator = fps_raw.split("/")
    fps = float(numerator) / float(denominator) if float(denominator) else 30.0

    return VideoInfo(
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        duration=float(data["format"]["duration"]),
        has_audio=has_audio,
    )


def mux_audio(
    silent_video: str | Path,
    audio_source: str | Path,
    output: str | Path,
    duration: float,
) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(silent_video),
        "-i",
        str(audio_source),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ]
    run_command(args)


def make_duration_matched_background(
    background_path: str | Path,
    output_path: str | Path,
    target_duration: float,
    fps: float,
) -> Path:
    """Create a silent background video stretched to target_duration."""

    background_path = Path(background_path)
    output_path = Path(output_path)
    info = probe_video(background_path)
    if info.duration <= 0:
        raise ValueError("Background duration must be positive.")

    ratio = target_duration / info.duration
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(background_path),
        "-an",
        "-filter:v",
        f"setpts={ratio:.10f}*PTS,fps={fps:.6f}",
        "-t",
        f"{target_duration:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "18",
        str(output_path),
    ]
    run_command(args)
    return output_path
