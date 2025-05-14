import sys
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
from art.estimators.classification import PyTorchClassifier
from art.attacks.evasion import FastGradientMethod

# Image preprocessing for torch
transform = transforms.Compose([
    transforms.Resize((160, 160)),
    transforms.ToTensor(),
])

def load_image_tensor(path):
    image = Image.open(path).convert("RGB")
    return transform(image).unsqueeze(0)  # (1, C, H, W)

def save_image_tensor(tensor, path):
    image = tensor.squeeze().detach().numpy().transpose(1, 2, 0)
    image = (image * 255).clip(0, 255).astype(np.uint8)
    Image.fromarray(image).save(path)

def get_model():
    model = models.resnet18(pretrained=True)
    model.fc = nn.Linear(model.fc.in_features, 2)  # dummy 2-class output
    return model

def poison(image_path, eps, output_path):
    if not image_path or image_path == "undefined":
        raise ValueError("Invalid image path provided.")
    model = get_model()
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    classifier = PyTorchClassifier(
        model=model,
        loss=loss_fn,
        optimizer=optimizer,
        input_shape=(3, 160, 160),
        nb_classes=2,
        clip_values=(0.0, 1.0),
    )

    x = load_image_tensor(image_path).numpy()
    y = np.array([[1, 0]])  # dummy label: one-hot

    fgsm = FastGradientMethod(estimator=classifier, eps=eps)
    x_poisoned = fgsm.generate(x=x)
    poisoned_tensor = torch.tensor(x_poisoned[0])

    save_image_tensor(poisoned_tensor, output_path)
    print(f"Poisoned image saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python poison.py <image_path> <eps> <output_path>")
        sys.exit(1)
    _, img_path, epsilon, out_path = sys.argv
    poison(img_path, float(epsilon), out_path)
