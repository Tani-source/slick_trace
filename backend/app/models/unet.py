"""U-Net segmentation model for Stage 0 (slick detection) plus weights loader.

Architecture follows the classic Ronneberger U-Net with a 2-band input
(Sentinel-1 VV + VH backscatter in dB, matching the Zenodo training dataset)
and a single sigmoid output channel (oil/not-oil probability).

Both `train_unet.py` and `stage0_perception.py` must use this module so the
architecture always matches the checkpoint. `load_unet` reads checkpoints saved
by `scripts/train_unet.py` (a dict with keys ``state_dict``/``config``) and also
accepts a bare state dict, in which case default config is assumed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn

DEFAULT_WEIGHTS: Path = Path(__file__).resolve().parent / "unet_weights.pt"
DEFAULT_IN_CHANNELS: int = 2
DEFAULT_BASE_FILTERS: int = 32
DEFAULT_DEPTH: int = 4


class _DoubleConv(nn.Module):
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

    def forward(self, x: Tensor) -> Tensor:
        return self.block(x)


class _Down(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.pool = nn.MaxPool2d(2)
        self.conv = _DoubleConv(in_ch, out_ch)

    def forward(self, x: Tensor) -> Tensor:
        return self.conv(self.pool(x))


class _Up(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, kernel_size=2, stride=2)
        self.conv = _DoubleConv(in_ch, out_ch)

    def forward(self, x: Tensor, skip: Tensor) -> Tensor:
        x = self.up(x)
        x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class UNet(nn.Module):
    """U-Net for 2-band SAR slick segmentation.

    Input: (B, 2, H, W) with H and W divisible by 2**depth.
    Output: (B, 1, H, W) raw logits; apply sigmoid for probabilities.
    """

    def __init__(self, in_channels: int = 2, base_filters: int = 32, depth: int = 4) -> None:
        super().__init__()
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.in_channels = in_channels
        self.base_filters = base_filters
        self.depth = depth

        self.inc = _DoubleConv(in_channels, base_filters)
        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        for d in range(depth):
            self.downs.append(_Down(base_filters * (2**d), base_filters * (2 ** (d + 1))))
        for d in range(depth - 1, -1, -1):
            self.ups.append(_Up(base_filters * (2 ** (d + 1)), base_filters * (2**d)))
        self.outc = nn.Conv2d(base_filters, 1, kernel_size=1)

    def forward(self, x: Tensor) -> Tensor:
        skips: list[Tensor] = []
        y = self.inc(x)
        skips.append(y)
        for down in self.downs:
            y = down(y)
            skips.append(y)
        for up, skip in zip(self.ups, reversed(skips[:-1])):
            y = up(y, skip)
        return self.outc(y)


def build_unet(
    in_channels: int = DEFAULT_IN_CHANNELS,
    base_filters: int = DEFAULT_BASE_FILTERS,
    depth: int = DEFAULT_DEPTH,
) -> UNet:
    return UNet(in_channels=in_channels, base_filters=base_filters, depth=depth)


def load_unet(weights_path: str | Path = DEFAULT_WEIGHTS) -> UNet:
    """Load a checkpoint into an eval-mode UNet.

    Accepts a ``train_unet.py`` checkpoint dict (``state_dict`` + ``config``)
    or a bare state dict (default config assumed).
    """
    path = Path(weights_path)
    if not path.exists():
        raise FileNotFoundError(f"unet weights not found: {path}")
    checkpoint: Any = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        config = checkpoint.get("config", {})
        model = build_unet(
            in_channels=int(config.get("in_channels", DEFAULT_IN_CHANNELS)),
            base_filters=int(config.get("base_filters", DEFAULT_BASE_FILTERS)),
            depth=int(config.get("depth", DEFAULT_DEPTH)),
        )
        model.load_state_dict(checkpoint["state_dict"])
    else:
        model = build_unet()
        try:
            model.load_state_dict(checkpoint["state_dict"] if isinstance(checkpoint, dict) else checkpoint)
        except Exception:
            state = checkpoint
            if isinstance(state, dict) and "model" in state:
                state = state["model"]
            model.load_state_dict(state)
    model.eval()
    return model