from __future__ import annotations

from pathlib import Path


def build_unet(in_channels: int = 2, out_channels: int = 1):
    """Pretrained ResNet34 U-Net (segmentation-models-pytorch) for SAR slick segmentation.

    PyTorch and segmentation_models_pytorch are imported lazily so the API server can boot
    even on machines that do not yet have the ML stack installed (rules.md §1 allow-list).
    """
    import segmentation_models_pytorch as smp

    return smp.Unet(
        encoder_name="resnet34",
        encoder_weights="imagenet",
        in_channels=in_channels,
        classes=out_channels,
    )


def load_weights(model, weights_path: str | Path) -> dict:
    import torch

    state = torch.load(weights_path, map_location="cpu")
    if isinstance(state, dict) and "state_dict" in state:
        sd = state["state_dict"]
    else:
        sd = state
    model.load_state_dict(sd)
    return sd


def unet_inference(image_float: object, weights_path: str | None) -> object:
    """Run U-Net inference and return a boolean mask ndarray.

    Raises on any inference failure so callers surface an explicit failure
    instead of silently falling back to a different method.
    """
    import numpy as np
    import torch

    from ..config import UNET_WEIGHTS_PATH

    resolved = weights_path or UNET_WEIGHTS_PATH
    state = torch.load(resolved, map_location="cpu")
    sd = state.get("state_dict", state) if isinstance(state, dict) else state
    
    if isinstance(state, dict) and "config" in state:
        in_ch = state["config"].get("in_channels", 2)
        out_ch = state["config"].get("out_channels", 1)
    elif "encoder.conv1.weight" in sd:
        in_ch = sd["encoder.conv1.weight"].shape[1]
        out_ch = sd["segmentation_head.0.weight"].shape[0] if "segmentation_head.0.weight" in sd else 1
    elif "inc.block.0.weight" in sd:
        in_ch = sd["inc.block.0.weight"].shape[1]
        out_ch = sd["outc.weight"].shape[0] if "outc.weight" in sd else 1
    else:
        in_ch = 2
        out_ch = 1

    model = build_unet(in_channels=in_ch, out_channels=out_ch)
    model.load_state_dict(sd)
    model.eval()

    arr = np.asarray(image_float, dtype=np.float32)
    # Channel normalization matching SlickDataset
    if arr.ndim == 2:
        arr = np.stack([arr, arr], axis=0) if in_ch == 2 else arr[None, :, :]
    elif arr.ndim == 3:
        if arr.shape[0] != in_ch and arr.shape[2] == in_ch:
            arr = np.transpose(arr, (2, 0, 1))

    t = torch.from_numpy(arr)
    if t.ndim == 2:
        t = t[None, :, :]
    b, h, w = t.shape
    flat = t.reshape(b, h * w)
    lo = torch.quantile(flat, 0.01, dim=1, keepdim=True).reshape(b, 1, 1)
    hi = torch.quantile(flat, 0.99, dim=1, keepdim=True).reshape(b, 1, 1)
    t = (t - lo) / (hi - lo + 1e-6)
    tensor = t.clamp(0.0, 1.0)[None, :, :, :]

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)[0, 0]

    p_max = float(probs.max())
    p_mean = float(probs.mean())
    p_std = float(probs.std())

    # Adaptive threshold for unet segmentation (fallback to 0.15 if probabilities are shifted)
    thresh = max(0.15, min(0.5, p_mean + 1.0 * p_std)) if p_max >= 0.15 else 0.5
    mask = (probs.numpy() > thresh)
    return mask
