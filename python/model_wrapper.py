"""
model_wrapper.py — SlowFast R101 wrapper for VidScratch.

Adapts SlowFast R101 (77.90 % top-1 on Kinetics-400) to accept the
same ``(B, C, T, H, W)`` normalised-to-``[-1, 1]`` input format that
the original I3D Inception pipeline used, so the rest of the codebase
needs no changes.

Internally the wrapper:
    1. Converts ``[-1, 1]`` → PyTorchVideo normalisation.
    2. Sub-samples *T* frames → 32 (SlowFast requirement).
    3. Resizes 224 → 256 (SlowFast crop size).
    4. Splits into Slow / Fast pathways automatically.
    5. Returns logits ``(B, 400)``.
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# PyTorchVideo normalisation constants
_PTV_MEAN = [0.45, 0.45, 0.45]
_PTV_STD = [0.225, 0.225, 0.225]

# SlowFast R101 architecture parameters
_SLOWFAST_CFG = {
    'hub_name': 'slowfast_r101',
    'num_frames': 32,
    'crop_size': 256,
    'slowfast_alpha': 4,  # slow pathway uses 32 / 4 = 8 frames
    'top1': 77.90,
    'top5': 93.27,
}


class SlowFastWrapper(nn.Module):
    """Wrap SlowFast R101 to accept the I3D-style input format.

    Input:  ``(B, C, T, H, W)`` in ``[-1, 1]``
    Output: ``(B, 400)`` logits
    """

    def __init__(
        self,
        model: nn.Module,
        num_frames: int = 32,
        crop_size: int = 256,
        slowfast_alpha: int = 4,
    ):
        super().__init__()
        self.model = model
        self.num_frames = num_frames
        self.crop_size = crop_size
        self.slowfast_alpha = slowfast_alpha

        self.register_buffer(
            '_mean', torch.tensor(_PTV_MEAN).view(1, 3, 1, 1, 1),
        )
        self.register_buffer(
            '_std', torch.tensor(_PTV_STD).view(1, 3, 1, 1, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, T, H, W = x.shape

        # [-1, 1] → [0, 1] → PTV normalisation
        x_01 = (x + 1.0) / 2.0
        x_norm = (x_01 - self._mean) / self._std

        # Temporal sub-sample → 32 frames
        if T != self.num_frames:
            idx = torch.linspace(0, T - 1, self.num_frames).long().to(x.device)
            x_norm = x_norm[:, :, idx, :, :]

        # Spatial resize → 256 × 256
        if H != self.crop_size or W != self.crop_size:
            T2 = x_norm.shape[2]
            x_flat = x_norm.permute(0, 2, 1, 3, 4).reshape(B * T2, C, H, W)
            x_flat = F.interpolate(
                x_flat,
                size=(self.crop_size, self.crop_size),
                mode='bilinear',
                align_corners=False,
            )
            x_norm = (
                x_flat
                .reshape(B, T2, C, self.crop_size, self.crop_size)
                .permute(0, 2, 1, 3, 4)
            )

        # Dual pathway split
        fast = x_norm
        slow_idx = torch.linspace(
            0, x_norm.shape[2] - 1,
            x_norm.shape[2] // self.slowfast_alpha,
        ).long().to(x.device)
        slow = x_norm[:, :, slow_idx, :, :]

        logits = self.model([slow, fast])

        if logits.dim() == 3:
            logits = logits.mean(dim=-1)

        return logits


def load_slowfast_r101(device: str = 'cpu') -> nn.Module:
    """Load pretrained SlowFast R101 wrapped for VidScratch.

    The model is downloaded from ``facebookresearch/pytorchvideo``
    via :func:`torch.hub.load` on first call and cached afterwards.

    Args:
        device: target device (``'cpu'`` or ``'cuda'``).

    Returns:
        A :class:`SlowFastWrapper` instance in eval mode.

    Raises:
        RuntimeError: if ``pytorchvideo`` is not installed.
    """
    cfg = _SLOWFAST_CFG
    logger.info(f"Loading SlowFast R101 (top-1: {cfg['top1']} %) …")

    try:
        model = torch.hub.load(
            'facebookresearch/pytorchvideo',
            cfg['hub_name'],
            pretrained=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "Cannot load SlowFast R101.  "
            "Install pytorchvideo:  pip install pytorchvideo\n"
            f"Original error: {exc}"
        ) from exc

    model = model.to(device).eval()
    wrapper = SlowFastWrapper(
        model,
        num_frames=cfg['num_frames'],
        crop_size=cfg['crop_size'],
        slowfast_alpha=cfg['slowfast_alpha'],
    ).to(device).eval()

    logger.info(
        f"SlowFast R101 ready — top-1: {cfg['top1']} %, top-5: {cfg['top5']} %"
    )
    return wrapper


if __name__ == '__main__':
    _device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Loading SlowFast R101 on {_device} …")

    _model = load_slowfast_r101(_device)
    _dummy = torch.randn(1, 3, 40, 224, 224, device=_device).clamp(-1, 1)
    with torch.no_grad():
        _logits = _model(_dummy)

    print(f"Input:  {_dummy.shape}  (B, C, T=40, H=224, W=224)")
    print(f"Output: {_logits.shape}  (B, 400)")
    print(f"Top-5:  {_logits[0].topk(5).indices.tolist()}")
    print("✓ Works!")
