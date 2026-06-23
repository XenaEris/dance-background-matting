from __future__ import annotations

import numpy as np


def refine_alpha_guided(
    image_rgb: np.ndarray,
    alpha: np.ndarray,
    radius: int = 8,
    eps: float = 1e-4,
) -> np.ndarray:
    """Refine a hard mask into a softer alpha using guided filtering.

    Requires opencv-contrib-python-headless for cv2.ximgproc.guidedFilter.
    Falls back to a light Gaussian blur if ximgproc is unavailable.
    """

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for alpha refinement.") from exc

    alpha32 = np.clip(alpha.astype(np.float32), 0.0, 1.0)
    guide = image_rgb.astype(np.float32) / 255.0

    if hasattr(cv2, "ximgproc") and hasattr(cv2.ximgproc, "guidedFilter"):
        refined = cv2.ximgproc.guidedFilter(guide=guide, src=alpha32, radius=radius, eps=eps)
    else:
        refined = cv2.GaussianBlur(alpha32, (0, 0), sigmaX=max(radius / 3.0, 0.1))

    return np.clip(refined, 0.0, 1.0).astype(np.float32)


def refine_alpha_edge_band(
    image_rgb: np.ndarray,
    alpha: np.ndarray,
    guided_radius: int = 5,
    guided_eps: float = 1e-4,
    erode_px: int = 2,
    dilate_px: int = 3,
) -> np.ndarray:
    """Keep the foreground core sharp and only soften a narrow edge band."""

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for edge-band alpha refinement.") from exc

    hard = (alpha.astype(np.float32) > 0.5).astype(np.uint8)
    if hard.max() == 0:
        return hard.astype(np.float32)

    erode_kernel = _ellipse_kernel(max(erode_px, 0))
    dilate_kernel = _ellipse_kernel(max(dilate_px, 0))
    core = cv2.erode(hard, erode_kernel, iterations=1) if erode_px > 0 else hard
    outer = cv2.dilate(hard, dilate_kernel, iterations=1) if dilate_px > 0 else hard
    band = (outer > 0) & (core == 0)

    guided = refine_alpha_guided(
        image_rgb=image_rgb,
        alpha=outer.astype(np.float32),
        radius=guided_radius,
        eps=guided_eps,
    )

    refined = np.zeros_like(guided, dtype=np.float32)
    refined[core > 0] = 1.0
    refined[band] = guided[band]
    return np.clip(refined, 0.0, 1.0).astype(np.float32)


def harden_alpha(alpha: np.ndarray, gain: float = 1.0, bias: float = 0.0) -> np.ndarray:
    return np.clip(alpha.astype(np.float32) * gain + bias, 0.0, 1.0)


def choke_alpha(alpha: np.ndarray, pixels: int = 1, feather: float = 0.6) -> np.ndarray:
    """Slightly shrink alpha to remove source-background edge contamination."""

    if pixels <= 0:
        return np.clip(alpha.astype(np.float32), 0.0, 1.0)

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for alpha choking.") from exc

    alpha32 = np.clip(alpha.astype(np.float32), 0.0, 1.0)
    kernel = _ellipse_kernel(pixels)
    choked = cv2.erode(alpha32, kernel, iterations=1)
    if feather > 0:
        choked = cv2.GaussianBlur(choked, (0, 0), sigmaX=max(feather, 0.1))
        choked = np.minimum(choked, alpha32)
    return np.clip(choked, 0.0, 1.0).astype(np.float32)


def _ellipse_kernel(radius: int):
    import cv2

    size = radius * 2 + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
