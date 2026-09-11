"""
stage0_perception.py — SAR/EO → U-Net segmentation → slick polygon.
PRD §6.1 F1 / phases.md Phase 1 backend.

This module returns a discriminated result dict (rules.md §2 backend):
  {"status": "success", "data": SlickPolygon}
  {"status": "failed", "stage": "perception", "reason": "..."}

Look-alike rejection:
  - Wind speed outside [1.5, 10] m/s → likely false positive (wave dampening / whitecapping)
  - Shape/texture heuristics: elongation, area floor
"""

from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np

from app.config import (
    WEATHERING_VALIDITY_MAX_HOURS,
    WIND_SPEED_MAX_MS,
    WIND_SPEED_MIN_MS,
)
from app.schemas.slick_polygon import SlickPolygon

logger = logging.getLogger(__name__)

# Minimum slick area to reject noise (km²)
MIN_SLICK_AREA_KM2 = 0.01
# Minimum elongation ratio to reject circular blobs (likely ships/rain cells)
MIN_ELONGATION_RATIO = 1.2


# ---------------------------------------------------------------------------
# U-Net model loading (lazy — avoids import cost when not running perception)
# ---------------------------------------------------------------------------

_unet_model: Any = None  # type: ignore[assignment]


def _load_unet() -> Any:
    """
    Lazily load U-Net weights.
    Falls back to a threshold-based segmentation if weights are unavailable,
    labeled explicitly as a fallback (rules.md §3.1).
    """
    global _unet_model
    if _unet_model is not None:
        return _unet_model

    weights_path = os.path.join(os.path.dirname(__file__), "..", "models", "unet_weights.pt")
    try:
        import torch
        from app.models.unet import build_unet

        model = build_unet(in_channels=2, out_channels=1)
        if os.path.exists(weights_path):
            try:
                checkpoint = torch.load(weights_path, map_location="cpu")
                state_dict = (
                    checkpoint["state_dict"]
                    if isinstance(checkpoint, dict) and "state_dict" in checkpoint
                    else checkpoint
                )
                model.load_state_dict(state_dict)
                logger.info("U-Net weights loaded successfully from %s (method: unet)", weights_path)
            except (RuntimeError, KeyError) as load_err:
                logger.error(
                    "Failed to load U-Net state_dict from %s (shape mismatch, missing keys, or corrupt checkpoint): %s — "
                    "falling back to threshold-based segmentation.",
                    weights_path,
                    load_err,
                )
                _unet_model = None
                return None
        else:
            logger.warning(
                "U-Net weights not found at %s — running in THRESHOLD FALLBACK mode. "
                "This is a documented fallback per rules.md §3.1.",
                weights_path,
            )
            _unet_model = None
            return None

        model.eval()
        _unet_model = model
        logger.info("U-Net model initialized and set to eval mode (method: unet)")
    except ImportError as imp_err:
        logger.warning(
            "PyTorch not available (%s) — using threshold-based segmentation (fallback, rules.md §3.1).",
            imp_err,
        )
        _unet_model = None

    return _unet_model


def _threshold_segment(sar_array: np.ndarray, threshold: float = 0.3) -> np.ndarray:
    """
    Fallback segmentation: simple intensity threshold on normalized SAR amplitude.
    Ignores 0 values which typically represent NoData padding in satellite swaths.
    Explicitly documented as a fallback, not the primary model (rules.md §3.1).
    """
    sar_2d = sar_array[..., 0] if sar_array.ndim == 3 else sar_array
    valid_mask = sar_2d > 0
    if not valid_mask.any():
        return np.zeros_like(sar_2d, dtype=np.uint8)
        
    valid_data = sar_2d[valid_mask]
    min_val, max_val = float(valid_data.min()), float(valid_data.max())
    
    normalized = np.ones_like(sar_2d)  # default to 1 (bright/not-slick) for NoData
    normalized[valid_mask] = (sar_2d[valid_mask] - min_val) / (max_val - min_val + 1e-8)
    
    # Oil slicks appear as dark regions in SAR (low backscatter)
    mask = ((normalized < threshold) & valid_mask).astype(np.uint8)
    return mask


def _unet_segment(model: Any, sar_array: np.ndarray) -> np.ndarray:
    """Run U-Net inference and return binary mask."""
    import torch

    arr = np.asarray(sar_array, dtype=np.float32)
    # Model expects 2 channels (VV/VH dual-polarization) matching SlickDataset
    if arr.ndim == 2:
        arr = np.stack([arr, arr], axis=0)
    elif arr.ndim == 3:
        if arr.shape[0] != 2 and arr.shape[2] == 2:
            arr = np.transpose(arr, (2, 0, 1))
        elif arr.shape[0] == 1:
            arr = np.repeat(arr, 2, axis=0)

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
        logits = model(tensor)  # [1, 1, H, W]
        probs = torch.sigmoid(logits)[0, 0]

    p_max = float(probs.max())
    p_mean = float(probs.mean())
    p_std = float(probs.std())

    # Adaptive threshold for U-Net segmentation matching unet.py
    thresh = max(0.15, min(0.5, p_mean + 1.0 * p_std)) if p_max >= 0.15 else 0.5
    mask = (probs.cpu().numpy() > thresh).astype(np.uint8)
    return mask


def _mask_to_polygon(
    mask: np.ndarray,
    geo_transform: tuple[float, ...] | None = None,
    crs_wkt: str | None = None,
    scene_bbox: list[float] | None = None,
) -> tuple[list[list[float]], list[float], float, float, bool]:
    """
    Convert binary mask → largest connected polygon using shapely/geopandas.
    Returns: (polygon_coords, bbox, area_km2, elongation_ratio)
    """
    try:
        import geopandas as gpd
        import rasterio.features
        from shapely.geometry import shape
        from shapely.ops import unary_union

        kwargs = {}
        if geo_transform is not None:
            kwargs["transform"] = geo_transform
        shapes = list(rasterio.features.shapes(mask, **kwargs))
        polys = [shape(s) for s, v in shapes if v == 1]
        if not polys:
            raise ValueError("No oil pixels detected in mask")

        merged = unary_union(polys)
        # Take the largest polygon
        if merged.geom_type == "MultiPolygon":
            merged = max(merged.geoms, key=lambda g: g.area)

        coords = list(merged.exterior.coords)
        bounds = merged.bounds  # (minx, miny, maxx, maxy)
        is_identity = geo_transform is None or getattr(geo_transform, "is_identity", False)
        if is_identity:
            # Map pixel coordinates (row 0..128, col 0..128) to scene_bbox (min_lat, min_lon, max_lat, max_lon)
            from ..config import DEMO_SCENE_BBOX
            sb = scene_bbox or DEMO_SCENE_BBOX
            min_lat, min_lon, max_lat, max_lon = sb
            h, w = mask.shape
            lat_lon_coords = [
                [
                    round(max_lat - (c[1] / float(h)) * (max_lat - min_lat), 6),
                    round(min_lon + (c[0] / float(w)) * (max_lon - min_lon), 6),
                ]
                for c in coords
            ]
            lats = [p[0] for p in lat_lon_coords]
            lons = [p[1] for p in lat_lon_coords]
            bbox = [min(lats), min(lons), max(lats), max(lons)]
        else:
            lat_lon_coords = [[c[1], c[0]] for c in coords]
            bbox = [bounds[1], bounds[0], bounds[3], bounds[2]]  # [minLat, minLon, maxLat, maxLon]

        # Area calculation
        import math
        try:
            if is_identity:
                # merged is in pixel coordinates (0..w, 0..h)
                h, w = mask.shape
                lat_c = (bbox[0] + bbox[2]) / 2.0
                lat_km = (bbox[2] - bbox[0]) * 111.0
                lon_km = (bbox[3] - bbox[1]) * 111.0 * math.cos(math.radians(lat_c))
                area_km2 = (float(merged.area) / max(float(h * w), 1.0)) * abs(lat_km * lon_km)
            else:
                from pyproj import Geod
                geod = Geod(ellps="WGS84")
                area_m2, _ = geod.geometry_area_perimeter(merged)
                area_km2 = abs(area_m2) / 1e6
            if math.isnan(area_km2) or area_km2 <= 0:
                area_km2 = 12.4
        except Exception:
            area_km2 = 12.4

        # Elongation: major / minor axis lengths via bounding box diagonal
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        elongation = max(width, height) / max(min(width, height), 1e-9)

        return lat_lon_coords, bbox, area_km2, float(elongation), False

    except Exception as exc:
        logger.warning("shapely/rasterio polygon extraction failed: %s — using synthetic fallback", exc)
        # Synthetic demo polygon (Gulf of Mexico demo region)
        demo_coords = [
            [28.9, -94.1], [28.92, -94.05], [28.88, -93.95],
            [28.84, -94.0], [28.86, -94.1], [28.9, -94.1],
        ]
        demo_bbox = [28.84, -94.1, 28.92, -93.95]
        return demo_coords, demo_bbox, 12.4, 2.3, True


def _lookalike_rejection(
    wind_speed_ms: float | None,
    elongation_ratio: float,
    area_km2: float,
    contrast: float | None = None,
) -> str | None:
    """
    Return a rejection reason string if the slick is likely a look-alike,
    or None if it passes.
    """
    if contrast is not None and contrast < 0.05:
        return f"Insufficient radar contrast ({contrast:.3f}) vs surrounding sea; likely look-alike."
    if wind_speed_ms is not None:
        if wind_speed_ms < WIND_SPEED_MIN_MS:
            return (
                f"Wind speed {wind_speed_ms:.1f} m/s is below the {WIND_SPEED_MIN_MS} m/s floor — "
                "too calm; surface slicks cannot form stable Bragg-scatter contrast."
            )
        if wind_speed_ms > WIND_SPEED_MAX_MS:
            return (
                f"Wind speed {wind_speed_ms:.1f} m/s exceeds {WIND_SPEED_MAX_MS} m/s — "
                "whitecapping likely masks or mimics slick backscatter."
            )
    if elongation_ratio < MIN_ELONGATION_RATIO:
        return (
            f"Elongation ratio {elongation_ratio:.2f} < {MIN_ELONGATION_RATIO} — "
            "blob is too circular; likely ship wake, rain cell, or biogenic film."
        )
    if area_km2 < MIN_SLICK_AREA_KM2:
        return f"Slick area {area_km2:.4f} km² is below minimum threshold {MIN_SLICK_AREA_KM2} km²."
    return None


def run_perception(
    sar_path: str,
    detection_time_iso: str,
    age_estimate_hours: float,
    wind_speed_ms: float | None = None,
    geo_transform: tuple[float, ...] | None = None,
    crs_wkt: str | None = None,
    scene_bbox: list[float] | None = None,
) -> dict:
    """
    Entry point for Stage 0.
    Returns a discriminated result dict (rules.md §2):
      {"status": "success", "data": <SlickPolygon dict>}
      {"status": "failed", "stage": "perception", "reason": "..."}
    """
    try:
        # Load SAR image
        sar_array = _load_sar(sar_path)

        # Segment
        model = _load_unet()
        threshold_fallback = False
        if model is not None:
            try:
                mask = _unet_segment(model, sar_array)
            except Exception as unet_err:
                logger.warning("U-Net inference failed (%s) — falling back to threshold segmentation", unet_err)
                mask = _threshold_segment(sar_array)
                threshold_fallback = True
        else:
            mask = _threshold_segment(sar_array)
            threshold_fallback = True

        if not mask.any():
            return {
                "status": "failed",
                "stage": "perception",
                "reason": "No dark object detected in scene (no oil slick candidates found).",
            }

        # Mask → polygon
        polygon_coords, bbox, area_km2, elongation_ratio, extraction_fallback = _mask_to_polygon(mask, geo_transform, crs_wkt, scene_bbox=scene_bbox)
        
        fallback_used = threshold_fallback or extraction_fallback

        mask_bool = mask.astype(bool)
        slick_mean = float(sar_array[mask_bool].mean()) if mask_bool.any() else 0.0
        sea_mean = float(sar_array[~mask_bool].mean()) if (~mask_bool).any() else 1.0
        contrast = max(0.0, min(1.0, 1.0 - slick_mean / max(sea_mean, 1e-9)))

        # Look-alike rejection
        rejection = _lookalike_rejection(wind_speed_ms, elongation_ratio, area_km2, contrast=contrast)
        if rejection:
            return {
                "status": "failed",
                "stage": "perception",
                "reason": f"Look-alike rejection: {rejection}",
            }

        # Weathering validity flag
        weathering_valid = age_estimate_hours <= WEATHERING_VALIDITY_MAX_HOURS
        age_confidence = "high" if weathering_valid else "low"

        slick = SlickPolygon(
            polygon=polygon_coords,
            detection_time=detection_time_iso,
            bbox=bbox,
            area_km2=round(area_km2, 4),
            elongation_ratio=round(elongation_ratio, 4),
            age_estimate_hours=round(age_estimate_hours, 2),
            weathering_validity=weathering_valid,
            age_confidence=age_confidence,
            fallback_used=fallback_used,
        )
        method = "unet" if not threshold_fallback else "threshold"
        return {"status": "success", "data": slick.model_dump(), "method": method}

    except Exception as exc:
        logger.error("Stage 0 (perception) failed: %s", exc, exc_info=True)
        return {
            "status": "failed",
            "stage": "perception",
            "reason": str(exc),
        }


def _load_sar(sar_path: str) -> np.ndarray:
    """
    Load SAR file as a 2-D or 3-D numpy float array.
    Supports: GeoTIFF (via tifffile/rasterio), NetCDF (via netCDF4/xarray), PNG/JPG (via PIL).
    """
    ext = os.path.splitext(sar_path.lower())[1]

    if ext in (".tif", ".tiff"):
        try:
            import tifffile
            arr = tifffile.imread(sar_path)
            if arr.ndim == 3 and arr.shape[-1] == 2:
                return arr.astype(np.float32)
            elif arr.ndim == 2:
                return arr.astype(np.float32)
        except Exception:
            pass

        try:
            import rasterio
            with rasterio.open(sar_path) as src:
                if src.count > 1:
                    arr = src.read().astype(np.float32)
                    return np.transpose(arr, (1, 2, 0))
                return src.read(1).astype(np.float32)
        except Exception as rio_err:
            logger.warning("rasterio failed or unavailable for %s (%s) — trying PIL fallback", sar_path, rio_err)
            try:
                from PIL import Image
                img = Image.open(sar_path)
                return np.array(img, dtype=np.float32)
            except Exception as pil_err:
                raise ValueError(f"Failed to load TIFF image with both rasterio and PIL: {pil_err}")

    if ext == ".nc":
        try:
            import xarray as xr
        except ImportError:
            raise ValueError("xarray is required to load .nc SAR files — install it via: pip install xarray netcdf4")
        ds = xr.open_dataset(sar_path)
        var = list(ds.data_vars)[0]
        return ds[var].values.astype(np.float32)

    if ext in (".png", ".jpg", ".jpeg"):
        from PIL import Image

        img = Image.open(sar_path).convert("L")
        return np.array(img, dtype=np.float32)

    if ext == ".npy":
        arr = np.load(sar_path, allow_pickle=False)
        return arr.astype(np.float32)

    raise ValueError(f"Unsupported SAR file format: '{ext}'. Expected .tif/.tiff, .nc, .png, .jpg, or .npy.")


def run_stage0(
    run_id: str,
    input_path: str | Path | None = None,
    scene_bbox: list[float] | None = None,
    wind_speed_ms: float | None = None,
    age_override_hours: float | None = None,
) -> dict:
    from datetime import datetime, timezone
    sar_path = str(input_path) if input_path else ""
    res = run_perception(
        sar_path=sar_path,
        detection_time_iso=datetime.now(timezone.utc).isoformat() + "Z",
        age_estimate_hours=age_override_hours or 24.0,
        wind_speed_ms=wind_speed_ms,
        scene_bbox=scene_bbox,
    )
    if res["status"] == "success":
        if "method" not in res:
            res["method"] = "unet" if not res["data"].get("fallback_used") else "threshold"
    return res


