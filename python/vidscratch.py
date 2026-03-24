"""
vidscratch.py — VidScratch: Sparse Adversarial Video Attack engine.

Merges the former ``deepsava.py`` (BO frame selection + adversarial
generation) and ``shortcut_noise.py`` (error-minimising base layer)
into a single module.

Attack modes:

* **Standard** — Bayesian-optimised frame selection (Algorithm 1) followed
  by Adam-based spatial-transform + noise optimisation (Algorithm 2).
* **Layered** — Standard attack on clean frames, then error-minimising
  noise on the remaining (non-attacked) frames for training-time
  poisoning resistance.
* **Legacy shortcuts** — ``error_min``, ``adversarial``, and ``hybrid``
  modes kept for backward compatibility.

References:
    Mu et al., "Sparse Adversarial Video Attacks with Spatial
    Transformations", BMVC 2021.  arXiv:2111.05468
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from models.ssim import SSIMLoss
from models.spatial_transformer import SpatialTransformer

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Configuration
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class AttackConfig:
    """Core attack hyper-parameters (formerly ``DeepSAVAConfig``)."""

    lam: float = 1.0
    """Weight balancing SSIM loss vs adversarial loss."""
    lr: float = 0.01
    """Adam learning rate."""
    max_iterations: int = 100
    """Adam steps per attack round."""
    num_perturbed_frames: int = 0
    """Frames to poison. 0 = auto (1 per 40 total frames)."""
    bo_max_iterations: int = 50
    """Bayesian optimisation exploration budget."""
    bo_init_samples: int = 5
    """Random warm-up samples for BO."""
    ssim_budget: float = 0.04
    """Maximum allowed SSIM degradation (1 − SSIM)."""
    noise_clamp: float = 0.03
    """Hard per-pixel noise cap (±)."""
    verbose: bool = True
    device: str = (
        'cuda' if torch.cuda.is_available()
        else 'mps' if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        else 'cpu'
    )

@dataclass
class ShortcutConfig:
    """Configuration for error-minimising / shortcut noise layers.

    Only used when the ``--shortcut`` flag is active.
    """

    mode: str = 'layered'
    """One of ``error_min``, ``adversarial``, ``hybrid``, ``layered``."""

    # Error-minimising noise (base layer)
    em_epsilon: float = 0.002
    em_steps: int = 50
    em_step_size: float = 0.002
    em_momentum: float = 0.9
    em_all_frames: bool = True

    # Adversarial booster (v1 compat)
    adv_epsilon: float = 0.03
    adv_steps: int = 30
    adv_step_size: float = 0.005

    # Hybrid blend (v1 compat)
    blend_ratio: float = 0.6

    # Feature-space targeting
    feature_layer: str = 'auto'
    feature_weight: float = 0.3

    device: str = (
        'cuda' if torch.cuda.is_available()
        else 'mps' if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        else 'cpu'
    )
    verbose: bool = True


# Backward-compatible aliases
DeepSAVAConfig = AttackConfig
ShortcutNoiseConfig = ShortcutConfig


# ═════════════════════════════════════════════════════════════════════════════
# Gaussian Process (for Bayesian Optimisation)
# ═════════════════════════════════════════════════════════════════════════════

class _GaussianProcess:
    """Minimal GP with RBF kernel for the BO frame selector."""

    def __init__(self, noise: float = 1e-4, length_scale: float = 1.0):
        self.noise = noise
        self.length_scale = length_scale
        self._X: Optional[np.ndarray] = None
        self._y: Optional[np.ndarray] = None
        self._K_inv: Optional[np.ndarray] = None

    def _rbf(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        diff = X1[:, None, :] - X2[None, :, :]
        return np.exp(-(diff ** 2).sum(-1) / (2 * self.length_scale ** 2))

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self._X, self._y = X.copy(), y.copy()
        K = self._rbf(X, X) + self.noise * np.eye(len(X))
        self._K_inv = np.linalg.inv(K)

    def predict(self, X_star: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self._X is None:
            return np.zeros(len(X_star)), np.ones(len(X_star))
        K_s = self._rbf(X_star, self._X)
        K_ss = self._rbf(X_star, X_star)
        mu = K_s @ self._K_inv @ self._y
        var = np.maximum(np.diag(K_ss - K_s @ self._K_inv @ K_s.T), 1e-8)
        return mu, var

    def expected_improvement(
        self, X_star: np.ndarray, best_y: float, xi: float = 0.01,
    ) -> np.ndarray:
        from scipy.stats import norm

        mu, var = self.predict(X_star)
        sigma = np.sqrt(var)
        z = (mu - best_y - xi) / (sigma + 1e-9)
        ei = (mu - best_y - xi) * norm.cdf(z) + sigma * norm.pdf(z)
        return np.maximum(ei, 0.0)


# ═════════════════════════════════════════════════════════════════════════════
# Bayesian Frame Selector (Algorithm 1)
# ═════════════════════════════════════════════════════════════════════════════

class _BayesianFrameSelector:
    """Select the *k* most vulnerable frames via Bayesian optimisation."""

    def __init__(
        self,
        config: AttackConfig,
        model: nn.Module,
        ssim_fn: SSIMLoss,
        spatial_transformer: SpatialTransformer,
    ):
        self.cfg = config
        self.model = model
        self.ssim = ssim_fn
        self.st = spatial_transformer
        self.device = torch.device(config.device)
        self._gp = _GaussianProcess()

    # ── inner evaluation ─────────────────────────────────────────────────

    def _evaluate_mask(
        self, mask: np.ndarray, X: torch.Tensor, y: int,
    ) -> float:
        M = torch.tensor(mask, dtype=torch.float32, device=self.device)
        T, C, H, W = X.shape
        U = torch.zeros(T, 2, H, W, device=self.device, requires_grad=True)
        N = torch.zeros(T, C, H, W, device=self.device, requires_grad=True)
        opt = optim.Adam([U, N], lr=self.cfg.lr)

        inner_steps = max(10, self.cfg.max_iterations // 10)
        self.model.eval()
        for _ in range(inner_steps):
            opt.zero_grad()
            loss = self._loss(X, M, U, N, y)
            (-loss).backward()
            opt.step()
            with torch.no_grad():
                N.clamp_(-self.cfg.noise_clamp, self.cfg.noise_clamp)

        with torch.no_grad():
            return self._loss(X, M, U, N, y).item()

    def _loss(
        self,
        X: torch.Tensor,
        M: torch.Tensor,
        U: torch.Tensor,
        N: torch.Tensor,
        y: int,
    ) -> torch.Tensor:
        X_hat = self._apply_transform(X, M, U, N)
        masked_idx = (M > 0.5).nonzero(as_tuple=True)[0]
        if len(masked_idx) > 0:
            Ls = self.ssim(X_hat[masked_idx], X[masked_idx])
        else:
            Ls = self.ssim(X_hat, X)
        La = self._adv_loss(X_hat, y)
        return self.cfg.lam * Ls - La

    def _apply_transform(
        self,
        X: torch.Tensor,
        M: torch.Tensor,
        U: torch.Tensor,
        N: torch.Tensor,
    ) -> torch.Tensor:
        X_s = self.st(X, U)
        M_exp = M.view(-1, 1, 1, 1)
        return (M_exp * X_s + (1 - M_exp) * X + M_exp * N).clamp(0.0, 1.0)

    def _adv_loss(self, X_hat: torch.Tensor, y: int) -> torch.Tensor:
        inp = (X_hat * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
        logit = self.model(inp)
        if logit.dim() == 3:
            logit = logit.mean(dim=-1)
        return nn.CrossEntropyLoss()(
            logit, torch.tensor([y], device=self.device),
        )

    # ── candidate mask generation ────────────────────────────────────────

    def _candidate_masks(
        self, T: int, k: int, max_cand: int = 400,
    ) -> np.ndarray:
        """Build candidate binary masks using stratified sampling.

        For ``k = 1`` each frame gets its own mask.  For ``k > 1`` the
        video is split into *k* equal segments and one frame is drawn
        from each segment to ensure spatial diversity.
        """
        rng = np.random.default_rng(42)

        if k == 1:
            indices = np.arange(T)
            n_sample = min(T, max_cand)
            chosen = rng.choice(indices, n_sample, replace=False)
            masks = np.zeros((n_sample, T), dtype=float)
            for i, idx in enumerate(chosen):
                masks[i, idx] = 1.0
            return masks

        n_cand = min(max_cand, 200)
        masks = np.zeros((n_cand, T), dtype=float)
        boundaries = np.linspace(0, T, k + 1, dtype=int)
        segments = [
            list(range(boundaries[s], boundaries[s + 1]))
            for s in range(k)
        ]
        for i in range(n_cand):
            for seg in segments:
                if seg:
                    masks[i, int(rng.choice(seg))] = 1.0

        masks = np.unique(masks, axis=0)
        order = rng.permutation(len(masks))
        return masks[order[:max_cand]]

    # ── Algorithm 1 ──────────────────────────────────────────────────────

    def select(
        self, X: torch.Tensor, y: int, k: Optional[int] = None,
    ) -> np.ndarray:
        """Run BO to find the best *k* frames to poison.

        Args:
            X: model-window frames ``(T, C, H, W)`` in ``[0, 1]``.
            y: ground-truth label.
            k: number of frames to poison (``None`` → use config).

        Returns:
            Binary mask ``(T,)`` with *k* entries set to 1.
        """
        T = X.shape[0]
        k = k or max(1, self.cfg.num_perturbed_frames)
        cfg = self.cfg

        all_masks = self._candidate_masks(T, k)
        n = len(all_masks)
        logger.info(
            f"  BO: {n} candidate masks (T={T}, k={k})"
        )

        D_X: list[np.ndarray] = []
        D_y: list[float] = []
        best_loss = -np.inf
        best_mask = all_masks[0]

        # Phase 1: random init
        rng = np.random.default_rng(0)
        init_idx = rng.choice(n, min(cfg.bo_init_samples, n), replace=False)
        for idx in init_idx:
            mask = all_masks[idx]
            loss = self._evaluate_mask(mask, X, y)
            D_X.append(mask)
            D_y.append(loss)
            if loss > best_loss:
                best_loss, best_mask = loss, mask.copy()

        # Phase 2: GP-guided
        gp = self._gp
        for it in range(cfg.bo_max_iterations):
            gp.fit(np.array(D_X), np.array(D_y))
            evaluated = {tuple(m.tolist()) for m in D_X}
            cands = [m for m in all_masks if tuple(m.tolist()) not in evaluated]
            if not cands:
                break
            ei = gp.expected_improvement(np.array(cands), best_loss)
            next_mask = cands[int(np.argmax(ei))]
            loss = self._evaluate_mask(next_mask, X, y)
            D_X.append(next_mask)
            D_y.append(loss)
            if loss > best_loss:
                best_loss, best_mask = loss, next_mask.copy()
            logger.debug(
                f"  BO {it + 1}: frames={np.where(next_mask)[0].tolist()} "
                f"loss={loss:.4f}  best={best_loss:.4f}"
            )

        logger.info(
            f"  BO done → frames {np.where(best_mask)[0].tolist()} "
            f"(loss={best_loss:.4f})"
        )
        return best_mask


# ═════════════════════════════════════════════════════════════════════════════
# Adversarial Generator (Algorithm 2)
# ═════════════════════════════════════════════════════════════════════════════

class _AdversarialGenerator:
    """Optimise spatial flow *U* and additive noise *N* for a fixed mask."""

    def __init__(
        self,
        config: AttackConfig,
        model: nn.Module,
        ssim_fn: SSIMLoss,
        spatial_transformer: SpatialTransformer,
    ):
        self.cfg = config
        self.model = model
        self.ssim = ssim_fn
        self.st = spatial_transformer
        self.device = torch.device(config.device)

    def generate(
        self, X: torch.Tensor, M: np.ndarray, y: int,
    ) -> Tuple[torch.Tensor, dict]:
        """Run Algorithm 2.

        Args:
            X: ``(T, C, H, W)`` model-window frames in ``[0, 1]``.
            M: ``(T,)`` binary mask.
            y: ground-truth label.

        Returns:
            ``(X_hat, metrics)`` — adversarial frames and diagnostics.
        """
        cfg = self.cfg
        T, C, H, W = X.shape
        device = self.device

        M_t = torch.tensor(M, dtype=torch.float32, device=device)
        masked_idx = (M_t > 0.5).nonzero(as_tuple=True)[0]

        U = torch.zeros(T, 2, H, W, device=device, requires_grad=True)
        N = torch.zeros(T, C, H, W, device=device, requires_grad=True)
        optimizer = optim.Adam([U, N], lr=cfg.lr)
        self.model.eval()

        loss_history: list[float] = []
        X_hat_best = X.clone()
        best_loss = float('inf')

        for step in range(cfg.max_iterations):
            optimizer.zero_grad()

            X_s = self.st(X, U)
            M_exp = M_t.view(-1, 1, 1, 1)
            X_hat = (M_exp * X_s + (1 - M_exp) * X + M_exp * N).clamp(0.0, 1.0)

            # SSIM on masked frames only
            if len(masked_idx) > 0:
                Ls = self.ssim(X_hat[masked_idx], X[masked_idx])
            else:
                Ls = self.ssim(X_hat, X)

            inp = (X_hat * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
            logit = self.model(inp)
            if logit.dim() == 3:
                logit = logit.mean(dim=-1)
            La = nn.CrossEntropyLoss()(
                logit, torch.tensor([y], device=device),
            )

            loss = cfg.lam * Ls - La
            loss.backward()
            optimizer.step()

            with torch.no_grad():
                N.clamp_(-cfg.noise_clamp, cfg.noise_clamp)

            loss_val = loss.item()
            loss_history.append(loss_val)

            if loss_val < best_loss:
                best_loss = loss_val
                with torch.no_grad():
                    X_s_b = self.st(X, U)
                    M_exp2 = M_t.view(-1, 1, 1, 1)
                    X_hat_best = (
                        M_exp2 * X_s_b + (1 - M_exp2) * X + M_exp2 * N
                    ).clamp(0.0, 1.0).detach().clone()

            # Early stopping on SSIM budget
            with torch.no_grad():
                if len(masked_idx) > 0:
                    ssim_val = 1.0 - self.ssim(
                        X_hat_best[masked_idx], X[masked_idx],
                    ).item()
                else:
                    ssim_val = 1.0 - self.ssim(X_hat_best, X).item()

            if ssim_val < (1.0 - cfg.ssim_budget):
                logger.debug(f"  step {step + 1}: SSIM={ssim_val:.4f} → early stop")
                break

            if cfg.verbose and (step + 1) % 20 == 0:
                logger.debug(
                    f"  step {step + 1}/{cfg.max_iterations}: "
                    f"loss={loss_val:.4f}  SSIM={ssim_val:.4f}"
                )

        # Final evaluation
        with torch.no_grad():
            if len(masked_idx) > 0:
                ssim_final = 1.0 - self.ssim(
                    X_hat_best[masked_idx], X[masked_idx],
                ).item()
            else:
                ssim_final = 1.0 - self.ssim(X_hat_best, X).item()
            inp_f = (X_hat_best * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
            logit_f = self.model(inp_f)
            if logit_f.dim() == 3:
                logit_f = logit_f.mean(dim=-1)
            pred = logit_f.argmax(dim=1).item()

        return X_hat_best, {
            'loss_history': loss_history,
            'ssim_final': ssim_final,
            'success': pred != y,
            'pred_label': pred,
            'true_label': y,
        }


# ═════════════════════════════════════════════════════════════════════════════
# VidScratch — main attack class (formerly DeepSAVA)
# ═════════════════════════════════════════════════════════════════════════════

class VidScratch:
    """Full attack pipeline.

    1. Compute *k* = ``max(1, round(total_frames / 40))`` (poison ratio ≈ 1:40).
    2. BO selects the best *k* frames from the 40-frame model window.
    3. Adam optimises spatial flow + additive noise on those frames.
    4. Returns the adversarial model window for the caller to map back.
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[AttackConfig] = None,
    ):
        self.cfg = config or AttackConfig()
        self.device = torch.device(self.cfg.device)
        self.model = model.to(self.device).eval()
        self.ssim = SSIMLoss()
        self.st = SpatialTransformer()
        self.bo = _BayesianFrameSelector(
            self.cfg, self.model, self.ssim, self.st,
        )
        self.gen = _AdversarialGenerator(
            self.cfg, self.model, self.ssim, self.st,
        )

    def _default_mask(self, T: int, k: int) -> np.ndarray:
        mask = np.zeros(T, dtype=float)
        mask[:k] = 1.0
        return mask

    def attack(
        self,
        X: torch.Tensor,
        y: int,
        total_frames: int = 40,
        use_bo: bool = True,
        forced_mask: Optional[np.ndarray] = None,
    ) -> Tuple[torch.Tensor, dict]:
        """Run the full VidScratch attack.

        Args:
            X: ``(T, C, H, W)`` model-window frames in ``[0, 1]``.
            y: ground-truth label.
            total_frames: total frames in the source video (for computing *k*).
            use_bo: whether to use Bayesian optimisation for frame selection.
            forced_mask: skip BO/default and use this mask directly.

        Returns:
            ``(X_hat, results)`` — adversarial model window and metrics dict.
        """
        X = X.to(self.device)
        t0 = time.time()

        # Compute k
        if self.cfg.num_perturbed_frames > 0:
            k = self.cfg.num_perturbed_frames
        else:
            k = max(1, round(total_frames / 40))

        logger.info(
            f"total_frames={total_frames} → k={k} "
            f"(ratio 1:{total_frames // k if k else '?'})"
        )

        # Check original prediction
        with torch.no_grad():
            inp = (X * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
            logit = self.model(inp)
            if logit.dim() == 3:
                logit = logit.mean(dim=-1)
            orig_pred = logit.argmax(dim=1).item()

        if orig_pred != y:
            logger.warning(
                f"orig_pred={orig_pred} != label={y} — "
                f"auto-label should match"
            )

        # Algorithm 1: frame selection
        if forced_mask is not None:
            mask, bo_t = forced_mask, 0.0
            logger.info(f"Using forced mask → frames {np.where(mask)[0].tolist()}")
        elif use_bo:
            logger.info(f"Running BO (k={k}, iters={self.cfg.bo_max_iterations})")
            t_bo = time.time()
            mask = self.bo.select(X, y, k=k)
            bo_t = time.time() - t_bo
        else:
            mask, bo_t = self._default_mask(X.shape[0], k), 0.0
            logger.info(f"Skipping BO → frames {np.where(mask)[0].tolist()}")

        # Algorithm 2: adversarial generation
        logger.info(
            f"Running generator (max_iter={self.cfg.max_iterations}, lr={self.cfg.lr})"
        )
        X_hat, metrics = self.gen.generate(X, mask, y)

        total_t = time.time() - t0
        metrics.update({
            'mask': mask,
            'key_frames': np.where(mask)[0].tolist(),
            'k': k,
            'total_frames': total_frames,
            'orig_pred': orig_pred,
            'total_time_s': total_t,
            'bo_time_s': bo_t,
            'use_bo': use_bo,
        })

        status = "✓ SUCCESS" if metrics['success'] else "✗ FAILED"
        logger.info(
            f"{status}  pred={metrics['pred_label']} (true={y})  "
            f"SSIM={metrics['ssim_final']:.4f}  "
            f"frames={metrics['key_frames']}  time={total_t:.1f}s"
        )
        return X_hat, metrics


# Backward-compatible alias
DeepSAVA = VidScratch


# ═════════════════════════════════════════════════════════════════════════════
# Feature hook helper
# ═════════════════════════════════════════════════════════════════════════════

def _auto_detect_feature_layer(model: nn.Module) -> str:
    """Find the last suitable feature layer before the classification head."""
    named = dict(model.named_modules())
    candidates = [
        'model.blocks.5', 'blocks.5', 'model.blocks.4', 'blocks.4',
        'Mixed_5c', 'Mixed_5b', 'layer4',
    ]
    for name in candidates:
        if name in named:
            return name

    last_block = None
    for name in named:
        if ('block' in name.lower() or 'layer' in name.lower()) \
                and 'head' not in name.lower() and 'cls' not in name.lower():
            last_block = name
    return last_block or ''


class _FeatureHook:
    """Captures intermediate features from a named layer."""

    def __init__(self, model: nn.Module, layer_name: str):
        self.features: Optional[torch.Tensor] = None
        self._hook = None

        if layer_name == 'auto':
            layer_name = _auto_detect_feature_layer(model)
            if layer_name:
                logger.info(f"  Auto-detected feature layer: '{layer_name}'")
            else:
                logger.warning("  No feature layer found — targeting disabled")
                return

        for name, module in model.named_modules():
            if name == layer_name:
                self._hook = module.register_forward_hook(self._on_forward)
                return
        logger.warning(f"  Layer '{layer_name}' not found — targeting disabled")

    def _on_forward(self, module, inp, out):
        self.features = out

    def remove(self):
        if self._hook is not None:
            self._hook.remove()


# ═════════════════════════════════════════════════════════════════════════════
# Error-Minimising Noise Generator (base layer)
# ═════════════════════════════════════════════════════════════════════════════

class _ErrorMinNoise:
    """Generate noise that *minimises* classification loss.

    Used as the "base layer" in the layered pipeline: every non-attacked
    frame gets a barely-visible texture that reduces the model's training
    signal for the correct class.
    """

    def __init__(self, model: nn.Module, config: ShortcutConfig):
        self.model = model
        self.cfg = config
        self.device = torch.device(config.device)
        self._feature_hook: Optional[_FeatureHook] = None

    @staticmethod
    def _to_model_input(X: torch.Tensor) -> torch.Tensor:
        return (X * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)

    def _logits(self, X_input: torch.Tensor) -> torch.Tensor:
        logits = self.model(X_input)
        if logits.dim() == 3:
            logits = logits.mean(dim=-1)
        return logits

    def generate(
        self,
        X: torch.Tensor,
        y: int,
        mask: Optional[np.ndarray] = None,
    ) -> Tuple[torch.Tensor, Dict]:
        """Produce error-minimising delta.

        Args:
            X: ``(T, C, H, W)`` frames in ``[0, 1]``.
            y: ground-truth label.
            mask: per-frame binary mask (used when ``em_all_frames=False``).

        Returns:
            ``(delta, metrics)`` — additive noise tensor and diagnostics.
        """
        cfg = self.cfg
        T, C, H, W = X.shape
        X = X.to(self.device)
        target = torch.tensor([y], device=self.device)

        delta = torch.zeros(T, C, H, W, device=self.device, requires_grad=True)

        # Build per-frame mask
        if cfg.em_all_frames:
            frame_mask = torch.ones(T, 1, 1, 1, device=self.device)
        elif mask is not None:
            frame_mask = torch.tensor(
                mask, dtype=torch.float32, device=self.device,
            ).view(-1, 1, 1, 1)
        else:
            frame_mask = torch.ones(T, 1, 1, 1, device=self.device)

        # Optional feature-space anchor
        feat_anchor = None
        if cfg.feature_weight > 0:
            self._feature_hook = _FeatureHook(self.model, cfg.feature_layer)
            with torch.no_grad():
                self._logits(self._to_model_input(X))
                if self._feature_hook.features is not None:
                    feat_anchor = self._feature_hook.features.detach().clone()
                else:
                    cfg.feature_weight = 0

        self.model.eval()
        momentum = torch.zeros_like(delta)
        loss_history: list[float] = []
        best_delta = delta.detach().clone()
        best_loss = float('inf')

        for step in range(cfg.em_steps):
            delta.requires_grad_(True)

            X_noisy = (X + delta * frame_mask).clamp(0.0, 1.0)
            logits = self._logits(self._to_model_input(X_noisy))
            ce_loss = nn.CrossEntropyLoss()(logits, target)

            feat_loss = torch.tensor(0.0, device=self.device)
            if cfg.feature_weight > 0 and feat_anchor is not None:
                if self._feature_hook.features is not None:
                    feat_loss = F.mse_loss(
                        self._feature_hook.features, feat_anchor,
                    )

            total_loss = ce_loss + cfg.feature_weight * feat_loss
            total_loss.backward()

            with torch.no_grad():
                grad = delta.grad.clone()
                grad_norm = grad / (
                    grad.abs().mean(dim=[1, 2, 3], keepdim=True) + 1e-8
                )
                momentum = cfg.em_momentum * momentum + grad_norm

                # MINIMISE: subtract gradient
                delta.data -= cfg.em_step_size * momentum.sign()
                delta.data.clamp_(-cfg.em_epsilon, cfg.em_epsilon)
                delta.data *= frame_mask
                delta.data = torch.max(delta.data, -X)
                delta.data = torch.min(delta.data, 1.0 - X)

            delta.grad = None
            loss_val = total_loss.item()
            loss_history.append(loss_val)

            if loss_val < best_loss:
                best_loss = loss_val
                best_delta = delta.detach().clone()

            if cfg.verbose and (step + 1) % 20 == 0:
                logger.info(
                    f"  ErrorMin step {step + 1}/{cfg.em_steps}: "
                    f"CE={ce_loss.item():.4f}  total={loss_val:.4f}  "
                    f"δ_max={delta.abs().max().item():.4f}"
                )

        if self._feature_hook is not None:
            self._feature_hook.remove()
            self._feature_hook = None

        return best_delta.detach(), {
            'em_loss_history': loss_history,
            'em_best_loss': best_loss,
            'em_final_ce': loss_history[-1] if loss_history else best_loss,
            'em_delta_l2': best_delta.pow(2).mean().sqrt().item(),
            'em_delta_linf': best_delta.abs().max().item(),
            'em_steps': cfg.em_steps,
            'em_epsilon': cfg.em_epsilon,
            'em_all_frames': cfg.em_all_frames,
        }


# ═════════════════════════════════════════════════════════════════════════════
# Adversarial Booster (v1 compat — PGD on key frames)
# ═════════════════════════════════════════════════════════════════════════════

class _AdversarialBooster:
    """PGD adversarial perturbation on key frames only (v1 compat)."""

    def __init__(self, model: nn.Module, config: ShortcutConfig):
        self.model = model
        self.cfg = config
        self.device = torch.device(config.device)

    @staticmethod
    def _to_model_input(X: torch.Tensor) -> torch.Tensor:
        return (X * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)

    def _logits(self, X_input: torch.Tensor) -> torch.Tensor:
        logits = self.model(X_input)
        if logits.dim() == 3:
            logits = logits.mean(dim=-1)
        return logits

    def generate(
        self,
        X: torch.Tensor,
        y: int,
        mask: np.ndarray,
        init_delta: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict]:
        cfg = self.cfg
        T, C, H, W = X.shape
        X = X.to(self.device)
        target = torch.tensor([y], device=self.device)
        frame_mask = torch.tensor(
            mask, dtype=torch.float32, device=self.device,
        ).view(-1, 1, 1, 1)

        delta = (
            init_delta.clone().to(self.device)
            if init_delta is not None
            else torch.zeros(T, C, H, W, device=self.device)
        )
        delta.requires_grad_(True)

        self.model.eval()
        loss_history: list[float] = []
        best_delta = delta.detach().clone()
        best_loss = float('-inf')

        for _ in range(cfg.adv_steps):
            delta.requires_grad_(True)
            X_adv = (X + delta * frame_mask).clamp(0.0, 1.0)
            logits = self._logits(self._to_model_input(X_adv))
            ce_loss = nn.CrossEntropyLoss()(logits, target)
            ce_loss.backward()

            with torch.no_grad():
                delta.data += cfg.adv_step_size * delta.grad.sign()
                delta.data.clamp_(-cfg.adv_epsilon, cfg.adv_epsilon)
                delta.data *= frame_mask
                delta.data = torch.max(delta.data, -X)
                delta.data = torch.min(delta.data, 1.0 - X)
            delta.grad = None

            loss_val = ce_loss.item()
            loss_history.append(loss_val)
            if loss_val > best_loss:
                best_loss = loss_val
                best_delta = delta.detach().clone()

        return best_delta.detach(), {
            'adv_loss_history': loss_history,
            'adv_best_loss': best_loss,
            'adv_delta_l2': best_delta.pow(2).mean().sqrt().item(),
            'adv_delta_linf': best_delta.abs().max().item(),
        }


# ═════════════════════════════════════════════════════════════════════════════
# ShortcutNoise Generator (v1 modes: error_min / adversarial / hybrid)
# ═════════════════════════════════════════════════════════════════════════════

class _ShortcutNoiseGenerator:
    """Combine error-min and adversarial deltas (v1 modes)."""

    def __init__(self, model: nn.Module, config: ShortcutConfig):
        self.model = model
        self.cfg = config
        self.device = torch.device(config.device)
        self._em = _ErrorMinNoise(model, config)
        self._adv = _AdversarialBooster(model, config)

    def generate(
        self, X: torch.Tensor, y: int, mask: np.ndarray,
    ) -> Tuple[torch.Tensor, Dict]:
        cfg = self.cfg
        X = X.to(self.device)
        t0 = time.time()
        metrics: Dict = {'mode': cfg.mode}

        if cfg.mode == 'error_min':
            delta, em_m = self._em.generate(X, y, mask)
            metrics.update(em_m)

        elif cfg.mode == 'adversarial':
            delta, adv_m = self._adv.generate(X, y, mask)
            metrics.update(adv_m)

        elif cfg.mode == 'layered':
            delta, em_m = self._em.generate(X, y, mask=None)
            metrics.update(em_m)

        elif cfg.mode == 'hybrid':
            delta_em, em_m = self._em.generate(X, y, mask)
            metrics.update(em_m)
            delta_adv, adv_m = self._adv.generate(X, y, mask, init_delta=delta_em)
            metrics.update(adv_m)
            r = cfg.blend_ratio
            delta = r * delta_em + (1 - r) * delta_adv
            max_eps = max(cfg.em_epsilon, cfg.adv_epsilon)
            delta = delta.clamp(-max_eps, max_eps)
            frame_mask = torch.tensor(
                mask, dtype=torch.float32, device=self.device,
            ).view(-1, 1, 1, 1)
            delta = delta * frame_mask
            delta = torch.max(delta, -X)
            delta = torch.min(delta, 1.0 - X)
            metrics['blend_ratio'] = r
        else:
            raise ValueError(f"Unknown shortcut mode: {cfg.mode}")

        X_poisoned = (X + delta).clamp(0.0, 1.0)

        with torch.no_grad():
            inp = (X_poisoned * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
            logits = self.model(inp)
            if logits.dim() == 3:
                logits = logits.mean(dim=-1)
            pred = logits.argmax(dim=1).item()
            ce = nn.CrossEntropyLoss()(
                logits, torch.tensor([y], device=self.device),
            ).item()

        metrics.update({
            'sc_pred': pred,
            'sc_true_label': y,
            'sc_success': pred != y,
            'sc_final_ce': ce,
            'sc_time_s': time.time() - t0,
            'sc_delta_linf': delta.abs().max().item(),
        })
        return X_poisoned, metrics


# ═════════════════════════════════════════════════════════════════════════════
# ShortcutVidScratch — layered pipeline (formerly ShortcutDeepSAVA)
# ═════════════════════════════════════════════════════════════════════════════

class ShortcutVidScratch:
    """VidScratch with an error-minimising base layer.

    Drop-in replacement for :class:`VidScratch`.  In ``layered`` mode:

    1. Run standard VidScratch on clean frames.
    2. Apply error-minimising noise to the *non-attacked* frames.

    The two layers operate on different frames so their gradients
    never cancel each other out.
    """

    def __init__(
        self,
        model: nn.Module,
        attack_config: Optional[AttackConfig] = None,
        shortcut_config: Optional[ShortcutConfig] = None,
    ):
        self.atk_cfg = attack_config or AttackConfig()
        self.sc_cfg = shortcut_config or ShortcutConfig()
        self.device = torch.device(self.atk_cfg.device)
        self.model = model.to(self.device).eval()
        self._engine = VidScratch(model, self.atk_cfg)
        self._sc_gen = _ShortcutNoiseGenerator(model, self.sc_cfg)

    def attack(
        self,
        X: torch.Tensor,
        y: int,
        total_frames: int = 40,
        use_bo: bool = True,
        forced_mask: Optional[np.ndarray] = None,
    ) -> Tuple[torch.Tensor, Dict]:
        """Run layered or legacy shortcut attack.

        Interface matches :meth:`VidScratch.attack` exactly.
        """
        X = X.to(self.device)
        t0 = time.time()

        with torch.no_grad():
            inp = (X * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
            logit = self.model(inp)
            if logit.dim() == 3:
                logit = logit.mean(dim=-1)
            orig_pred = logit.argmax(dim=1).item()

        if self.sc_cfg.mode == 'layered':
            return self._attack_layered(
                X, y, total_frames, use_bo, forced_mask, orig_pred, t0,
            )
        return self._attack_shortcut_only(
            X, y, total_frames, use_bo, forced_mask, orig_pred, t0,
        )

    # ── Layered (v2) ─────────────────────────────────────────────────────

    def _attack_layered(
        self, X, y, total_frames, use_bo, forced_mask, orig_pred, t0,
    ) -> Tuple[torch.Tensor, Dict]:
        logger.info("=" * 50)
        logger.info("  ShortcutVidScratch v2: Layered Separation")
        logger.info("=" * 50)

        # Step 1: Attack layer — VidScratch on clean X
        logger.info("  ▶ Step 1: VidScratch (BO + spatial transform)")
        X_hat, ds_results = self._engine.attack(
            X, y, total_frames=total_frames,
            use_bo=use_bo, forced_mask=forced_mask,
        )

        mask = ds_results['mask']
        adv_status = "✓ SUCCESS" if ds_results['success'] else "✗ FAILED"
        logger.info(
            f"    VidScratch: {adv_status}  pred={ds_results['pred_label']}  "
            f"frames={ds_results['key_frames']}"
        )

        # Step 2: Base layer — error-min on non-attacked frames
        logger.info("  ▶ Step 2: Error-minimising noise (base layer)")
        em_mask = np.ones(X.shape[0], dtype=float)
        em_mask[np.where(mask > 0.5)[0]] = 0.0
        n_em = int(em_mask.sum())

        if n_em > 0:
            self.sc_cfg.em_all_frames = False
            em_gen = _ErrorMinNoise(self.model, self.sc_cfg)
            delta_em, em_metrics = em_gen.generate(X_hat, y, mask=em_mask)
            X_final = (X_hat + delta_em).clamp(0.0, 1.0)
        else:
            X_final = X_hat
            em_metrics = {'em_final_ce': -1, 'em_delta_linf': 0}

        total_t = time.time() - t0
        em_ce = em_metrics.get('em_final_ce', -1)
        em_linf = em_metrics.get('em_delta_linf', 0)

        results = {
            'mask': ds_results['mask'],
            'key_frames': ds_results['key_frames'],
            'k': ds_results['k'],
            'total_frames': total_frames,
            'orig_pred': orig_pred,
            'pred_label': ds_results['pred_label'],
            'true_label': y,
            'success': ds_results['success'],
            'ssim_final': ds_results['ssim_final'],
            'loss_history': ds_results['loss_history'],
            'total_time_s': total_t,
            'bo_time_s': ds_results.get('bo_time_s', 0),
            'use_bo': use_bo,
            'layered': True,
            'em_metrics': em_metrics,
            'em_ce': em_ce,
            'em_delta_linf': em_linf,
        }

        logger.info(
            f"  Layered done: {adv_status}  "
            f"EM CE={em_ce:.4f}  time={total_t:.1f}s"
        )
        return X_final, results

    # ── Legacy shortcut-only (v1) ────────────────────────────────────────

    def _attack_shortcut_only(
        self, X, y, total_frames, use_bo, forced_mask, orig_pred, t0,
    ) -> Tuple[torch.Tensor, Dict]:
        if self.atk_cfg.num_perturbed_frames > 0:
            k = self.atk_cfg.num_perturbed_frames
        else:
            k = max(1, round(total_frames / 40))

        if forced_mask is not None:
            mask, bo_t = forced_mask, 0.0
        elif use_bo:
            t_bo = time.time()
            mask = self._engine.bo.select(X, y, k=k)
            bo_t = time.time() - t_bo
        else:
            mask = np.zeros(X.shape[0], dtype=float)
            mask[:k] = 1.0
            bo_t = 0.0

        X_hat, sc_metrics = self._sc_gen.generate(X, y, mask)

        total_t = time.time() - t0
        results = {
            'mask': mask,
            'key_frames': np.where(mask)[0].tolist(),
            'k': k,
            'total_frames': total_frames,
            'orig_pred': orig_pred,
            'pred_label': sc_metrics['sc_pred'],
            'true_label': y,
            'success': sc_metrics['sc_success'],
            'total_time_s': total_t,
            'bo_time_s': bo_t,
            'use_bo': use_bo,
            'loss_history': sc_metrics.get(
                'em_loss_history', sc_metrics.get('adv_loss_history', []),
            ),
            'ssim_final': -1.0,
            'shortcut_metrics': sc_metrics,
        }
        return X_hat, results


# Backward-compatible alias
ShortcutDeepSAVA = ShortcutVidScratch