from __future__ import annotations

import numpy as np


class MattingBackend:
    def estimate_alpha(self, human_rgb: np.ndarray, background_rgb: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class DifferenceMatting:
    """A no-download baseline for fixed-scene demos.

    This is not a replacement for RVM/SAM2. It is a practical first pass that
    works best when the two videos are similarly framed and the person video has
    a darker or cleaner background than the replacement background.
    """

    def __init__(
        self,
        threshold: float = 0.10,
        soft_width: float = 0.20,
        temporal_blend: float = 0.70,
    ) -> None:
        self.threshold = threshold
        self.soft_width = soft_width
        self.temporal_blend = temporal_blend
        self._prev_alpha: np.ndarray | None = None

    def estimate_alpha(self, human_rgb: np.ndarray, background_rgb: np.ndarray) -> np.ndarray:
        human = human_rgb.astype(np.float32) / 255.0
        background = background_rgb.astype(np.float32) / 255.0

        diff = np.linalg.norm(human - background, axis=2) / np.sqrt(3.0)
        saturation = human.max(axis=2) - human.min(axis=2)
        brightness = human.mean(axis=2)

        # The person is bright and saturated in the sample videos. Combining
        # color distance with brightness reduces false positives in black sky.
        raw = np.maximum(diff, saturation * 0.75)
        raw = np.maximum(raw, np.clip((brightness - 0.10) * 1.6, 0.0, 1.0))

        alpha = np.clip((raw - self.threshold) / max(self.soft_width, 1e-6), 0.0, 1.0)
        alpha = _box_blur(alpha, radius=2)
        alpha = _smoothstep(alpha)

        if self._prev_alpha is not None:
            alpha = self.temporal_blend * self._prev_alpha + (1.0 - self.temporal_blend) * alpha
        self._prev_alpha = alpha
        return alpha.astype(np.float32)


class RvmMatting(MattingBackend):
    """Robust Video Matting backend loaded through PyTorch Hub."""

    def __init__(
        self,
        model_name: str = "mobilenetv3",
        device: str | None = None,
        downsample_ratio: float | None = None,
    ) -> None:
        import torch

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.downsample_ratio = downsample_ratio
        try:
            self.model = torch.hub.load("PeterL1n/RobustVideoMatting", model_name, pretrained=True)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load RVM through PyTorch Hub. This usually means the first run "
                "needs network access to download the repository and weights."
            ) from exc
        self.model = self.model.to(self.device).eval()
        self.rec = [None, None, None, None]

    def estimate_alpha(self, human_rgb: np.ndarray, background_rgb: np.ndarray) -> np.ndarray:
        del background_rgb
        torch = self.torch
        frame = torch.from_numpy(human_rgb.copy()).to(self.device)
        frame = frame.float().permute(2, 0, 1).unsqueeze(0).unsqueeze(0) / 255.0
        with torch.no_grad():
            _fgr, pha, *self.rec = self.model(frame, *self.rec, self.downsample_ratio)
        alpha = pha[0, 0, 0].detach().float().cpu().numpy()
        return np.clip(alpha, 0.0, 1.0).astype(np.float32)


def create_matting_backend(
    name: str,
    rvm_model: str = "mobilenetv3",
    rvm_downsample_ratio: float | None = None,
) -> MattingBackend:
    if name == "diff":
        return DifferenceMatting()
    if name == "rvm":
        return RvmMatting(model_name=rvm_model, downsample_ratio=rvm_downsample_ratio)
    raise ValueError(f"Unknown matting backend: {name}")


def _smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _box_blur(alpha: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return alpha
    padded = np.pad(alpha, radius, mode="edge")
    out = np.zeros_like(alpha, dtype=np.float32)
    kernel_area = float((radius * 2 + 1) ** 2)
    for dy in range(radius * 2 + 1):
        for dx in range(radius * 2 + 1):
            out += padded[dy : dy + alpha.shape[0], dx : dx + alpha.shape[1]]
    return out / kernel_area
