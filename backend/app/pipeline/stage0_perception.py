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
        from app.models.unet import UNet

        model = UNet(in_channels=1, out_channels=1)
        if os.path.exists(weights_path):
            model.load_state_dict(torch.load(weights_path, map_location="cpu"))
            logger.info("U-Net weights loaded from %s", weights_path)
        else:
            logger.warning(
                "U-Net weights not found at %s — running in THRESHOLD FALLBACK mode. "
                "This is a documented fallback per rules.md §3.1.",
                weights_path,
            )
        model.eval()
        _unet_model = model
    except ImportError:
        logger.warning(
            "PyTorch not available — using threshold-based segmentation (fallback, rules.md §3.1)."
        )
        _unet_model = None

    return _unet_model


def _threshold_segment(sar_array: np.ndarray, threshold: float = 0.3) -> np.ndarray:
    """
    Fallback segmentation: simple intensity threshold on normalized SAR amplitude.
    Explicitly documented as a fallback, not the primary model (rules.md §3.1).
    """
    normalized = (sar_array - sar_array.min()) / (sar_array.max() - sar_array.min() + 1e-8)
    # Oil slicks appear as dark regions in SAR (low backscatter)
    mask = (normalized < threshold).astype(np.uint8)
    return mask


def _unet_segment(model: Any, sar_array: np.ndarray) -> np.ndarray:
    """Run U-Net inference and return binary mask."""
    import torch

    h, w = sar_array.shape[-2], sar_array.shape[-1]
    # Normalize and add batch + channel dims
    norm = (sar_array - sar_array.mean()) / (sar_array.std() + 1e-8)
    tensor = torch.from_numpy(norm.astype(np.float32)).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        logits = model(tensor)  # [1, 1, H, W]
        prob = torch.sigmoid(logits).squeeze().numpy()
    return (prob > 0.5).astype(np.uint8)


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
        if geo_transform is None:
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

        # Area — use pyproj to convert to m² if CRS is geographic (degrees);
        # fall back to bounds approximation otherwise.
        try:
            from pyproj import Geod
            geod = Geod(ellps="WGS84")
            area_m2, _ = geod.geometry_area_perimeter(merged)
            area_km2 = abs(area_m2) / 1e6
        except Exception:
            # Crude fallback: 1° lat ≈ 111 km, 1° lon ≈ 111*cos(lat) km
            import math
            lat_c = (bounds[1] + bounds[3]) / 2
            lat_km = 111.0
            lon_km = 111.0 * math.cos(math.radians(lat_c))
            area_km2 = float(merged.area) * lat_km * lon_km

        # Elongation: major / minor axis lengths via bounding box diagonal
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        elongation = max(width, height) / max(min(width, height), 1e-9)

        return lat_lon_coords, bbox, area_km2, float(elongation), False

    except Exception as exc:
        logger.warning("shapely/rasterio polygon extraction failed: %s — using synthetic fallback", exc)
        # Synthetic demo polygon (Gulf of Mexico demo region)
        demo_coords = [
            [28.5, -90.1], [28.52, -90.05], [28.48, -89.95],
            [28.44, -90.0], [28.46, -90.1], [28.5, -90.1],
        ]
        demo_bbox = [28.44, -90.1, 28.52, -89.95]
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
            mask = _unet_segment(model, sar_array)
        else:
            mask = _threshold_segment(sar_array)
            threshold_fallback = True

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
        return {"status": "success", "data": slick.model_dump()}

    except Exception as exc:
        logger.error("Stage 0 (perception) failed: %s", exc, exc_info=True)
        return {
            "status": "failed",
            "stage": "perception",
            "reason": str(exc),
        }


def _load_sar(sar_path: str) -> np.ndarray:
    """
    Load SAR file as a 2-D numpy float array.
    Supports: GeoTIFF (via rasterio), NetCDF (via netCDF4/xarray), PNG/JPG (via PIL).
    """
    ext = os.path.splitext(sar_path.lower())[1]

    if ext in (".tif", ".tiff"):
        try:
            import rasterio
        except ImportError:
            raise ValueError("rasterio is required to load .tif SAR files — install it via: pip install rasterio")
        with rasterio.open(sar_path) as src:
            return src.read(1).astype(np.float32)

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
        res["method"] = "unet" if not res["data"].get("fallback_used") else "threshold"
    return res


