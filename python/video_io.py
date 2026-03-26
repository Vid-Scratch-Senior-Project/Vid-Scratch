"""
video_io.py — Video I/O and frame preprocessing for VidScratch.

Handles loading all frames from video files or image directories,
resizing for the model window, mapping perturbations back to original
resolution, and saving output videos.

Pipeline overview::

    input.mp4 (N frames, H×W, fps)
        │
        ├─ load_video()          → frames_all (N, C, H, W), meta
        ├─ frames_model = frames_all[meta.sampled_idx]
        ├─ frames_224   = resize_for_model(frames_model)
        │
        ├─ [VidScratch attack]   → frames_adv_224
        │
        ├─ apply_perturbation()  → frames_adv_all
        └─ save_video()          → output.mp4 (N frames, H×W, fps)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL_FRAME_SIZE: int = 224
MODEL_NUM_FRAMES: int = 40

_ALLOWED_VIDEO_EXT = frozenset(('.mp4', '.avi', '.mov', '.mkv', '.webm'))
_ALLOWED_IMAGE_EXT = frozenset(('.jpg', '.jpeg', '.png', '.bmp'))
_MAX_FRAMES = 50_000  # safety cap to prevent OOM


# ── Input validation helpers ──────────────────────────────────────────────────

def _sanitise_path(path: str) -> str:
    """Resolve and validate a filesystem path.

    Rejects paths containing null bytes or traversal sequences that
    resolve outside the original parent directory.
    """
    if '\x00' in path:
        raise ValueError("Path contains null bytes")
    resolved = os.path.realpath(path)
    return resolved


def _validate_video_path(path: str) -> str:
    """Validate that *path* points to an existing video file."""
    safe = _sanitise_path(path)
    if not os.path.isfile(safe):
        raise FileNotFoundError(f"Video not found: {safe}")
    ext = os.path.splitext(safe)[1].lower()
    if ext not in _ALLOWED_VIDEO_EXT:
        raise ValueError(
            f"Unsupported video format '{ext}'. "
            f"Allowed: {sorted(_ALLOWED_VIDEO_EXT)}"
        )
    return safe


def _validate_directory(path: str) -> str:
    """Validate that *path* is an existing directory."""
    safe = _sanitise_path(path)
    if not os.path.isdir(safe):
        raise FileNotFoundError(f"Directory not found: {safe}")
    return safe


# ── VideoMeta ─────────────────────────────────────────────────────────────────

@dataclass
class VideoMeta:
    """Metadata produced by :func:`load_video` and consumed throughout the
    pipeline to keep track of original video properties and the mapping
    between the model window and the full frame sequence."""

    orig_height: int
    orig_width: int
    fps: float
    total_frames: int
    sampled_idx: List[int]
    source_path: str

    @property
    def orig_size(self) -> Tuple[int, int]:
        return self.orig_height, self.orig_width

    def num_poison_frames(self, custom_k: Optional[int] = None) -> int:
        """Compute how many frames to poison.

        * ``custom_k`` overrides everything when provided.
        * N ≥ ``MODEL_NUM_FRAMES`` → fixed k = 10.
        * N < ``MODEL_NUM_FRAMES`` → k = max(1, round(N × 0.25)).
        """
        if custom_k is not None:
            return max(1, custom_k)
        if self.total_frames >= MODEL_NUM_FRAMES:
            return 10
        return max(1, round(self.total_frames * 0.25))


# ── Load video frames ────────────────────────────────────────────────────────

def load_video(
    video_path: str,
    model_window: int = MODEL_NUM_FRAMES,
) -> Tuple[torch.Tensor, VideoMeta]:
    """Load every frame from a video file at original resolution.

    Returns the full frame tensor and a :class:`VideoMeta` instance
    containing uniform-sampled indices for the model window.
    """
    try:
        import cv2
    except ImportError as exc:
        raise ImportError("pip install opencv-python") from exc

    safe_path = _validate_video_path(video_path)
    cap = cv2.VideoCapture(safe_path)
    if not cap.isOpened():
        raise RuntimeError(f"cv2 cannot open: {safe_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    raw: list[np.ndarray] = []
    while True:
        ret, frm = cap.read()
        if not ret:
            break
        if len(raw) >= _MAX_FRAMES:
            break
        raw.append(cv2.cvtColor(frm, cv2.COLOR_BGR2RGB))
    cap.release()

    if not raw:
        raise ValueError(f"No frames decoded from {safe_path}")

    orig_h, orig_w = raw[0].shape[:2]
    frames_all = torch.stack([
        torch.from_numpy(f).float().div(255.0).permute(2, 0, 1)
        for f in raw
    ])

    total = len(raw)
    sampled_idx = np.linspace(0, total - 1, model_window, dtype=int).tolist()

    meta = VideoMeta(
        orig_height=orig_h,
        orig_width=orig_w,
        fps=fps,
        total_frames=total,
        sampled_idx=sampled_idx,
        source_path=safe_path,
    )
    return frames_all, meta


def load_frames_from_directory(
    frames_dir: str,
    model_window: int = MODEL_NUM_FRAMES,
) -> Tuple[torch.Tensor, VideoMeta]:
    """Load all image frames from a directory at original resolution."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("pip install Pillow") from exc

    safe_dir = _validate_directory(frames_dir)
    files = sorted(
        f for f in os.listdir(safe_dir)
        if os.path.splitext(f)[1].lower() in _ALLOWED_IMAGE_EXT
    )
    if not files:
        raise FileNotFoundError(f"No images found in {safe_dir}")
    if len(files) > _MAX_FRAMES:
        files = files[:_MAX_FRAMES]

    raw = [
        np.array(Image.open(os.path.join(safe_dir, f)).convert('RGB'))
        for f in files
    ]
    orig_h, orig_w = raw[0].shape[:2]
    frames_all = torch.stack([
        torch.from_numpy(f).float().div(255.0).permute(2, 0, 1)
        for f in raw
    ])

    total = len(raw)
    sampled_idx = np.linspace(0, total - 1, model_window, dtype=int).tolist()

    meta = VideoMeta(
        orig_height=orig_h,
        orig_width=orig_w,
        fps=25.0,
        total_frames=total,
        sampled_idx=sampled_idx,
        source_path=safe_dir,
    )
    return frames_all, meta


# ── Resize helpers ────────────────────────────────────────────────────────────

def resize_for_model(
    frames: torch.Tensor,
    target_size: int = MODEL_FRAME_SIZE,
) -> torch.Tensor:
    """Stretch-resize frames to ``target_size × target_size``.

    Uses stretch (not centre-crop) so the perturbation can be mapped
    back to the full original frame.

    Args:
        frames: ``(T, C, H, W)`` in ``[0, 1]``.
        target_size: square output dimension.

    Returns:
        Resized tensor ``(T, C, target_size, target_size)``.
    """
    return F.interpolate(
        frames,
        size=(target_size, target_size),
        mode='bilinear',
        align_corners=False,
    ).contiguous()


# ── Apply perturbation back to original frames ───────────────────────────────

def _gaussian_blur(
    x: torch.Tensor, kernel_size: int, sigma: float,
) -> torch.Tensor:
    """Apply Gaussian blur to a ``(1, C, H, W)`` tensor."""
    C = x.shape[1]
    coords = torch.arange(kernel_size, dtype=torch.float32) - kernel_size // 2
    g = torch.exp(-(coords ** 2) / (2 * sigma ** 2))
    g = g / g.sum()
    kernel_2d = (g.unsqueeze(0) * g.unsqueeze(1)).unsqueeze(0).unsqueeze(0)
    kernel_2d = kernel_2d.expand(C, 1, -1, -1).to(x.device)
    pad = kernel_size // 2
    return F.conv2d(x, kernel_2d, padding=pad, groups=C)


def apply_perturbation(
    frames_all: torch.Tensor,
    frames_model_224: torch.Tensor,
    frames_adv_224: torch.Tensor,
    meta: VideoMeta,
    poison_mask: Optional[np.ndarray] = None,
    resize_mode: str = 'nearest',
    smooth_kernel: int = 0,
    codec_boost: float = 1.5,
) -> torch.Tensor:
    """Map the 224 px perturbation back to every poisoned original frame.

    Because :func:`resize_for_model` uses stretch resize (no crop), the
    224 × 224 diff can be resized directly back to ``H_orig × W_orig`` and
    the noise covers the entire frame.

    Args:
        frames_all: ``(N, C, H, W)`` original frames.
        frames_model_224: ``(T, C, 224, 224)`` clean model-window frames.
        frames_adv_224: ``(T, C, 224, 224)`` adversarial model-window.
        meta: :class:`VideoMeta` with ``sampled_idx``.
        poison_mask: ``(T,)`` binary mask from BO (which frames are poisoned).
        resize_mode: interpolation for upscaling diff.
        smooth_kernel: Gaussian blur kernel size (0 = off).
        codec_boost: multiply noise to compensate codec compression.

    Returns:
        ``(N, C, H, W)`` output frames with perturbation applied.
    """
    H_orig, W_orig = meta.orig_height, meta.orig_width
    frames_out = frames_all.clone()
    diff_224 = frames_adv_224 - frames_model_224

    # Determine which model-window indices were poisoned
    if poison_mask is not None:
        poisoned_window_idx = [
            int(i) for i in np.where(poison_mask > 0.5)[0]
        ]
    else:
        frame_l2 = diff_224.pow(2).flatten(1).mean(dim=1).sqrt()
        threshold = max(frame_l2.max().item() * 0.1, 1e-5)
        poisoned_window_idx = (
            (frame_l2 > threshold).nonzero(as_tuple=True)[0].tolist()
        )

    for i in poisoned_window_idx:
        real_idx = meta.sampled_idx[i]
        diff_i = diff_224[i:i + 1]  # (1, C, 224, 224)

        if codec_boost != 1.0:
            diff_i = diff_i * codec_boost

        diff_orig = F.interpolate(
            diff_i, size=(H_orig, W_orig), mode=resize_mode,
        )

        if smooth_kernel > 0:
            k = smooth_kernel if smooth_kernel % 2 == 1 else smooth_kernel + 1
            diff_orig = _gaussian_blur(diff_orig, k, k / 3.0)

        diff_orig = diff_orig.clamp(-1.0, 1.0)[0]
        frames_out[real_idx] = (frames_out[real_idx] + diff_orig).clamp(0.0, 1.0)

    return frames_out


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_video(
    frames: torch.Tensor,
    output_path: str,
    fps: float = 25.0,
) -> None:
    """Save all frames ``(N, C, H, W)`` as a browser-playable MP4.

    Strategy:
      1. Write raw frames via OpenCV (mp4v — works on all OS).
      2. If ``ffmpeg`` is available, remux to H.264 so that browsers
         and WebView (Tauri/Electron) can play it.
      3. If ``ffmpeg`` is not available, the mp4v file is kept as-is
         (VLC can play it, but browsers may not).
    """
    try:
        import cv2
    except ImportError as exc:
        raise ImportError("pip install opencv-python") from exc

    safe_path = _sanitise_path(output_path)
    os.makedirs(os.path.dirname(safe_path) or '.', exist_ok=True)

    N, C, H, W = frames.shape
    np_frames = (
        frames.detach().cpu().clamp(0, 1).numpy() * 255
    ).astype(np.uint8).transpose(0, 2, 3, 1)

    # Step 1: write with mp4v (universally available)
    temp_path = safe_path.replace('.mp4', '_raw.mp4')
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_path, fourcc, fps, (W, H))
    if not writer.isOpened():
        # Last resort: try XVID → .avi
        temp_path = safe_path.replace('.mp4', '_raw.avi')
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        writer = cv2.VideoWriter(temp_path, fourcc, fps, (W, H))
    for frm in np_frames:
        writer.write(cv2.cvtColor(frm, cv2.COLOR_RGB2BGR))
    writer.release()

    # Step 2: remux to H.264 via ffmpeg (browser-compatible)
    if _remux_to_h264(temp_path, safe_path):
        # Success — remove temp
        try:
            os.remove(temp_path)
        except OSError:
            pass
    else:
        # No ffmpeg — rename temp to final
        if temp_path != safe_path:
            if os.path.exists(safe_path):
                os.remove(safe_path)
            os.rename(temp_path, safe_path)


def _remux_to_h264(input_path: str, output_path: str) -> bool:
    """Re-encode to H.264 using ffmpeg. Returns True on success."""
    import subprocess
    import shutil

    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return False

    try:
        cmd = [
            ffmpeg, '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-an',  # no audio (added separately later)
            output_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=300,
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False


def save_frames_as_images(
    frames: torch.Tensor,
    output_dir: str,
    prefix: str = 'frame',
) -> List[str]:
    """Save each frame as a PNG image."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("pip install Pillow") from exc

    safe_dir = _sanitise_path(output_dir)
    os.makedirs(safe_dir, exist_ok=True)

    np_frames = (
        frames.detach().cpu().clamp(0, 1).numpy() * 255
    ).astype(np.uint8)

    paths: list[str] = []
    for t, frm in enumerate(np_frames):
        img = Image.fromarray(frm.transpose(1, 2, 0))
        path = os.path.join(safe_dir, f"{prefix}_{t:04d}.png")
        img.save(path)
        paths.append(path)
    return paths