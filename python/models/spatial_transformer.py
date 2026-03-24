"""
Spatial Transformer Network (STN) for DeepSAVA.
Implements differentiable spatial transformation via flow displacement vectors U.
Based on: Jaderberg et al., "Spatial Transformer Networks", NeurIPS 2015.
Used in DeepSAVA for spatial-transformed perturbation (Section 3.1).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class SpatialTransformer(nn.Module):
    """
    Applies a spatial transformation (optical-flow-like displacement) to frames.

    Given flow displacement vectors U = (ΔH, ΔV) for each pixel, the new pixel
    location is:  (h_new, v_new) = (h_orig + Δh, v_orig + Δv)

    This is equivalent to the inverse warp: for each output pixel (h,v),
    sample from input at (h + Δh, v + Δv).
    """

    def __init__(self):
        super().__init__()

    def forward(self, x: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x:    (T, C, H, W) — video frames, values in [0,1]
            flow: (T, 2, H, W) — displacement vectors (ΔH, ΔV) per pixel
                  flow[:,0,...] = vertical displacement
                  flow[:,1,...] = horizontal displacement
                  Values are in pixel units (will be normalised internally).
        Returns:
            warped: (T, C, H, W) — spatially transformed frames
        """
        T, C, H, W = x.shape
        assert flow.shape == (T, 2, H, W), \
            f"flow shape {flow.shape} != expected ({T},2,{H},{W})"

        # Build normalised sampling grid
        # grid_sample expects grid in range [-1,1]
        # Base identity grid: shape (T, H, W, 2)
        base_grid = self._make_base_grid(T, H, W, x.device)  # (T,H,W,2): [x,y] coords

        # flow is in pixel units; normalise to [-1,1]
        flow_norm = flow.clone()
        flow_norm[:, 0] = flow[:, 0] / ((H - 1) / 2.0)  # vertical   -> y
        flow_norm[:, 1] = flow[:, 1] / ((W - 1) / 2.0)  # horizontal -> x

        # flow_norm: (T,2,H,W) -> (T,H,W,2) with order [x, y]
        flow_perm = flow_norm.permute(0, 2, 3, 1)          # (T,H,W,2)
        flow_perm = flow_perm[..., [1, 0]]                  # swap to [x(horizontal), y(vertical)]

        # Displaced grid
        grid = base_grid + flow_perm                        # (T,H,W,2)
        grid = torch.clamp(grid, -1.0, 1.0)

        # Sample
        warped = F.grid_sample(x, grid,
                               mode='bilinear',
                               padding_mode='border',
                               align_corners=True)
        return warped

    @staticmethod
    def _make_base_grid(T: int, H: int, W: int,
                        device: torch.device) -> torch.Tensor:
        """
        Identity sampling grid: (T, H, W, 2) with values in [-1,1].
        grid[t,h,w] = [x_w, y_h] where x_w in [-1,1], y_h in [-1,1].
        """
        x_lin = torch.linspace(-1, 1, W, device=device)
        y_lin = torch.linspace(-1, 1, H, device=device)
        y_grid, x_grid = torch.meshgrid(y_lin, x_lin, indexing='ij')  # (H,W)
        grid = torch.stack([x_grid, y_grid], dim=-1)                   # (H,W,2)
        grid = grid.unsqueeze(0).expand(T, -1, -1, -1)                 # (T,H,W,2)
        return grid
