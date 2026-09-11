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
from dataclasses import dataclass
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


def discover_pairs(
    data_dir: Path,
    filter_quality: bool = True,
    quality_report_path: Path | None = None,
) -> dict[tuple[str, str], list[tuple[Path, Path]]]:
    """Scan for image/mask TIFF pairs grouped by (split, class).
    
    If filter_quality is True, reads quality_report.json (if present) and excludes
    any pairs flagged as low-quality (passed == False).
    """
    files: DefaultDict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for path in sorted(data_dir.rglob("*.tif")):
        if not path.is_file():
            continue
        kind, cls, split = classify_text(" ".join(p.lower() for p in path.relative_to(data_dir).parts))
        files[(split, cls, kind)].append(path)

    # Load quality report if requested
    flagged_pairs: set[tuple[str, str]] = set()
    if filter_quality:
        candidates = [
            quality_report_path,
            data_dir / "quality_report.json",
            data_dir / "sar" / "quality_report.json",
            data_dir / "real" / "sar" / "quality_report.json",
            Path(__file__).resolve().parents[1] / "data" / "real" / "sar" / "quality_report.json",
        ]
        report_file = next((p for p in candidates if p is not None and p.is_file()), None)
        if report_file is not None:
            try:
                import json
                with open(report_file, "r", encoding="utf-8") as f:
                    rep = json.load(f)
                for entry in rep.get("pairs", {}).values():
                    if not entry.get("passed", True):
                        split_val = entry.get("split", "").lower()
                        cls_val = entry.get("class", "oil_spill").lower()
                        fn_val = entry.get("filename", "").lower()
                        if split_val and fn_val:
                            flagged_pairs.add((split_val, cls_val, fn_val))
                print(
                    f"[discover_pairs] Quality filter enabled: loaded {len(flagged_pairs)} flagged pairs from {report_file.name}",
                    flush=True,
                )
            except Exception as e:
                print(f"[discover_pairs] Warning: Failed to load quality report from {report_file}: {e}", flush=True)

    pairs: DefaultDict[tuple[str, str], list[tuple[Path, Path]]] = defaultdict(list)
    excluded_count = 0
    for (split, cls, kind), imgs in files.items():
        if kind != "image":
            continue
        masks = {p.stem: p for p in files.get((split, cls, "mask"), [])}
        for img in imgs:
            mask = masks.get(img.stem)
            if mask is not None:
                if filter_quality and (split.lower(), cls.lower(), img.name.lower()) in flagged_pairs:
                    excluded_count += 1
                    continue
                pairs[(split, cls)].append((img, mask))

    if filter_quality and excluded_count > 0:
        print(f"[discover_pairs] Quality filter active: excluded {excluded_count} flagged low-quality pairs.", flush=True)

    return dict(pairs)


class SlickDataset(Dataset):
    """Supervised pairs with on-the-fly normalization, cropping, and data augmentation."""

    def __init__(
        self,
        pairs: list[tuple[Path, Path, int]],
        crop: int,
        augment: bool = False,
    ) -> None:
        if tifffile is None:
            raise RuntimeError("tifffile is required: pip install tifffile")
        self.pairs = pairs
        self.crop = crop
        self.augment = augment

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
        if self.augment:
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
        if self.augment:
            y = random.randint(0, h - self.crop)
            x = random.randint(0, w - self.crop)
        else:
            y = (h - self.crop) // 2
            x = (w - self.crop) // 2
        return img[:, y : y + self.crop, x : x + self.crop], mask[:, y : y + self.crop, x : x + self.crop]

    @staticmethod
    def _augment(img: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
        # Random horizontal flip
        if random.random() < 0.5:
            img, mask = torch.flip(img, dims=[2]), torch.flip(mask, dims=[2])
        # Random vertical flip
        if random.random() < 0.5:
            img, mask = torch.flip(img, dims=[1]), torch.flip(mask, dims=[1])
        # Random 90-degree rotations
        k = random.randint(0, 3)
        if k:
            img, mask = torch.rot90(img, k, dims=(1, 2)), torch.rot90(mask, k, dims=(1, 2))
        # Brightness jitter: factor in [0.9, 1.1]
        factor = random.uniform(0.9, 1.1)
        img = (img * factor).clamp(0.0, 1.0)
        return img, mask


class DiceBCELoss(nn.Module):
    """Combined Dice + BCE loss for imbalanced slick segmentation."""

    def __init__(
        self,
        bce_weight: float = 0.5,
        dice_weight: float = 0.5,
        smooth: float = 1.0,
        pos_weight: float = 2.0,
    ) -> None:
        super().__init__()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight
        self.smooth = smooth
        self.pos_weight = pos_weight

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        pw = torch.tensor([self.pos_weight], device=logits.device, dtype=logits.dtype)
        bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, pos_weight=pw)

        probs = torch.sigmoid(logits)
        p_flat = probs.contiguous().view(-1)
        t_flat = targets.contiguous().view(-1)
        intersection = (p_flat * t_flat).sum()
        dice = 1.0 - (2.0 * intersection + self.smooth) / (p_flat.sum() + t_flat.sum() + self.smooth)

        return self.bce_weight * bce + self.dice_weight * dice


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
    use_cuda_amp = amp and device.type == "cuda"
    for step, (img, mask, _) in enumerate(loader):
        img, mask = img.to(device), mask.to(device)
        optimizer.zero_grad(set_to_none=True)
        if use_cuda_amp and scaler is not None:
            with torch.amp.autocast("cuda", enabled=True):
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
            print(f"    step {step + 1}/{len(loader)}: loss {loss.item():.4f}", flush=True)
    return total_loss / max(seen, 1), seen


@dataclass
class ValidationMetrics:
    oil_iou: float           # Macro mean IoU on oil-spill samples
    oil_micro_iou: float     # Micro (sum inter / sum union) IoU on oil samples
    oil_detected_rate: float # Fraction of oil samples with IoU > 0
    oil_count: int

    neg_crr: float           # Correct-rejection rate across all non-oil samples (pred has 0 oil pixels)
    neg_count: int

    no_oil_crr: float        # Correct-rejection rate on no_oil
    no_oil_count: int

    lookalike_crr: float     # Correct-rejection rate on lookalikes
    lookalike_fpr: float     # False-positive rate on lookalikes (1.0 - lookalike_crr)
    lookalike_count: int
    lookalike_fp_count: int  # Number of lookalike samples with false positive oil pixels
    lookalike_mean_fp_pix: float  # Mean FP pixels on lookalike samples

    combined_iou: float      # Legacy aggregate IoU across all samples


@torch.no_grad()
def validate(model: nn.Module, loader: DataLoader, device: torch.device, amp: bool) -> ValidationMetrics:
    model.eval()
    use_cuda_amp = amp and device.type == "cuda"

    oil_ious: list[float] = []
    oil_inters = 0.0
    oil_unions = 0.0

    no_oil_total = 0
    no_oil_clean = 0

    lookalike_total = 0
    lookalike_clean = 0
    lookalike_fp_pixels: list[int] = []

    legacy_total_iou = 0.0
    seen = 0

    for img, mask, cls_ids in loader:
        img, mask = img.to(device), mask.to(device)
        if use_cuda_amp:
            with torch.amp.autocast("cuda", enabled=True):
                logits = model(img)
        else:
            logits = model(img)
        pred = (torch.sigmoid(logits) > 0.5)

        legacy_total_iou += iou_score(pred.bool(), mask.bool()).item() * img.size(0)
        seen += img.size(0)

        for p, m, c in zip(pred, mask, cls_ids):
            c_val = c.item()
            p_b = p.bool()
            m_b = m.bool()

            if c_val == CLASS_OIL:
                inter = (p_b & m_b).sum().float().item()
                union = (p_b | m_b).sum().float().item()
                oil_inters += inter
                oil_unions += union
                sample_iou = inter / union if union > 0 else (1.0 if inter == 0 else 0.0)
                oil_ious.append(sample_iou)
            elif c_val == CLASS_NO_OIL:
                no_oil_total += 1
                fp_pix = p_b.sum().item()
                if fp_pix == 0:
                    no_oil_clean += 1
            elif c_val == CLASS_LOOKALIKE:
                lookalike_total += 1
                fp_pix = p_b.sum().item()
                lookalike_fp_pixels.append(fp_pix)
                if fp_pix == 0:
                    lookalike_clean += 1

    oil_macro_iou = sum(oil_ious) / max(len(oil_ious), 1)
    oil_micro_iou = oil_inters / max(oil_unions, 1e-6)
    oil_detected = sum(1 for x in oil_ious if x > 0)
    oil_det_rate = oil_detected / max(len(oil_ious), 1)

    no_oil_crr = no_oil_clean / max(no_oil_total, 1)
    lookalike_crr = lookalike_clean / max(lookalike_total, 1)
    lookalike_fpr = 1.0 - lookalike_crr
    lookalike_fp_count = lookalike_total - lookalike_clean

    all_neg_total = no_oil_total + lookalike_total
    all_neg_clean = no_oil_clean + lookalike_clean
    neg_crr = all_neg_clean / max(all_neg_total, 1)

    mean_lookalike_fp = sum(lookalike_fp_pixels) / max(len(lookalike_fp_pixels), 1) if lookalike_fp_pixels else 0.0
    combined_iou = legacy_total_iou / max(seen, 1)

    return ValidationMetrics(
        oil_iou=oil_macro_iou,
        oil_micro_iou=oil_micro_iou,
        oil_detected_rate=oil_det_rate,
        oil_count=len(oil_ious),
        neg_crr=neg_crr,
        neg_count=all_neg_total,
        no_oil_crr=no_oil_crr,
        no_oil_count=no_oil_total,
        lookalike_crr=lookalike_crr,
        lookalike_fpr=lookalike_fpr,
        lookalike_count=lookalike_total,
        lookalike_fp_count=lookalike_fp_count,
        lookalike_mean_fp_pix=mean_lookalike_fp,
        combined_iou=combined_iou,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "real" / "sar")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "app" / "models" / "unet_weights.pt")
    parser.add_argument("--crop", type=int, default=512)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--pos-weight", type=float, default=2.0)
    parser.add_argument("--val-split", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument(
        "--quality-filter",
        dest="quality_filter",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="filter out low-quality pairs flagged in quality_report.json (default: enabled; use --no-quality-filter to disable)",
    )
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=None,
        help="explicit path to quality_report.json (default: auto-detected under data-dir or backend/data/real/sar/)",
    )
    parser.add_argument("--dry-run", action="store_true", help="run a few synthetic steps without real data")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    if args.device == "auto":
        device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"device: {device}  (mps: {torch.backends.mps.is_available()}, cuda: {torch.cuda.is_available()})", flush=True)

    if args.dry_run:
        crop = min(args.crop, 64)
        epochs = min(args.epochs, 2)
        log_every = 1
        train_ds: Dataset = DryRunDataset(24, crop)
        val_ds: Dataset = DryRunDataset(8, crop)
        test_ds: Dataset = DryRunDataset(8, crop)
        workers = 0
    else:
        pairs = discover_pairs(
            args.data_dir,
            filter_quality=args.quality_filter,
            quality_report_path=args.quality_report,
        )
        if not pairs:
            sys.exit(
                f"no image/mask TIFF pairs found under {args.data_dir}. "
                "Run scripts/download_sar_dataset.py first, or point --data-dir at the extracted archives."
            )
        for (split, cls), group in sorted(pairs.items()):
            print(f"  {split:>5}/{cls:<12} {len(group)} pairs", flush=True)
        
        # Training pool: 618 clean oil, 685 no_oil, 685 lookalike (1,988 total)
        train_oil = pairs.get(("train", "oil_spill"), [])
        train_no_oil = pairs.get(("train", "no_oil"), [])
        train_lookalike = pairs.get(("train", "lookalike"), [])
        
        if len(train_oil) == 0:
            sys.exit("no oil_spill pairs found in training set; training on negatives only is unsupported")
        print(f"Training pool: oil={len(train_oil)}, no_oil={len(train_no_oil)}, lookalike={len(train_lookalike)} (total={len(train_oil) + len(train_no_oil) + len(train_lookalike)})", flush=True)

        # Held-out test set: 18 clean test oil, 150 no_oil, 150 lookalike (318 total)
        test_oil = pairs.get(("test", "oil_spill"), [])
        test_no_oil = pairs.get(("test", "no_oil"), [])
        test_lookalike = pairs.get(("test", "lookalike"), [])
        test_triplets = (
            [(p[0], p[1], CLASS_OIL) for p in test_oil]
            + [(p[0], p[1], CLASS_NO_OIL) for p in test_no_oil]
            + [(p[0], p[1], CLASS_LOOKALIKE) for p in test_lookalike]
        )
        print(f"Held-out test set: oil={len(test_oil)}, no_oil={len(test_no_oil)}, lookalike={len(test_lookalike)} (total={len(test_triplets)})", flush=True)

        # Stratified split for train/validation across all 3 classes (85/15)
        rng = random.Random(args.seed)
        val_triplets: list[tuple[Path, Path, int]] = []
        train_triplets: list[tuple[Path, Path, int]] = []

        for cls_id, group in [(CLASS_OIL, train_oil), (CLASS_NO_OIL, train_no_oil), (CLASS_LOOKALIKE, train_lookalike)]:
            shuffled = list(group)
            rng.shuffle(shuffled)
            n_val = max(1, int(len(shuffled) * args.val_split))
            val_triplets.extend((img, mask, cls_id) for img, mask in shuffled[:n_val])
            train_triplets.extend((img, mask, cls_id) for img, mask in shuffled[n_val:])

        rng.shuffle(train_triplets)
        rng.shuffle(val_triplets)
        print(f"Train/Val split: {len(train_triplets)} train, {len(val_triplets)} val (split ratio {args.val_split:.2f})", flush=True)

        crop, epochs, log_every, workers = args.crop, args.epochs, args.log_every, args.workers
        train_ds = SlickDataset(train_triplets, crop=crop, augment=True)
        val_ds = SlickDataset(val_triplets, crop=crop, augment=False)
        test_ds = SlickDataset(test_triplets, crop=crop, augment=False)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=workers, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=workers, drop_last=False)

    model = build_unet(in_channels=2, out_channels=1).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"U-Net params: {n_params / 1e6:.2f}M (SMP ResNet34)", flush=True)

    criterion = DiceBCELoss(bce_weight=0.5, dice_weight=0.5, pos_weight=args.pos_weight).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    amp = device.type == "cuda" and not args.no_amp
    scaler = torch.amp.GradScaler("cuda", enabled=amp) if device.type == "cuda" else None

    best_iou = 0.0
    best_epoch = -1
    checkpoint_dict: dict = {}
    for epoch in range(1, epochs + 1):
        t0 = time.time()
        loss, seen = train_epoch(model, train_loader, criterion, optimizer, scaler, device, amp, log_every)
        val_metrics = validate(model, val_loader, device, amp)
        now = time.strftime("%H:%M:%S")
        print(
            f"[{now}] epoch {epoch:>2}/{epochs} loss {loss:.4f} | "
            f"Val: oil_iou {val_metrics.oil_iou:.4f} (micro {val_metrics.oil_micro_iou:.4f}, {val_metrics.oil_detected_rate:.1%} det) | "
            f"neg_CRR {val_metrics.neg_crr:.4f} (no_oil {val_metrics.no_oil_crr:.4f}, lookalike {val_metrics.lookalike_crr:.4f}) | "
            f"lookalike_FPR {val_metrics.lookalike_fpr:.4f} ({val_metrics.lookalike_fp_count}/{val_metrics.lookalike_count} FP) "
            f"({seen} samples, {time.time() - t0:.1f}s)",
            flush=True,
        )
        checkpoint_dict = {
            "state_dict": model.state_dict(),
            "config": {
                "in_channels": 2,
                "out_channels": 1,
                "architecture": "smp.Unet",
                "encoder": "resnet34",
                "crop": args.crop,
            },
            "epoch": epoch,
            "val_iou": val_metrics.oil_iou,
            "metrics": {
                "val_oil_iou": val_metrics.oil_iou,
                "val_oil_micro_iou": val_metrics.oil_micro_iou,
                "val_oil_detected_rate": val_metrics.oil_detected_rate,
                "val_neg_crr": val_metrics.neg_crr,
                "val_no_oil_crr": val_metrics.no_oil_crr,
                "val_lookalike_crr": val_metrics.lookalike_crr,
                "val_lookalike_fpr": val_metrics.lookalike_fpr,
                "val_combined_iou": val_metrics.combined_iou,
            },
        }
        if val_metrics.oil_iou > best_iou:
            best_iou = val_metrics.oil_iou
            best_epoch = epoch
            args.output.parent.mkdir(parents=True, exist_ok=True)
            torch.save(checkpoint_dict, args.output)
            print(f"    saved best checkpoint -> {args.output} (oil_iou {val_metrics.oil_iou:.4f})", flush=True)
        if args.dry_run:
            break

    # Save final checkpoint regardless
    if checkpoint_dict:
        final_output = args.output.with_name("unet_weights_final.pt")
        torch.save(checkpoint_dict, final_output)
        print(f"    saved final checkpoint -> {final_output}")

    print(f"\nBest val oil_iou {best_iou:.4f} at epoch {best_epoch} -> {args.output}")

    # Evaluate best checkpoint on held-out test set
    if not args.dry_run and args.output.exists():
        print("\n================================================================================")
        print("EVALUATING BEST CHECKPOINT ON HELD-OUT TEST SET (NEVER SEEN IN TRAINING/VAL)")
        print("================================================================================")
        best_ckpt = torch.load(args.output, map_location=device)
        model.load_state_dict(best_ckpt["state_dict"])
        test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=workers, drop_last=False)
        test_metrics = validate(model, test_loader, device, amp=False)
        print(f"Held-Out Test Results across {len(test_ds)} unseen samples:")
        print(f"  Oil-only samples ({test_metrics.oil_count}):")
        print(f"    Macro IoU:              {test_metrics.oil_iou:.4f}")
        print(f"    Micro IoU:              {test_metrics.oil_micro_iou:.4f}")
        print(f"    Oil detected (>0 IoU):  {test_metrics.oil_detected_rate:.1%}")
        print(f"  Non-oil / Lookalike samples ({test_metrics.neg_count}):")
        print(f"    Correct-rejection rate: {test_metrics.neg_crr:.4f} ({test_metrics.neg_count - int(round(test_metrics.neg_count * (1.0 - test_metrics.neg_crr)))}/{test_metrics.neg_count})")
        print(f"    no_oil CRR:             {test_metrics.no_oil_crr:.4f}")
        print(f"    lookalike CRR:          {test_metrics.lookalike_crr:.4f}")
        print(f"    lookalike FPR:          {test_metrics.lookalike_fpr:.4f} ({test_metrics.lookalike_fp_count}/{test_metrics.lookalike_count} false alarms)")
        print(f"    lookalike mean FP pix:  {test_metrics.lookalike_mean_fp_pix:.1f} (out of 262,144)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())