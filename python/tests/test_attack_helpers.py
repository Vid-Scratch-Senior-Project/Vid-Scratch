import torch
from attack import get_label_from_model, _resolve_label


class DummyModel(torch.nn.Module):
    def __init__(self, logits):
        super().__init__()
        self._logits = logits

    def forward(self, x):
        return self._logits


def test_get_label_from_model_returns_top_prediction_and_topk():
    logits = torch.tensor([[0.1, 2.0, 0.5, 1.0]])
    model = DummyModel(logits)
    frames = torch.rand(4, 3, 224, 224)

    predicted, top_preds = get_label_from_model(model, frames, device="cpu", top_k=3)

    assert predicted == 1
    assert len(top_preds) == 3
    assert top_preds[0][0] == 1


def test_get_label_from_model_handles_3d_logits_by_averaging_last_dim():
    logits = torch.tensor([[[0.1, 0.2], [1.5, 1.0], [0.3, 0.4]]])  # (1,3,2)
    model = DummyModel(logits)
    frames = torch.rand(4, 3, 224, 224)

    predicted, top_preds = get_label_from_model(model, frames, device="cpu", top_k=2)

    assert predicted == 1
    assert len(top_preds) == 2


def test_resolve_label_uses_override_when_provided():
    logits = torch.tensor([[0.1, 2.0, 0.5]])
    model = DummyModel(logits)
    frames = torch.rand(4, 3, 224, 224)

    label, top_preds = _resolve_label(
        model=model,
        frames_224=frames,
        label_override=2,
        device="cpu",
    )

    assert label == 2
    assert top_preds[0][0] == 1


def test_resolve_label_uses_predicted_label_when_override_is_none():
    logits = torch.tensor([[0.1, 2.0, 0.5]])
    model = DummyModel(logits)
    frames = torch.rand(4, 3, 224, 224)

    label, _ = _resolve_label(
        model=model,
        frames_224=frames,
        label_override=None,
        device="cpu",
    )

    assert label == 1