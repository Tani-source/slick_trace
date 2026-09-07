from __future__ import annotations

from pathlib import Path


def build_unet(in_channels: int = 1, out_channels: int = 1):
    """Standard encoder-decoder U-Net (PyTorch) for SAR slick segmentation.

    PyTorch is imported lazily so the API server can boot even on machines
    that do not yet have the ML stack installed (rules.md §1 allow-list).
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class DoubleConv(nn.Module):
        def __init__(self, in_ch: int, out_ch: int) -> None:
            super().__init__()
            self.block = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.block(x)

    class Down(nn.Module):
        def __init__(self, in_ch: int, out_ch: int) -> None:
            super().__init__()
            self.pool = nn.MaxPool2d(2)
            self.conv = DoubleConv(in_ch, out_ch)

        def forward(self, x):
            return self.conv(self.pool(x))

    class Up(nn.Module):
        def __init__(self, in_ch: int, out_ch: int) -> None:
            super().__init__()
            self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_ch, out_ch)

        def forward(self, x1, x2):
            x1 = self.up(x1)
            diff_y = x2.size(2) - x1.size(2)
            diff_x = x2.size(3) - x1.size(3)
            x1 = F.pad(x1, [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2])
            x = torch.cat([x2, x1], dim=1)
            return self.conv(x)

    class UNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.inc = DoubleConv(in_channels, 64)
            self.down1 = Down(64, 128)
            self.down2 = Down(128, 256)
            self.down3 = Down(256, 512)
            self.down4 = Down(512, 512)
            self.up1 = Up(1024, 256)
            self.up2 = Up(512, 128)
            self.up3 = Up(256, 64)
            self.up4 = Up(128, 64)
            self.outc = nn.Conv2d(64, out_channels, kernel_size=1)

        def forward(self, x):
            x1 = self.inc(x)
            x2 = self.down1(x1)
            x3 = self.down2(x2)
            x4 = self.down3(x3)
            x5 = self.down4(x4)
            x = self.up1(x5, x4)
            x = self.up2(x, x3)
            x = self.up3(x, x2)
            x = self.up4(x, x1)
            return self.outc(x)

    return UNet()


def load_weights(model, weights_path: str | Path) -> None:
    import torch

    state = torch.load(weights_path, map_location="cpu")
    model.load_state_dict(state)


def unet_inference(image_float: object, weights_path: str | None) -> object:
    """Run U-Net inference and return a boolean mask ndarray.

    Raises on any inference failure so callers surface an explicit failure
    instead of silently falling back to a different method.
    """
    import numpy as np
    import torch

    from ..config import UNET_WEIGHTS_PATH

    resolved = weights_path or UNET_WEIGHTS_PATH
    model = build_unet(in_channels=1, out_channels=1)
    load_weights(model, resolved)
    model.eval()

    tensor = torch.from_numpy(np.asarray(image_float, dtype=np.float32))[None, None, :, :]
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)
    mask = (probs[0, 0].numpy() > 0.5)
    return mask
