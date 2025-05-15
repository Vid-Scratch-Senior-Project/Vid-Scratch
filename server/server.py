# server/server.py
import io
import uvicorn
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse, JSONResponse
import torch
import torch.nn.functional as F
from torchvision import models, transforms
import cv2

app = FastAPI()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = models.mobilenet_v2(pretrained=True).to(device).eval()

target_layer = model.features[6]

transform = transforms.Compose([
    transforms.Resize((160, 160)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

class FeatureExtractor(torch.nn.Module):
    def __init__(self, model, target_layer):
        super().__init__()
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None

        def save_gradients_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0]

        def save_activations_hook(module, input, output):
            self.activations = output

        self.target_layer.register_forward_hook(save_activations_hook)
        self.target_layer.register_backward_hook(save_gradients_hook)

    def forward(self, x):
        return self.model(x)

@app.post("/poison")
async def poison_image(file: UploadFile = File(...), eps: float = Form(0.05), threshold: float = Form(0.4)):
    try:
        contents = await file.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        x = transform(pil_image).unsqueeze(0).to(device).requires_grad_()

        extractor = FeatureExtractor(model, target_layer)
        outputs = extractor(x)
        pred_class = outputs.argmax(dim=1)
        loss = outputs[0, pred_class]
        loss.backward()

        grads = extractor.gradients
        saliency = grads.abs().max(dim=1)[0].detach().cpu().numpy()[0]  # (20x20)
        saliency_resized = cv2.resize(saliency, (160, 160))  # Match input size
        # ✅ Normalize saliency to [0, 1] like TensorFlow Grad-CAM
        saliency_resized = (saliency_resized - saliency_resized.min()) / (
                    saliency_resized.max() - saliency_resized.min() + 1e-8)

        # ✅ Apply threshold after normalization
        saliency_mask = (saliency_resized > threshold).astype(np.float32)

        # ⛔️ Fix starts here
        gradient = x.grad[0].cpu().numpy()
        signed_grad = np.sign(gradient)  # Equivalent to FGSM in TensorFlow
        mask_3ch = np.stack([saliency_mask] * 3, axis=0)
        masked_grad = signed_grad * mask_3ch
        poisoned_np = x[0].detach().cpu().numpy() + eps * masked_grad

        # ✅ De-normalize
        mean = np.array([0.485, 0.456, 0.406])[:, None, None]
        std = np.array([0.229, 0.224, 0.225])[:, None, None]
        poisoned_np = poisoned_np * std + mean
        poisoned_np = np.clip(poisoned_np, 0, 1)

        print("Grad max:", x.grad.max().item())
        print("Grad min:", x.grad.min().item())
        print("Masked grad max:", masked_grad.max())

        # Save image
        poisoned_img = Image.fromarray((poisoned_np.transpose(1, 2, 0) * 255).astype(np.uint8))
        buf = io.BytesIO()
        poisoned_img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    uvicorn.run("server.server:app", host="127.0.0.1", port=8000, reload=True)
