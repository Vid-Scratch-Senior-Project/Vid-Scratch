import numpy as np
import pytest
import torch

from video_io import (
    VideoMeta,
    _sanitise_path,
    _validate_video_path,
    resize_for_model,
    apply_perturbation,
)


def make_meta(total_frames=4, sampled_idx=None):
    return VideoMeta(
        orig_height=8,
        orig_width=8,
        fps=25.0,
        total_frames=total_frames,
        sampled_idx=sampled_idx or [0, 1, 2, 3],
        source_path="/tmp/demo.mp4",
    )


def test_sanitise_path_rejects_null_bytes():
    with pytest.raises(ValueError):
        _sanitise_path("bad\x00path.mp4")


def test_validate_video_path_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.mp4"
    with pytest.raises(FileNotFoundError):
        _validate_video_path(str(missing))


def test_validate_video_path_rejects_invalid_extension(tmp_path):
    f = tmp_path / "demo.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        _validate_video_path(str(f))


def test_num_poison_frames_returns_10_when_total_frames_ge_model_window():
    meta = make_meta(total_frames=40)
    assert meta.num_poison_frames() == 10


def test_num_poison_frames_returns_quarter_for_small_video():
    meta = make_meta(total_frames=8)
    assert meta.num_poison_frames() == 2


def test_num_poison_frames_honors_custom_k():
    meta = make_meta(total_frames=8)
    assert meta.num_poison_frames(custom_k=7) == 7


def test_resize_for_model_returns_expected_shape():
    frames = torch.rand(4, 3, 8, 10)
    out = resize_for_model(frames, target_size=16)
    assert out.shape == (4, 3, 16, 16)


def test_apply_perturbation_only_changes_masked_frames():
    frames_all = torch.zeros(4, 3, 8, 8)
    frames_model_224 = torch.zeros(4, 3, 224, 224)
    frames_adv_224 = frames_model_224.clone()
    frames_adv_224[1] += 0.2
    frames_adv_224[3] += 0.3

    meta = make_meta(total_frames=4, sampled_idx=[0, 1, 2, 3])
    poison_mask = np.array([0, 1, 0, 1], dtype=np.float32)

    out = apply_perturbation(
        frames_all=frames_all,
        frames_model_224=frames_model_224,
        frames_adv_224=frames_adv_224,
        meta=meta,
        poison_mask=poison_mask,
        resize_mode="nearest",
        smooth_kernel=0,
        codec_boost=1.0,
    )

    assert torch.allclose(out[0], torch.zeros_like(out[0]))
    assert torch.any(out[1] > 0)
    assert torch.allclose(out[2], torch.zeros_like(out[2]))
    assert torch.any(out[3] > 0)


def test_apply_perturbation_clamps_values_to_0_1():
    frames_all = torch.ones(2, 3, 8, 8) * 0.95
    frames_model_224 = torch.zeros(2, 3, 224, 224)
    frames_adv_224 = torch.ones(2, 3, 224, 224) * 2.0
    meta = make_meta(total_frames=2, sampled_idx=[0, 1])

    out = apply_perturbation(
        frames_all=frames_all,
        frames_model_224=frames_model_224,
        frames_adv_224=frames_adv_224,
        meta=meta,
        poison_mask=np.array([1, 1], dtype=np.float32),
        codec_boost=1.0,
    )

    assert float(out.max()) <= 1.0
    assert float(out.min()) >= 0.0