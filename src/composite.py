from __future__ import annotations

from pathlib import Path

import numpy as np

from .ffmpeg_utils import make_duration_matched_background, mux_audio, probe_video
from .matting import create_matting_backend


def composite_videos(
    human_path: str | Path,
    background_path: str | Path,
    output_path: str | Path,
    work_dir: str | Path,
    max_seconds: float | None = None,
    harmonize: bool = True,
    backend: str = "diff",
    rvm_model: str = "mobilenetv3",
    rvm_downsample_ratio: float | None = None,
    alpha_gain: float = 1.0,
    alpha_bias: float = 0.0,
    background_mode: str = "loop",
) -> Path:
    human_path = Path(human_path)
    background_path = Path(background_path)
    output_path = Path(output_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    human_info = probe_video(human_path)
    bg_info = probe_video(background_path)
    if (human_info.width, human_info.height) != (bg_info.width, bg_info.height):
        raise ValueError("The first demo requires both videos to have the same resolution.")

    fps = human_info.fps
    duration = min(human_info.duration, max_seconds or human_info.duration)
    frame_count = int(duration * fps)
    silent_output = work_dir / "silent_result.mp4"
    effective_background_path = background_path
    loop_background = True
    if background_mode == "stretch":
        effective_background_path = make_duration_matched_background(
            background_path,
            work_dir / "background_stretched.mp4",
            target_duration=duration,
            fps=fps,
        )
        loop_background = False
    elif background_mode != "loop":
        raise ValueError(f"Unknown background mode: {background_mode}")

    human_reader = _FrameReader(human_path, human_info.width, human_info.height)
    bg_reader = _FrameReader(effective_background_path, bg_info.width, bg_info.height, loop=loop_background)
    writer = _FrameWriter(silent_output, human_info.width, human_info.height, fps)
    matting = create_matting_backend(
        backend,
        rvm_model=rvm_model,
        rvm_downsample_ratio=rvm_downsample_ratio,
    )

    try:
        for index in range(frame_count):
            human = human_reader.read()
            background = bg_reader.read()
            if human is None:
                break
            if background is None:
                raise RuntimeError("Background reader unexpectedly returned no frame.")

            alpha = matting.estimate_alpha(human, background)
            alpha = np.clip(alpha * alpha_gain + alpha_bias, 0.0, 1.0)
            foreground = _harmonize_foreground(human, background, alpha) if harmonize else human
            frame = _alpha_composite(foreground, background, alpha)
            writer.write(frame)

            if index % max(int(fps), 1) == 0:
                print(f"processed {index}/{frame_count} frames")
    finally:
        human_reader.close()
        bg_reader.close()
        writer.close()

    mux_audio(silent_output, human_path, output_path, duration)
    return output_path


def _alpha_composite(foreground: np.ndarray, background: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    a = alpha[..., None]
    mixed = foreground.astype(np.float32) * a + background.astype(np.float32) * (1.0 - a)
    return np.clip(mixed, 0, 255).astype(np.uint8)


def _harmonize_foreground(
    foreground: np.ndarray,
    background: np.ndarray,
    alpha: np.ndarray,
) -> np.ndarray:
    mask = alpha > 0.25
    if not np.any(mask):
        return foreground

    fg = foreground.astype(np.float32)
    bg = background.astype(np.float32)
    fg_mean = fg[mask].mean(axis=0)
    bg_mean = bg[mask].mean(axis=0)
    gain = np.clip((bg_mean + 18.0) / (fg_mean + 18.0), 0.75, 1.25)

    adjusted = fg * gain
    adjusted = adjusted * 1.04 + 4.0
    return np.clip(adjusted, 0, 255).astype(np.uint8)


class _FrameReader:
    def __init__(self, path: Path, width: int, height: int, loop: bool = False) -> None:
        self.path = path
        self.width = width
        self.height = height
        self.loop = loop
        self._process = None
        self._start()

    def _start(self) -> None:
        import subprocess

        args = [
            "ffmpeg",
            "-v",
            "error",
            "-stream_loop",
            "-1" if self.loop else "0",
            "-i",
            str(self.path),
            "-f",
            "image2pipe",
            "-pix_fmt",
            "rgb24",
            "-vcodec",
            "rawvideo",
            "-",
        ]
        if not self.loop:
            args = [arg for arg in args if arg != "-stream_loop" and arg != "0"]
        self._process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def read(self) -> np.ndarray | None:
        assert self._process is not None and self._process.stdout is not None
        size = self.width * self.height * 3
        raw = self._process.stdout.read(size)
        if len(raw) != size:
            return None
        return np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3))

    def close(self) -> None:
        if self._process is not None:
            self._process.kill()
            self._process.wait()


class _FrameWriter:
    def __init__(self, path: Path, width: int, height: int, fps: float) -> None:
        import subprocess

        self.path = path
        args = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
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
            "-preset",
            "medium",
            "-crf",
            "18",
            str(path),
        ]
        self._process = subprocess.Popen(args, stdin=subprocess.PIPE)

    def write(self, frame: np.ndarray) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(frame.tobytes())

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        self._process.wait()
