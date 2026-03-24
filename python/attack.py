"""
attack.py — VidScratch CLI.

Model: SlowFast R101 (77.90 % top-1 on Kinetics-400) by default.
       Pass ``--checkpoint`` to use a legacy I3D Inception checkpoint.

Usage::

    # SlowFast R101 (default)
    python attack.py --video input.mp4 --shortcut

    # Custom params
    python attack.py --video input.mp4 --shortcut \\
        --noise-clamp 0.03 --ssim-budget 0.03 --max-iter 150

    # Legacy I3D Inception
    python attack.py --video input.mp4 --checkpoint checkpoints/i3d.pt

    # Batch mode
    python attack.py --video-dir clips/ --shortcut
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys

import numpy as np
import torch

from vidscratch import (
    AttackConfig,
    ShortcutConfig,
    VidScratch,
    ShortcutVidScratch,
)
from video_io import (
    load_video,
    load_frames_from_directory,
    resize_for_model,
    apply_perturbation,
    save_video,
    save_frames_as_images,
    MODEL_NUM_FRAMES,
    MODEL_FRAME_SIZE,
    _sanitise_path,
)

logger = logging.getLogger(__name__)

# ── Label names ───────────────────────────────────────────────────────────────

_LABEL_NAMES: dict[int, str] = {}
for _f in ('kinetics_400_labels.json', 'label_map.json'):
    if os.path.isfile(_f):
        try:
            with open(_f, encoding='utf-8') as _fh:
                _LABEL_NAMES = {int(k): v for k, v in json.load(_fh).items()}
        except Exception:
            pass
        break


def _label_name(idx: int) -> str:
    return _LABEL_NAMES.get(idx, f"action_{idx}")


# ── Model loading ─────────────────────────────────────────────────────────────

def _load_model(
    checkpoint_path: str = '',
    num_classes: int = 400,
    device: str = 'cpu',
) -> torch.nn.Module:
    """Load the attack model.

    * If ``checkpoint_path`` points to an existing file -> I3D Inception.
    * Otherwise -> SlowFast R101 via PyTorchVideo (downloaded automatically).
    """
    if checkpoint_path and os.path.isfile(checkpoint_path):
        logger.info(f"Loading I3D checkpoint: {checkpoint_path}")
        try:
            from download_weights import load_model_from_checkpoint
            return load_model_from_checkpoint(checkpoint_path, num_classes, device)
        except ImportError:
            from models.i3d import InceptionI3d

            model = InceptionI3d(num_classes=num_classes, in_channels=3)
            state = torch.load(
                checkpoint_path, map_location=device, weights_only=True,
            )
            model.load_state_dict(state)
            return model.to(device).eval()

    logger.info("Loading SlowFast R101 from PyTorchVideo ...")
    try:
        from model_wrapper import load_slowfast_r101
        return load_slowfast_r101(device)
    except ImportError as exc:
        raise ImportError(
            "Install pytorchvideo:  pip install pytorchvideo\n"
            f"Error: {exc}"
        ) from exc


# ── Auto-label ────────────────────────────────────────────────────────────────

def get_label_from_model(
    model: torch.nn.Module,
    frames_224: torch.Tensor,
    device: str,
    top_k: int = 5,
) -> tuple[int, list[tuple[int, float]]]:
    inp = (frames_224.to(device) * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
    with torch.no_grad():
        logits = model(inp)
        if logits.dim() == 3:
            logits = logits.mean(dim=-1)
        probs = torch.softmax(logits, dim=1)[0]
        top_probs, top_classes = probs.topk(min(top_k, probs.shape[0]))

    predicted = top_classes[0].item()
    top_preds = [
        (c.item(), round(p.item(), 4))
        for c, p in zip(top_classes, top_probs)
    ]
    return predicted, top_preds


def _resolve_label(
    model: torch.nn.Module,
    frames_224: torch.Tensor,
    label_override: int | None,
    device: str,
) -> tuple[int, list[tuple[int, float]]]:
    """Return the attack label and top-k predictions."""
    predicted, top_preds = get_label_from_model(model, frames_224, device)
    if label_override is not None:
        return label_override, top_preds

    print("\n  +-- Auto-Label -----------------------------------------------+")
    for rank, (cls, prob) in enumerate(top_preds, 1):
        bar = "#" * int(prob * 40)
        marker = "  << using" if rank == 1 else ""
        print(f"  |  #{rank}  class {cls:4d}  {prob:.4f}  {bar}{marker}")
    print(f"  +-- label = {predicted}  ({top_preds[0][1]:.4f}) ----------------------------+\n")
    return predicted, top_preds


# ── Verify saved video ────────────────────────────────────────────────────────

def verify_saved(
    video_path: str,
    model: torch.nn.Module,
    meta,
    label: int,
    device: str,
) -> dict:
    """Reload the saved video and check if the model is fooled."""
    frames_all_saved, _ = load_video(video_path, model_window=len(meta.sampled_idx))
    frames_model = frames_all_saved[meta.sampled_idx]
    frames_224 = resize_for_model(frames_model, MODEL_FRAME_SIZE)

    inp = (frames_224.to(device) * 2.0 - 1.0).permute(1, 0, 2, 3).unsqueeze(0)
    with torch.no_grad():
        logits = model(inp)
        if logits.dim() == 3:
            logits = logits.mean(dim=-1)
        probs = torch.softmax(logits, dim=1)[0]
        top_probs, top_classes = probs.topk(min(5, probs.shape[0]))

    pred = top_classes[0].item()
    top5 = [(c.item(), round(p.item(), 4)) for c, p in zip(top_classes, top_probs)]
    return {
        'pred': pred,
        'prob': round(top_probs[0].item(), 4),
        'top5': top5,
        'fooled': pred != label,
    }


# ── Audio merge ───────────────────────────────────────────────────────────────

def _merge_audio(original_video: str, poisoned_video: str) -> None:
    """Copy audio track from original video into poisoned video using PyAV."""
    try:
        import av

        # Check if original has audio
        original = av.open(original_video)
        has_audio = any(s.type == 'audio' for s in original.streams)
        original.close()

        if not has_audio:
            print(f"  No audio in original, skipping")
            return

        temp_path = poisoned_video.replace('.mp4', '_noaudio.mp4')
        os.rename(poisoned_video, temp_path)

        inp_video = av.open(temp_path)
        inp_audio = av.open(original_video)
        output = av.open(poisoned_video, 'w')

        # Copy video stream
        video_in = inp_video.streams.video[0]
        video_out = output.add_stream(template=video_in)

        # Copy audio stream
        audio_in = inp_audio.streams.audio[0]
        audio_out = output.add_stream(template=audio_in)

        for packet in inp_video.demux(video_in):
            if packet.dts is None:
                continue
            packet.stream = video_out
            output.mux(packet)

        for packet in inp_audio.demux(audio_in):
            if packet.dts is None:
                continue
            packet.stream = audio_out
            output.mux(packet)

        output.close()
        inp_video.close()
        inp_audio.close()
        os.remove(temp_path)
        print(f"  Audio merged from original")

    except Exception as e:
        # If merge fails, restore the no-audio version
        if 'temp_path' in locals() and os.path.exists(temp_path) and not os.path.exists(poisoned_video):
            os.rename(temp_path, poisoned_video)
        print(f"  Audio merge skipped: {e}")


# ── Single-video attack ──────────────────────────────────────────────────────

def attack_single(args: argparse.Namespace, model=None) -> dict:
    """Run the full attack pipeline on one video."""
    if args.cpu:
        device = 'cpu'
    elif torch.cuda.is_available():
        device = 'cuda'
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
    print(f"  Device: {device}")
    if model is None:
        model = _load_model(args.checkpoint, args.num_classes, device)

    # 1. Load all frames
    if os.path.isdir(args.video):
        frames_all, meta = load_frames_from_directory(args.video)
    else:
        frames_all, meta = load_video(args.video)

    N = meta.total_frames
    logger.info(
        f"Loaded {N} frames ({meta.orig_width}x{meta.orig_height} "
        f"@ {meta.fps:.1f} fps)"
    )

    # 2. Model window + resize
    frames_model_orig = frames_all[meta.sampled_idx]
    frames_224 = resize_for_model(frames_model_orig, MODEL_FRAME_SIZE)

    # 3. Resolve label
    label, top_preds = _resolve_label(model, frames_224, args.label, device)
    label_source = 'auto' if args.label is None else 'provided'

    # 4. Poison budget
    k_poison = (
        args.num_perturbed
        if args.num_perturbed > 0
        else meta.num_poison_frames()
    )
    print(f"  Poison budget: {k_poison} / {N} frames (~1:{N // k_poison})")

    # 5. Build config + run attack
    cfg = AttackConfig(
        lam=args.lam,
        lr=args.lr,
        max_iterations=args.max_iter,
        num_perturbed_frames=k_poison,
        bo_max_iterations=args.bo_iter,
        ssim_budget=args.ssim_budget,
        noise_clamp=args.noise_clamp,
        verbose=not args.quiet,
        device=device,
    )

    use_shortcut = getattr(args, 'shortcut', False)
    if use_shortcut:
        sc_cfg = ShortcutConfig(
            mode=args.sc_mode,
            em_epsilon=args.sc_em_epsilon,
            adv_epsilon=args.sc_adv_epsilon,
            em_steps=args.sc_em_steps,
            adv_steps=args.sc_adv_steps,
            blend_ratio=args.sc_blend,
            device=device,
            verbose=not args.quiet,
        )
        attack_obj = ShortcutVidScratch(model, cfg, sc_cfg)
        print(
            f"\n  * ShortcutVidScratch mode={sc_cfg.mode}  "
            f"em_eps={sc_cfg.em_epsilon}  adv_eps={sc_cfg.adv_epsilon}\n"
        )
    else:
        attack_obj = VidScratch(model, cfg)

    frames_adv_224, results = attack_obj.attack(
        frames_224.to(device), label,
        total_frames=N, use_bo=not args.no_bo,
    )
    results['label_source'] = label_source
    results['label_used'] = label

    # 6. Map perturbation back
    frames_adv_all = apply_perturbation(
        frames_all.cpu(), frames_224.cpu(), frames_adv_224.cpu(), meta,
        poison_mask=results['mask'],
        resize_mode=args.resize_mode,
        smooth_kernel=args.smooth_kernel,
        codec_boost=args.codec_boost,
    )

    # 7. Save + verify loop
    os.makedirs(args.output_dir, exist_ok=True)
    base = os.path.splitext(
        os.path.basename(
            args.video.rstrip('/') if os.path.isdir(args.video) else args.video
        )
    )[0]
    adv_path = os.path.join(args.output_dir, f"{base}_adv.mp4")
    metrics_path = os.path.join(args.output_dir, f"{base}_metrics.json")

    # Grid-search verify loop
    max_noise_clamp = args.max_noise_clamp
    max_attempts = args.max_attempts
    noise_step = (
        args.retry_step if args.retry_step is not None else args.noise_step
    )

    # SSIM budget schedule for inner loop
    ssim_levels = []
    s = args.ssim_budget
    ssim_end = 0.055
    while s <= ssim_end + 1e-9:
        ssim_levels.append(round(s, 4))
        s += args.ssim_step
    if not ssim_levels or ssim_levels[-1] < ssim_end - 1e-9:
        ssim_levels.append(round(ssim_end, 4))
    ssim_levels = sorted(set(ssim_levels))

    real_verified = False
    verify_info: dict = {}
    current_frames_adv_all = frames_adv_all
    current_frames_adv_224 = frames_adv_224.cpu()
    current_noise_clamp = args.noise_clamp
    current_ssim_budget = args.ssim_budget
    attempt = 0
    current_mask = results['mask']

    print(f"\n  Grid search: noise=[{args.noise_clamp}, +{noise_step}, "
          f"max {max_noise_clamp}]  ssim={ssim_levels}\n")

    # Verify initial result
    save_video(current_frames_adv_all, adv_path, fps=meta.fps)
    attempt += 1
    verify_info = verify_saved(adv_path, model, meta, label, device)
    v_fooled = verify_info['fooled']

    _print_verify(attempt, current_noise_clamp, cfg.ssim_budget, verify_info, label)

    if v_fooled:
        real_verified = True

    # Grid search
    if not real_verified:
        first_noise_level = True
        nc = current_noise_clamp

        while nc <= max_noise_clamp + 1e-9 and not real_verified:
            if attempt >= max_attempts:
                print(f"  -> max_attempts={max_attempts} reached.")
                break

            if first_noise_level:
                ssim_to_try = [s for s in ssim_levels if s > args.ssim_budget + 1e-9]
                first_noise_level = False
            else:
                print(f"\n  === noise_clamp={nc:.4f} -> re-running BO ===")
                cfg.noise_clamp = nc
                current_noise_clamp = nc
                bo_engine = (
                    ShortcutVidScratch(model, cfg, sc_cfg) if use_shortcut
                    else VidScratch(model, cfg)
                )
                _, bo_results = bo_engine.attack(
                    frames_224.to(device), label,
                    total_frames=N, use_bo=not args.no_bo,
                )
                current_mask = bo_results['mask']
                ssim_to_try = list(ssim_levels)

            for sb in ssim_to_try:
                if attempt >= max_attempts:
                    break

                cfg.noise_clamp = nc
                cfg.ssim_budget = sb
                current_noise_clamp = nc
                current_ssim_budget = sb

                retry_engine = (
                    ShortcutVidScratch(model, cfg, sc_cfg) if use_shortcut
                    else VidScratch(model, cfg)
                )
                frames_adv_224_new, _ = retry_engine.attack(
                    frames_224.to(device), label,
                    total_frames=N, use_bo=False, forced_mask=current_mask,
                )
                current_frames_adv_224 = frames_adv_224_new.cpu()

                current_frames_adv_all = apply_perturbation(
                    frames_all.cpu(), frames_224.cpu(),
                    current_frames_adv_224, meta,
                    poison_mask=current_mask,
                    resize_mode=args.resize_mode,
                    smooth_kernel=args.smooth_kernel,
                    codec_boost=args.codec_boost,
                )

                save_video(current_frames_adv_all, adv_path, fps=meta.fps)
                attempt += 1
                verify_info = verify_saved(adv_path, model, meta, label, device)

                _print_verify(attempt, nc, sb, verify_info, label)

                if verify_info['fooled']:
                    real_verified = True
                    results['mask'] = current_mask
                    break

            nc = round(nc + noise_step, 6)
            if nc > max_noise_clamp + 1e-9:
                break

    # Merge audio from original into poisoned video
    if not os.path.isdir(args.video):
        _merge_audio(args.video, adv_path)

    # Finalise results
    results['real_verified'] = real_verified
    results['verified_pred'] = verify_info.get('pred')
    results['verified_fooled'] = verify_info.get('fooled', False)
    results['verify_top5'] = verify_info.get('top5', [])

    if args.save_frames:
        save_frames_as_images(
            frames_all, os.path.join(args.output_dir, f"{base}_orig_frames"),
        )
        save_frames_as_images(
            current_frames_adv_all,
            os.path.join(args.output_dir, f"{base}_adv_frames"),
        )

    results['total_input_frames'] = N
    results['total_output_frames'] = N
    results['orig_resolution'] = f"{meta.orig_width}x{meta.orig_height}"
    results['orig_fps'] = meta.fps

    with open(metrics_path, 'w') as f:
        json.dump(
            {k: (v.tolist() if isinstance(v, np.ndarray) else v)
             for k, v in results.items()},
            f, indent=2,
        )

    # Summary
    real_poisoned = [meta.sampled_idx[i] for i in results['key_frames']]
    in_mem = 'YES [OK]' if results['success'] else 'NO  [X]'
    verified = 'YES [OK]' if results['real_verified'] else 'NO  [X]'

    print("\n" + "=" * 64)
    print("  VidScratch Attack Summary")
    print("=" * 64)
    print(f"  Input          : {args.video}")
    print(f"  Resolution     : {meta.orig_width}x{meta.orig_height} @ {meta.fps:.1f} fps")
    print(f"  Frames in/out  : {N} / {N}  [OK] preserved")
    print(f"  Frames poisoned: {len(results['key_frames'])} "
          f"(window {results['key_frames']} -> real {real_poisoned})")
    print(f"  Label          : {label}  ({'auto' if label_source == 'auto' else 'provided'})")
    print(f"  Orig pred      : {results['orig_pred']}")
    print(f"  -- In-memory -----------------------------------------------")
    print(f"  Adv pred       : {results['pred_label']}  ->  {in_mem}")
    print(f"  -- After save/load -----------------------------------------")
    print(f"  Verified pred  : {results['verified_pred']}  ->  {verified}")
    print(f"  Attempts       : {attempt}")
    print(f"  Final noise    : {current_noise_clamp:.4f}")
    print(f"  Final ssim_bud : {current_ssim_budget:.4f}")
    print(f"  Time           : {results['total_time_s']:.1f}s")
    print(f"  Saved to       : {adv_path}")
    print("=" * 64 + "\n")

    # JSON output for GUI integration
    if getattr(args, 'json_output', False):
        json_result = {
            'verified_fooled': bool(results.get('real_verified', False)),
            'adv_path': adv_path,
            'orig_pred': int(results.get('orig_pred', -1)),
            'orig_pred_name': _label_name(int(results.get('orig_pred', -1))),
            'verified_pred': int(results.get('verified_pred', -1)),
            'verified_pred_name': _label_name(int(results.get('verified_pred', -1))),
            'orig_confidence': float(top_preds[0][1]) if top_preds else 0.0,
            'adv_confidence': float(
                verify_info.get('top5', [[0, 0]])[0][1]
            ) if verify_info.get('top5') else 0.0,
            'ssim': float(results.get('ssim_final', 0)),
            'psnr': float(
                10 * np.log10(1.0 / max(results.get('mse_final', 1e-10), 1e-10))
            ) if results.get('mse_final') else 0.0,
            'noise_clamp': float(current_noise_clamp),
            'ssim_budget': float(current_ssim_budget),
            'attempts': int(attempt),
            'total_time': float(results.get('total_time_s', 0)),
            'total_frames': N,
            'frames_poisoned': len(results.get('key_frames', [])),
            'key_frames': [int(x) for x in results.get('key_frames', [])],
            # Top-5 predictions for UI stats panel
            'orig_top5': [[int(c), float(p)] for c, p in top_preds] if top_preds else [],
            'orig_top5_names': [_label_name(int(c)) for c, _ in top_preds] if top_preds else [],
            'adv_top5': [[int(c), float(p)] for c, p in verify_info.get('top5', [])] if verify_info.get('top5') else [],
            'adv_top5_names': [_label_name(int(c)) for c, _ in verify_info.get('top5', [])] if verify_info.get('top5') else [],
        }
        sys.stdout.write(json.dumps(json_result))
        sys.stdout.flush()

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_verify(
    attempt: int, noise: float, ssim: float, info: dict, label: int,
) -> None:
    fooled = info['fooled']
    tag = 'FOOLED [OK]' if fooled else 'not fooled [X]'
    print(f"  [Verify #{attempt}  noise={noise:.4f}  ssim={ssim:.4f}]  {tag}")
    for rank, (cls, prob) in enumerate(info['top5'], 1):
        bar = "#" * int(prob * 35)
        marker = "  << label" if cls == label else (
            "  << FOOLED" if rank == 1 and fooled else ""
        )
        print(f"    #{rank}  class {cls:4d}  {prob:.4f}  {bar}{marker}")
    print()


# ── Batch mode ────────────────────────────────────────────────────────────────

def attack_batch(args: argparse.Namespace) -> None:
    if args.cpu:
        device = 'cpu'
    elif torch.cuda.is_available():
        device = 'cuda'
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
    print(f"  Device: {device}")
    model = _load_model(args.checkpoint, args.num_classes, device)

    labels: dict[str, int] = {}
    if args.label_csv and os.path.isfile(args.label_csv):
        with open(args.label_csv) as f:
            for row in csv.DictReader(f):
                labels[row['filename']] = int(row['label'])
        print(f"Loaded {len(labels)} labels from {args.label_csv}")
    else:
        print("No label CSV -> auto-labelling every video\n")

    video_files = sorted(
        f for f in os.listdir(args.video_dir)
        if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))
    )
    print(f"Found {len(video_files)} video(s) in {args.video_dir}\n")

    successes, totals = 0, 0
    for fname in video_files:
        args.video = os.path.join(args.video_dir, fname)
        args.label = labels.get(fname, None)
        try:
            res = attack_single(args, model=model)
            if res['success']:
                successes += 1
            totals += 1
        except Exception as exc:
            logger.error(f"Failed on {fname}: {exc}")

    print(
        f"\nBatch: {successes}/{totals} "
        f"({100 * successes / max(totals, 1):.1f} %)"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "VidScratch -- Sparse Adversarial Video Attack\n"
            "Default model: SlowFast R101 (77.90 % top-1)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    grp = p.add_mutually_exclusive_group()
    grp.add_argument('--video', type=str)
    grp.add_argument('--video-dir', type=str)

    p.add_argument('--label', type=int, default=None,
                   help='Target class (auto-detect if omitted)')
    p.add_argument('--label-csv', type=str, default=None)
    p.add_argument('--checkpoint', type=str, default='',
                   help='I3D checkpoint (omit -> SlowFast R101)')
    p.add_argument('--num-classes', type=int, default=400)

    # Attack parameters
    p.add_argument('--lam', type=float, default=1.0)
    p.add_argument('--lr', type=float, default=0.01)
    p.add_argument('--max-iter', type=int, default=150)
    p.add_argument('--num-perturbed', type=int, default=0,
                   help='Frames to poison (0 = auto)')
    p.add_argument('--bo-iter', type=int, default=50)
    p.add_argument('--ssim-budget', type=float, default=0.03)
    p.add_argument('--noise-clamp', type=float, default=0.03)
    p.add_argument('--no-bo', action='store_true')
    p.add_argument('--max-noise-clamp', type=float, default=0.15)
    p.add_argument('--max-attempts', type=int, default=20)

    # Retry schedule
    p.add_argument('--noise-step', type=float, default=0.01)
    p.add_argument('--ssim-step', type=float, default=0.01)

    # Imperceptibility
    p.add_argument('--smooth-kernel', type=int, default=0)
    p.add_argument('--resize-mode', type=str, default='nearest',
                   choices=['nearest', 'bilinear', 'bicubic'])
    p.add_argument('--codec-boost', type=float, default=1.5)

    p.add_argument('--output-dir', type=str, default='output')
    p.add_argument('--save-frames', action='store_true')
    p.add_argument('--cpu', action='store_true')
    p.add_argument('--quiet', action='store_true')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--json-output', action='store_true',
                   help='Print JSON to stdout (for GUI integration)')
    p.add_argument('--retry-step', type=float, default=None)

    # Shortcut noise
    p.add_argument('--shortcut', action='store_true')
    p.add_argument('--sc-mode', type=str, default='layered',
                   choices=['error_min', 'adversarial', 'hybrid', 'layered'])
    p.add_argument('--sc-em-epsilon', type=float, default=0.002)
    p.add_argument('--sc-adv-epsilon', type=float, default=0.03)
    p.add_argument('--sc-em-steps', type=int, default=50)
    p.add_argument('--sc-adv-steps', type=int, default=30)
    p.add_argument('--sc-blend', type=float, default=0.6)

    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.json_output:
        import builtins
        _orig_print = builtins.print
        def _stderr_print(*a, **kw):
            kw['file'] = sys.stderr
            _orig_print(*a, **kw)
        builtins.print = _stderr_print

    logging.basicConfig(
        level=logging.WARNING if (args.quiet or args.json_output) else logging.INFO,
        format='[%(levelname)s] %(message)s',
    )
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    if args.video_dir:
        attack_batch(args)
    elif args.video:
        attack_single(args)
    else:
        print("Error: specify --video or --video-dir")
        sys.exit(1)


if __name__ == '__main__':
    main()