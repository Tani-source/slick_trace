"""Train the Stage 0 slick-segmentation U-Net on the Zenodo SAR oil-spill dataset.

Runbook (Google Colab / Kaggle GPU):
    1.  git clone <your repo>  # or upload backend/
    2.  In the runtime:  cd backend
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
        pip install numpy tifffile
    3.  python scripts/download_sar_dataset.py --records i     # oil train first (~40 GB)
    4.  python scripts/train_unet.py --data-dir data/dataset   # starts training
    5.  The best-validation model is saved as backend/app/models/unet_weights.pt
        (persist across Colab sessions with e.g.
         --output /content/drive/MyDrive/slicktrace/unet_weights.pt)

Dataset layout (produced by download_sar_dataset.py): any tree of TIFFs under
--data-dir. Images vs. masks are told apart by their parent folder name
("mask"/"ground truth" = mask), oil / no-oil / look-alike classes by folder
keywords, and test vs. train by the "test" keyword. Pairs are matched by file
stem. This is intentionally loose so the three Zenodo archives need no
restructuring.

Preprocessing: SAR bands (VV, VH, dB) are percentile-clipped (1-99) and
min-max scaled to [0,1] per band. Training uses random crops (--crop), random
hflip/vflip/rot90, BCEWithLogitsLoss with a positive-weight on the oil class,
and IoU validation. Minority classes (no-oil, look-alike) are oversampled so
every epoch sees all classes. Checkpoints are saved whenever validation IoU
improves, and the best is written to --output as a {"state_dict", "config"}
dict compatible with backends that call app.models.unet.load_unet.

Tradeoffs (stated, per rules.md): a plain U-Net without a pretrained encoder
because SAR dB inputs have no ImageNet features to reuse; the percentile
normalizer is a stand-in for full SNAP radiometric calibration in production.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

import numpy as np
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.unet import build_unet

try:
    import tifffile
except ImportError:
    tifffile = None

CLASS_OIL = 0
CLASS_NO_OIL = 1
CLASS_LOOKALIKE = 2
CLASS_NAMES = ["oil_spill", "no_oil", "lookalike"]
NO_OIL_HINTS = ("no_oil", "no oil", "oil free", "oil-free", "nooil")
LOOKALIKE_HINTS = ("lookalike", "look-alike", "look_alike")


def classify_text(text: str) -> tuple[str, str, str]:
    """Return (kind, class_name, split) for a path's lowercased text."""
    kind = "mask" if any(k in text for k in ("mask", "ground", "groundtruth", "gt_", "ground_truth")) else "image"
    if any(k in text for k in LOOKALIKE_HINTS):
        cls = "lookalike"
    elif any(k in text for k in NO_OIL_HINTS):
        cls = "no_oil"
    elif "oil" in text:
        cls = "oil_spill"
    else:
        cls = "unknown"
    split = "test" if "test" in text else "train"
    return kind, cls, split


def class_id_of_path(path: Path) -> int:
    text = " ".join(p.lower() for p in path.parts)
    if any(k in text for k in LOOKALIKE_HINTS):
        return CLASS_LOOKALIKE
    if any(k in text for k in NO_OIL_HINTS):
        return CLASS_NO_OIL
    if "oil" in text:
        return CLASS_OIL
    return CLASS_LOOKALIKE


def discover_pairs(data_dir: Path) -> dict[tuple[str, str], list[tuple[Path, Path]]]:
    """Scan for image/mask TIFF pairs grouped by (split, class)."""
    files: DefaultDict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for path in sorted(data_dir.rglob("*.tif")):
        if not path.is_file():
            continue
        kind, cls, split = classify_text(" ".join(p.lower() for p in path.relative_to(data_dir).parts))
        files[(split, cls, kind)].append(path)

    pairs: DefaultDict[tuple[str, str], list[tuple[Path, Path]]] = defaultdict(list)
    for (split, cls, kind), imgs in files.items():
        if kind != "image":
            continue
        masks = {p.stem: p for p in files.get((split, cls, "mask"), [])}
        for img in imgs:
            mask = masks.get(img.stem)
            if mask is not None:
                pairs[(split, cls)].append((img, mask))
    return dict(pairs)


class SlickDataset(Dataset):
    """Random-crop supervised pairs with on-the-fly normalization + augmentation."""

    def __init__(self, pairs: list[tuple[Path, Path, int]], crop: int) -> None:
        if tifffile is None:
            raise RuntimeError("tifffile is required: pip install tifffile")
        self.pairs = pairs
        self.crop = crop

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> tuple[Tensor, Tensor, Tensor]:
        img_path, mask_path, cls_id = self.pairs[idx]
        img = tifffile.imread(img_path)
        mask = tifffile.imread(mask_path)
        if img.ndim == 3 and img.shape[-1] == 2:
            img = np.transpose(img, (2, 0, 1))
        elif img.ndim == 3 and img.shape[0] == 2:
            pass
        else:
            raise ValueError(f"unexpected SAR image shape {img.shape}: {img_path}")
        if mask.ndim == 3:
            mask = mask[..., 0] if mask.shape[-1] == 1 else mask[:, :, 0]
        mask = (mask > 0).astype(np.float32)

        img = torch.from_numpy(img.astype(np.float32))
        mask = torch.from_numpy(mask).unsqueeze(0)
        img = self._normalize(img)
        img, mask = self._crop(img, mask)
        img, mask = self._augment(img, mask)
        return img, mask, torch.tensor(cls_id, dtype=torch.long)

    @staticmethod
    def _normalize(img: Tensor) -> Tensor:
        eps = 1e-6
        b, h, w = img.shape
        flat = img.reshape(b, h * w)
        lo = torch.quantile(flat, 0.01, dim=1, keepdim=True).reshape(b, 1, 1)
        hi = torch.quantile(flat, 0.99, dim=1, keepdim=True).reshape(b, 1, 1)
        img = (img - lo) / (hi - lo + eps)
        return img.clamp(0.0, 1.0)

    def _crop(self, img: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
        _, h, w = img.shape
        if h < self.crop or w < self.crop:
            raise ValueError(f"crop {self.crop} exceeds image {h}x{w}")
        y = random.randint(0, h - self.crop)
        x = random.randint(0, w - self.crop)
        return img[:, y : y + self.crop, x : x + self.crop], mask[:, y : y + self.crop, x : x + self.crop]

    @staticmethod
    def _augment(img: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
        if random.random() < 0.5:
            img, mask = torch.flip(img, dims=[2]), torch.flip(mask, dims=[2])
        if random.random() < 0.5:
            img, mask = torch.flip(img, dims=[1]), torch.flip(mask, dims=[1])
        k = random.randint(0, 3)
        if k:
            img, mask = torch.rot90(img, k, dims=(1, 2)), torch.rot90(mask, k, dims=(1, 2))
        return img, mask


class DryRunDataset(Dataset):
    """Tiny in-memory stand-in so the loop can be smoke-tested without data."""

    def __init__(self, n: int, crop: int) -> None:
        self.n = n
        self.crop = crop

    def __len__(self) -> int:
        return self.n

    def __getitem__(self, idx: int) -> tuple[Tensor, Tensor, Tensor]:
        rng = torch.Generator().manual_seed(idx)
        img = torch.rand(2, 64, 64, generator=rng)
        mask = (torch.rand(1, 64, 64, generator=rng) > 0.85).float()
        return (
            img[:, : self.crop, : self.crop],
            mask[:, : self.crop, : self.crop],
            torch.tensor(idx % 3, dtype=torch.long),
        )


def balanced_triplets(pairs: list[tuple[Path, Path]], seed: int) -> list[tuple[Path, Path, int]]:
    """Oversample minority classes so every epoch sees all classes."""
    by_class: DefaultDict[int, list[tuple[Path, Path]]] = defaultdict(list)
    for img, mask in pairs:
        by_class[class_id_of_path(img)].append((img, mask))
    by_class.setdefault(CLASS_OIL, [])
    by_class.setdefault(CLASS_NO_OIL, [])
    by_class.setdefault(CLASS_LOOKALIKE, [])
    max_len = max(len(v) for v in by_class.values())
    out: list[tuple[Path, Path, int]] = []
    for cls_id, values in by_class.items():
        reps = values * (max_len // max(len(values), 1) + 1)
        out.extend((img, mask, cls_id) for img, mask in reps[:max_len])
    random.Random(seed).shuffle(out)
    return out


def iou_score(pred: Tensor, target: Tensor, eps: float = 1e-6) -> Tensor:
    inter = (pred & target).sum().float()
    union = (pred | target).sum().float()
    return (inter + eps) / (union + eps)


def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler | None,
    device: torch.device,
    amp: bool,
    log_every: int,
) -> tuple[float, int]:
    model.train()
    total_loss = 0.0
    seen = 0
    for step, (img, mask, _) in enumerate(loader):
        img, mask = img.to(device), mask.to(device)
        optimizer.zero_grad(set_to_none=True)
        if scaler is not None:
            with torch.amp.autocast("cuda", enabled=amp):
                logits = model(img)
                loss = criterion(logits, mask)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(img)
            loss = criterion(logits, mask)
            loss.backward()
            optimizer.step()
        total_loss += loss.item() * img.size(0)
        seen += img.size(0)
        if log_every and (step + 1) % log_every == 0:
            print(f"    step {step + 1}: loss {loss.item():.4f}", flush=True)
    return total_loss / max(seen, 1), seen


@torch.no_grad()
def validate(model: nn.Module, loader: DataLoader, device: torch.device, amp: bool) -> float:
    model.eval()
    total_iou = 0.0
    seen = 0
    for img, mask, _ in loader:
        img, mask = img.to(device), mask.to(device)
        with torch.amp.autocast("cuda", enabled=amp):
            logits = model(img)
        pred = torch.sigmoid(logits) > 0.5
        total_iou += iou_score(pred.bool(), mask.bool()).item() * img.size(0)
        seen += img.size(0)
    return total_iou / max(seen, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "dataset")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "app" / "models" / "unet_weights.pt")
    parser.add_argument("--crop", type=int, default=512)
    parser.add_argument("--base-filters", type=int, default=32)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--pos-weight", type=float, default=5.0)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="run a few synthetic steps without real data")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"device: {device}  (cuda: {torch.cuda.is_available()})", flush=True)

    if args.dry_run:
        crop = min(args.crop, 64)
        epochs = min(args.epochs, 2)
        log_every = 1
        train_ds: Dataset = DryRunDataset(24, crop)
        val_ds: Dataset = DryRunDataset(8, crop)
        workers = 0
    else:
        pairs = discover_pairs(args.data_dir)
        if not pairs:
            sys.exit(
                f"no image/mask TIFF pairs found under {args.data_dir}. "
                "Run scripts/download_sar_dataset.py first, or point --data-dir at the extracted archives."
            )
        for (split, cls), group in pairs.items():
            print(f"  {split:>5}/{cls:<12} {len(group)} pairs", flush=True)
        oil = sum(len(v) for (s, c), v in pairs.items() if c == "oil_spill")
        if oil == 0:
            sys.exit("no oil_spill pairs found; training on negatives only is unsupported")
        pooled = (
            pairs.get(("train", "oil_spill"), [])
            + pairs.get(("train", "no_oil"), [])
            + pairs.get(("train", "lookalike"), [])
        )
        triplets = balanced_triplets(pooled, args.seed)
        rng = random.Random(args.seed)
        rng.shuffle(triplets)
        n_val = max(1, int(len(triplets) * args.val_split))
        val_triplets, train_triplets = triplets[:n_val], triplets[n_val:]
        crop, epochs, log_every, workers = args.crop, args.epochs, args.log_every, args.workers
        train_ds = SlickDataset(train_triplets, crop)
        val_ds = SlickDataset(val_triplets, crop)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=workers, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=workers, drop_last=False)

    model = build_unet(in_channels=2).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"U-Net params: {n_params / 1e6:.2f}M", flush=True)

    bw = torch.tensor([args.pos_weight]).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=bw)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    amp = device.type == "cuda" and not args.no_amp
    scaler = torch.amp.GradScaler("cuda", enabled=amp) if device.type == "cuda" else None

    best_iou = 0.0
    best_epoch = -1
    for epoch in range(1, epochs + 1):
        t0 = time.time()
        loss, seen = train_epoch(model, train_loader, criterion, optimizer, scaler, device, amp, log_every)
        val_iou = validate(model, val_loader, device, amp)
        now = time.strftime("%H:%M:%S")
        print(f"[{now}] epoch {epoch}/{epochs} loss {loss:.4f} val_iou {val_iou:.4f} ({seen} samples, {time.time() - t0:.1f}s)", flush=True)
        if val_iou > best_iou:
            best_iou = val_iou
            best_epoch = epoch
            args.output.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "config": {"in_channels": 2, "base_filters": args.base_filters, "depth": args.depth, "crop": args.crop},
                    "epoch": epoch,
                    "val_iou": val_iou,
                },
                args.output,
            )
            print(f"    saved best checkpoint -> {args.output} (val_iou {val_iou:.4f})", flush=True)
        if args.dry_run:
            break

    print(f"\nBest val IoU {best_iou:.4f} at epoch {best_epoch} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())