"""
Structural Similarity Index Measure (SSIM) implementation.
Differentiable SSIM for use in adversarial optimization.
Based on: Wang et al., "Image quality assessment: from error visibility to structural similarity"
IEEE TIP, 2004. Appendix A of DeepSAVA paper.
"""

import torch
import torch.nn.functional as F
import torch.nn as nn


def gaussian_kernel(kernel_size: int = 11, sigma: float = 1.5) -> torch.Tensor:
    """Create 2D Gaussian kernel."""
    coords = torch.arange(kernel_size, dtype=torch.float32)
    coords -= kernel_size // 2
    g = torch.exp(-(coords ** 2) / (2 * sigma ** 2))
    g /= g.sum()
    kernel = g.unsqueeze(0) * g.unsqueeze(1)
    return kernel


def ssim_single_frame(x: torch.Tensor, y: torch.Tensor,
                       kernel_size: int = 11,
                       sigma: float = 1.5,
                       C1: float = 0.01 ** 2,
                       C2: float = 0.03 ** 2) -> torch.Tensor:
    """
    Compute SSIM between two single frames.
    Args:
        x, y: tensors of shape (B, C, H, W) in range [0, 1]
    Returns:
        ssim_val: scalar tensor, mean SSIM over batch and channels
    """
    assert x.shape == y.shape, f"Shape mismatch: {x.shape} vs {y.shape}"

    B, C, H, W = x.shape

    # Build Gaussian kernel
    kernel = gaussian_kernel(kernel_size, sigma).to(x.device)
    kernel = kernel.unsqueeze(0).unsqueeze(0)  # (1,1,kH,kW)
    kernel = kernel.expand(C, 1, kernel_size, kernel_size)

    padding = kernel_size // 2

    # Compute means
    mu_x = F.conv2d(x, kernel, padding=padding, groups=C)
    mu_y = F.conv2d(y, kernel, padding=padding, groups=C)

    mu_x_sq = mu_x * mu_x
    mu_y_sq = mu_y * mu_y
    mu_xy  = mu_x * mu_y

    # Compute variances
    sigma_x_sq = F.conv2d(x * x, kernel, padding=padding, groups=C) - mu_x_sq
    sigma_y_sq = F.conv2d(y * y, kernel, padding=padding, groups=C) - mu_y_sq
    sigma_xy   = F.conv2d(x * y, kernel, padding=padding, groups=C) - mu_xy

    # SSIM formula
    numerator   = (2 * mu_xy + C1) * (2 * sigma_xy + C2)
    denominator = (mu_x_sq + mu_y_sq + C1) * (sigma_x_sq + sigma_y_sq + C2)

    ssim_map = numerator / (denominator + 1e-8)
    return ssim_map.mean()


def ssim_video(x: torch.Tensor, y: torch.Tensor,
               kernel_size: int = 11,
               sigma: float = 1.5) -> torch.Tensor:
    """
    Compute mean SSIM over all frames of a video.
    Args:
        x, y: tensors of shape (T, C, H, W) or (B, T, C, H, W), in range [0,1]
    Returns:
        mean SSIM scalar
    """
    if x.dim() == 4:
        # (T, C, H, W)
        T = x.shape[0]
        scores = []
        for t in range(T):
            scores.append(ssim_single_frame(
                x[t:t+1], y[t:t+1], kernel_size, sigma
            ))
        return torch.stack(scores).mean()
    elif x.dim() == 5:
        # (B, T, C, H, W) — treat each (b,t) pair
        B, T, C, H, W = x.shape
        scores = []
        for b in range(B):
            for t in range(T):
                scores.append(ssim_single_frame(
                    x[b, t:t+1], y[b, t:t+1], kernel_size, sigma
                ))
        return torch.stack(scores).mean()
    else:
        raise ValueError(f"Expected 4D or 5D tensor, got {x.dim()}D")


def ssim_loss(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """
    SSIM-based similarity loss: 1 - SSIM(x, y).
    Minimizing this encourages x to be similar to y.
    """
    return 1.0 - ssim_video(x, y)


class SSIMLoss(nn.Module):
    """Differentiable SSIM loss module."""

    def __init__(self, kernel_size: int = 11, sigma: float = 1.5):
        super().__init__()
        self.kernel_size = kernel_size
        self.sigma = sigma

    def forward(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        return ssim_loss(x, y)
