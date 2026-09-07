"""Generate realistic synthetic SAR scenes and oil-spill masks.

Renders Sentinel-1-like GRD imagery (VV + VH in dB) plus a binary oil mask,
using simplified but physically-motivated SAR scattering:

  sigma0_VV(dB) = BASELINE + ALPHA*log10(U10) + GAMMA*log10(sin(incidence))
  sigma0_VH(dB) = sigma0_VV(dB) - VH_OFFSET

Then adds:
  * Multi-look Rayleigh speckle (4 looks, realistic for GRD)
  * A smooth power-law sea-clutter gradient across the swath
  * Wind streaks and organic frontal slicks (look-alike structures)
  * The actual oil slick (damping of Sigma0) + ship PSF targets

Scenes are saved in the exact folder convention expected by
`train_unet.py` (image under ``oil_spill/``, mask under ``mask/``) so no
training-loop changes are needed. Masks are saved via PIL (uint8, 0/255).

Other than the demo scene (which seeds from the shared scenario slick
polygon so it is geolocated and consistent with ``scenario.json``), the
training scenes are procedurally generated oil blobs in arbitrary frames —
their only requirement is realistic texture, not geolocation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import tifffile

from . import config as C


def _sigma0_linear(U10: float, incidence_deg: float,
                   baseline_db: float = C.SAR_BASELINE_DB,
                   alpha: float = C.SAR_ALPHA,
                   gamma: float = C.SAR_GAMMA) -> float:
    sig0_vv_db = baseline_db + alpha * np.log10(max(U10, 1.0)) + gamma * np.log10(np.sin(np.radians(incidence_deg)))
    return 10 ** (sig0_vv_db / 10.0)


def _rectangle_mask(n: int) -> np.ndarray:
    """Return True everywhere (for full-frame renders)."""
    return np.ones((n, n), dtype=bool)


def _slick_shape_mask(rng: np.random.Generator, n: int, k: int) -> np.ndarray:
    """Procedural slick blob mask of index k (oil_spill training scenes)."""
    canvas = Image.new("L", (n, n), 0)
    draw = ImageDraw.Draw(canvas)
    cx, cy = rng.uniform(0.25, 0.75, 2) * n
    # Main body + trailing smear (wind-swept tail)
    n_blobs = rng.integers(4, 9)
    for b in range(n_blobs):
        bx = cx + rng.normal(0, 0.08 * n)
        by = cy + rng.normal(0, 0.05 * n)
        r = rng.uniform(0.02, 0.06) * n
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=255)
    # Elongated tail toward downwind
    tail_len = rng.uniform(0.2, 0.5) * n
    tail_angle = rng.uniform(0, 2 * np.pi)
    tx, ty = cx + tail_len * np.cos(tail_angle), cy + tail_len * np.sin(tail_angle)
    for t in range(6):
        bx = np.linspace(cx, tx, 6)[t] + rng.normal(0, 0.03 * n)
        by = np.linspace(cy, ty, 6)[t] + rng.normal(0, 0.03 * n)
        r = rng.uniform(0.01, 0.03) * n * (1 - t / 6)
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=255)
    mask = np.array(canvas) > 0
    return mask


def _speckle(n: int, sigma0: float, num_looks: int, rng: np.random.Generator) -> np.ndarray:
    """Multilook speckle: mean of `num_looks` exponential samples."""
    samples = np.zeros((n, n), dtype=np.float32)
    for _ in range(num_looks):
        samples += rng.exponential(scale=sigma0, size=(n, n))
    return samples / num_looks


def _apply_clutter_gradient(sigma0_base: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth large-scale power-law gradient plus wind streaks."""
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    grad = (1.0 + 0.15 * (yy / n)) * (1.0 + 0.1 * np.sin(np.pi * xx / n))
    streaks = 1.0 + 0.05 * np.sin(2 * np.pi * (xx * 0.05 + yy * 0.002 + rng.uniform(0, 2 * np.pi)))
    return sigma0_base * grad * streaks


def _lookalike_zones(n: int, rng: np.random.Generator) -> np.ndarray:
    """Add low-sigma biogenic/frontal slicks (look-alone structures)."""
    zones = np.zeros((n, n), dtype=np.float32)
    for _ in range(rng.integers(1, 4)):
        cx, cy = rng.uniform(0, 1, 2) * n
        r1 = rng.uniform(0.05, 0.15) * n
        r2 = r1 * rng.uniform(0.4, 0.8)
        ang = rng.uniform(0, np.pi)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        dist = np.sqrt(((xx - cx) * np.cos(ang) - (yy - cy) * np.sin(ang)) ** 2 / r1 ** 2 +
                       ((xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang)) ** 2 / r2 ** 2)
        zones += np.exp(-0.5 * dist ** 2) * rng.uniform(0.7, 0.9)
    return zones


def _ship_targets(n: int, rng: np.random.Generator) -> np.ndarray:
    """Add bright ship point-targets (PSF) outside the slick."""
    ships = np.zeros((n, n), dtype=np.float32)
    for _ in range(rng.integers(1, 4)):
        cx, cy = int(rng.uniform(0.05, 0.95) * n), int(rng.uniform(0.05, 0.95) * n)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        r2 = (xx - cx) ** 2 + (yy - cy) ** 2
        ships += C.SHIP_PEAK_DB * np.exp(-r2 / (2 * C.SHIP_PSF_RADIUS_PX ** 2))
    return ships


def render_demo_scene(
    out_dir: Path,
    slick_polygon: list[list[float]],
    rng: np.random.Generator,
) -> Path:
    """Render the geolocated demo SAR scene + mask at the scenario's slick.

    The scene covers the scenario bbox; the slick polygon (lat/lon) is
    projected onto pixel space and damped. Output:
      out_dir/demo_scene.tif (two-band VV,VH float32 dB)
      out_dir/demo_scene_mask.png (uint8 mask)
    """
    n = C.SAR_SCENE_SIZE
    lats = np.linspace(C.BBOX[0], C.BBOX[2], n)
    lons = np.linspace(C.BBOX[1], C.BBOX[3], n)
    U10 = C.WIND_SPEED_MS
    sig0_vv = _apply_clutter_gradient(_sigma0_linear(U10, C.SAR_INCIDENCE_DEG), n, rng)
    sig0_vv *= _lookalike_zones(n, rng)
    sig0_vv = sig0_vv.astype(np.float32)

    mask = np.zeros((n, n), dtype=np.uint8)
    poly_px = []
    for lat, lon in slick_polygon:
        px = int((lon - C.BBOX[1]) / (C.BBOX[3] - C.BBOX[1]) * (n - 1))
        py = int((lat - C.BBOX[0]) / (C.BBOX[2] - C.BBOX[0]) * (n - 1))
        poly_px.append((px, py))
    if len(poly_px) >= 3:
        img_poly = Image.new("L", (n, n), 0)
        ImageDraw.Draw(img_poly).polygon(poly_px, fill=255)
        mask = np.array(img_poly)
        poly_mask = mask > 0
        # Thicker damping near the core, thinner at the smeared edges
        core = Image.new("L", (n, n), 0)
        ImageDraw.Draw(core).polygon(poly_px, outline=255, width=12)
        core_mask = np.array(core) > 0
        # Damping (linear attenuation of sigma0^0)
        damp = np.where(poly_mask,
                        np.where(core_mask, C.SLICK_DAMPING_MIN, C.SLICK_DAMPING_MAX),
                        1.0).astype(np.float32)
        sig0_vv *= damp

    vv_lin = _speckle(n, sig0_vv, C.SAR_NUM_LOOKS, rng)
    vh_lin = _speckle(n, sig0_vv * (10 ** (C.SAR_VH_OFFSET_DB / 10.0)), C.SAR_NUM_LOOKS, rng)
    ships_db = _ship_targets(n, rng)
    vv_db = 10 * np.log10(vv_lin + 1e-12) + ships_db
    vh_db = 10 * np.log10(vh_lin + 1e-12) + ships_db * 0.3
    # Mask out ships that fall inside the slick core (physics: ship is the source, not in slick)
    ships_mask = ships_db > (C.SHIP_PEAK_DB * 0.5)
    vv_db = np.where(ships_mask & ~poly_mask, vv_db, 10 * np.log10(vv_lin + 1e-12))
    vh_db = np.where(ships_mask & ~poly_mask, vh_db, 10 * np.log10(vh_lin + 1e-12))

    img = np.stack([vv_db.astype(np.float32), vh_db.astype(np.float32)], axis=-1)
    out_dir.mkdir(parents=True, exist_ok=True)
    tif_path = out_dir / "demo_scene.tif"
    tifffile.imwrite(tif_path, img, photometric="minisblack")
    mask_path = out_dir / "demo_scene_mask.png"
    Image.fromarray(mask).save(mask_path)
    return tif_path


def render_training_scenes(out_dir: Path, n_scenes: int, rng: np.random.Generator) -> dict:
    """Render `n_scenes` procedural oil/non-oil scenes for U-Net training.

    Folders:
      <out>/oil_spill/train/*.tif     + <out>/mask/train/*.tif
      <out>/train/no_oil/*.tif        + <out>/mask/*.tif
    Ratio of oil to non-oil is ~2:1 so the model sees negatives too.
    Returns a dict of counts for reporting.
    """
    n = C.SAR_SCENE_SIZE
    oil_dir = out_dir / "oil_spill" / "train"
    no_oil_dir = out_dir / "no_oil" / "train"
    mask_oil_dir = out_dir / "oil_spill_masks" / "train"
    mask_nooil_dir = out_dir / "no_oil_masks" / "train"
    for d in (oil_dir, no_oil_dir, mask_oil_dir, mask_nooil_dir):
        d.mkdir(parents=True, exist_ok=True)

    counts = {"oil": 0, "no_oil": 0}
    for i in range(n_scenes):
        is_no_oil = (i % 3) == 2
        base = _apply_clutter_gradient(_sigma0_linear(C.WIND_SPEED_MS, C.SAR_INCIDENCE_DEG), n, rng)
        base *= _lookalike_zones(n, rng)
        mask = np.zeros((n, n), dtype=np.uint8)
        if not is_no_oil:
            slick_mask = _slick_shape_mask(rng, n, i)
            core = Image.new("L", (n, n), 0)
            ImageDraw.Draw(core).polygon([(0, 0), (0, 0)], outline=0)  # anchor no-op
            damp = np.where(slick_mask, C.SLICK_DAMPING_MIN, 1.0).astype(np.float32)
            base *= damp
            mask[slick_mask] = 255
        vv_lin = _speckle(n, base.astype(np.float32), C.SAR_NUM_LOOKS, rng)
        vh_lscale = base * (10 ** (C.SAR_VH_OFFSET_DB / 10.0))
        vh_lin = _speckle(n, vh_lscale.astype(np.float32), C.SAR_NUM_LOOKS, rng)
        ships_db = _ship_targets(n, rng)
        ships_mask = ships_db > (C.SHIP_PEAK_DB * 0.5)
        vv_db = np.where(ships_mask, 10 * np.log10(vv_lin + 1e-12) + ships_db,
                         10 * np.log10(vv_lin + 1e-12))
        # note: for no_oil scenes, bright ships are still realistic clutter
        vv_db = 10 * np.log10(vv_lin + 1e-12)
        vh_db = 10 * np.log10(vh_lin + 1e-12)
        img = np.stack([vv_db.astype(np.float32), vh_db.astype(np.float32)], axis=-1)

        if is_no_oil:
            img_path = no_oil_dir / f"scene_{i:04d}.tif"
            mask_path = mask_nooil_dir / f"scene_{i:04d}.tif"
            counts["no_oil"] += 1
        else:
            img_path = oil_dir / f"scene_{i:04d}.tif"
            mask_path = mask_oil_dir / f"scene_{i:04d}.tif"
            counts["oil"] += 1
        tifffile.imwrite(img_path, img, photometric="minisblack")
        Image.fromarray(mask).save(mask_path)
    return counts
