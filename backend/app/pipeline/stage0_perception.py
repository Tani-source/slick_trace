from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..config import (
    AGE_WEATHERING_LIMIT_HOURS,
    DEMO_PIXEL_SIZE_DEG,
    DEMO_SCENE_BBOX,
    UNET_WEIGHTS_PATH,
    WIND_VALID_RANGE_M_S,
)
from ..models.unet import unet_inference
from ..schemas.slick_polygon import SlickPolygon
from ..services import run_store

MIN_SLICK_PIXELS = 25
COARSEN_TARGET = 40_000


def _load_raster(input_path: Path) -> tuple[np.ndarray, np.ndarray]:
    suffix = input_path.suffix.lower()
    if suffix == ".npy":
        raw = np.load(input_path, allow_pickle=False)
        arr = np.asarray(raw, dtype=np.float32)
    elif suffix in (".tif", ".tiff"):
        try:
            import tifffile
            arr = tifffile.imread(input_path).astype(np.float32)
        except Exception:
            from PIL import Image
            with Image.open(input_path) as image:
                arr = np.asarray(image, dtype=np.float32)
    else:
        from PIL import Image
        with Image.open(input_path) as image:
            arr = np.asarray(image, dtype=np.float32)
    if arr.size == 0:
        raise ValueError("file empty")
    raw = arr.astype(np.float32, copy=True)
    lo, hi = float(arr.min()), float(arr.max())
    normalized = np.zeros_like(arr)
    if hi - lo > 1e-9:
        normalized = (arr - lo) / (hi - lo)
    return raw, normalized


def _segment(normalized: np.ndarray) -> tuple[np.ndarray, str]:
    if UNET_WEIGHTS_PATH:
        mask = unet_inference(normalized, UNET_WEIGHTS_PATH)
        return np.asarray(mask, dtype=bool), "unet"
    threshold = min(float(np.mean(normalized) - 1.5 * float(np.std(normalized)), ), float(np.quantile(normalized, 0.2)))
    return normalized < threshold, "threshold"


def _largest_component(mask: np.ndarray) -> np.ndarray:
    from scipy.ndimage import binary_fill_holes, label

    labels, _ = label(mask)
    if labels.max() == 0:
        return np.zeros_like(mask, dtype=bool)
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    biggest = int(counts.argmax())
    return binary_fill_holes(labels == biggest)


def _coarsen(mask: np.ndarray) -> np.ndarray:
    from scipy.ndimage import maximum_filter

    factor = 1
    while int(mask[::factor, ::factor].sum()) > COARSEN_TARGET and factor * 2 < min(mask.shape):
        factor += 1
    if factor == 1:
        return mask
    return maximum_filter(mask, size=factor)[::factor, ::factor].astype(bool)


def _mask_to_polygon(mask: np.ndarray, min_lon: float, max_lat: float, px_lon: float, px_lat: float) -> list[list[float]]:
    import shapely
    import shapely.ops as sops
    from shapely.geometry import box as shapely_box

    rows, cols = np.nonzero(_coarsen(mask))
    union = sops.unary_union([shapely_box(int(c), int(r), int(c) + 1, int(r) + 1) for r, c in zip(rows, cols)])
    if union.is_empty:
        return []
    if union.geom_type == "MultiPolygon":
        union = max(union.geoms, key=lambda g: g.area)
    simplified = union.simplify(0.5, preserve_topology=False)
    ring = simplified.exterior
    coords = [[max_lat - float(y) * px_lat, min_lon + float(x) * px_lon] for x, y in ring.coords]
    return [[round(lat, 6), round(lon, 6)] for lat, lon in coords]


def _elongation(mask: np.ndarray) -> float:
    rows, cols = np.nonzero(mask)
    if rows.size < 2:
        return 1.0
    points = np.column_stack([rows, cols]).astype(np.float64)
    centered = points - points.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues = np.linalg.eigvalsh(cov)
    major, minor = float(max(eigenvalues)), float(min(eigenvalues))
    if minor < 1e-9 or major <= 0:
        return 1.0
    return float(np.sqrt(major / minor))


def _area_km2(mask: np.ndarray, lat_center: float, px_lon_deg: float, px_lat_deg: float) -> float:
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * float(np.cos(np.deg2rad(lat_center)))
    return float(mask.sum()) * (px_lat_deg * km_per_deg_lat) * (px_lon_deg * km_per_deg_lon)


def _heap_estimate(raw: np.ndarray, mask: np.ndarray) -> tuple[float, float]:
    slick = raw[mask]
    sea = raw[~mask]
    slick_mean = float(slick.mean()) if slick.size else 0.0
    sea_mean = float(sea.mean()) if sea.size else 1.0
    contrast = max(0.0, min(1.0, 1.0 - slick_mean / max(sea_mean, 1e-9)))
    area_frac = float(mask.sum()) / float(raw.size)
    age_hours = 12.0 * (1.0 - contrast) + 4.0 * float(np.sqrt(area_frac))
    confidence = "high" if contrast >= 0.6 else "low"
    return round(age_hours, 1), confidence


def _assess_look_alike(wind_speed_ms: float | None, area_frac: float, contrast: float) -> dict:
    rejections: list[str] = []
    notes: list[str] = []
    if wind_speed_ms is None:
        notes.append("wind speed unknown; look-alike rejection not assessable")
    elif not (WIND_VALID_RANGE_M_S[0] <= wind_speed_ms <= WIND_VALID_RANGE_M_S[1]):
        rejections.append(
            f"wind speed {wind_speed_ms} m/s outside {WIND_VALID_RANGE_M_S[0]}-{WIND_VALID_RANGE_M_S[1]} m/s "
            "valid detection window (look-alike risk too high to attribute)"
        )
    if area_frac < 1e-4:
        rejections.append(f"dark object too small ({area_frac:.2e} of scene) for confident attribution")
    if contrast < 0.05:
        rejections.append(f"insufficient radar contrast vs surrounding sea ({contrast:.3f}); likely look-alike")
    return {"rejected": bool(rejections), "rejections": rejections, "notes": notes}


def run_stage0(
    run_id: str,
    input_path: Path | None = None,
    scene_bbox: list[float] | None = None,
    wind_speed_ms: float | None = None,
    age_override_hours: float | None = None,
) -> dict:
    """Run Stage 0 perception: SAR crop -> binary mask -> polygon + descriptors.

    Honesty note (rules.md §3.1): when no trained U-Net weights are configured
    this uses a clearly-documented threshold-based segmentation fallback. The
    chosen method is returned in the result so the UI can label provenance.
    """
    try:
        scene = scene_bbox or DEMO_SCENE_BBOX
        if len(scene) != 4:
            return {"status": "failed", "stage": "perception", "reason": "scene bounds not recognized"}
        min_lat, min_lon, max_lat, max_lon = scene

        if input_path is None:
            uploaded = run_store.uploaded_file(run_id, "sar")
            if uploaded is None:
                return {"status": "failed", "stage": "perception", "reason": "no SAR dataset uploaded"}
            input_path = uploaded

        raw, normalized = _load_raster(input_path)
        mask, method = _segment(normalized)

        component = _largest_component(mask)
        if int(component.sum()) < MIN_SLICK_PIXELS or int(component.sum()) == 0:
            return {
                "status": "failed",
                "stage": "perception",
                "reason": "no slick-like dark object detected in scene",
            }

        rows, cols = component.shape
        px_lat_deg = (max_lat - min_lat) / rows
        px_lon_deg = (max_lon - min_lon) / cols
        lat_center = (min_lat + max_lat) / 2.0

        polygon = _mask_to_polygon(component, min_lon, max_lat, px_lon_deg, px_lat_deg)
        if len(polygon) < 4:
            return {"status": "failed", "stage": "perception", "reason": "detected object too small to polygonize"}

        area_km2 = _area_km2(component, lat_center, px_lon_deg, px_lat_deg)
        elongation_ratio = round(_elongation(component), 3)

        age_hours, age_confidence = _heap_estimate(raw, component)
        if age_override_hours is not None:
            age_hours = float(age_override_hours)
            age_confidence = "high" if age_hours <= AGE_WEATHERING_LIMIT_HOURS else "low"
        weathering_validity = age_hours <= AGE_WEATHERING_LIMIT_HOURS

        slick_mean = float(raw[component].mean())
        sea_mean = float(raw[~component].mean()) if raw[~component].size else 1.0
        contrast = max(0.0, min(1.0, 1.0 - slick_mean / max(sea_mean, 1e-9)))
        area_frac = float(component.sum()) / float(raw.size)
        look_alike = _assess_look_alike(wind_speed_ms, area_frac, contrast)

        if wind_speed_ms is None and run_id and run_store.run_exists(run_id):
            dataset = run_store.get_dataset(run_id, "sar") or {}
            supplied = dataset.get("wind_speed_ms")
            if supplied is not None:
                look_alike = _assess_look_alike(float(supplied), area_frac, contrast)

        if look_alike["rejected"]:
            return {
                "status": "failed",
                "stage": "perception",
                "reason": "; ".join(look_alike["rejections"]),
            }

        bbox = [
            round(min(p[0] for p in polygon), 6),
            round(min(p[1] for p in polygon), 6),
            round(max(p[0] for p in polygon), 6),
            round(max(p[1] for p in polygon), 6),
        ]

        data = SlickPolygon(
            polygon=polygon,
            detection_time=datetime.now(timezone.utc),
            bbox=bbox,
            area_km2=round(area_km2, 4),
            elongation_ratio=elongation_ratio,
            age_estimate_hours=round(age_hours, 2),
            weathering_validity=bool(weathering_validity),
            age_confidence=age_confidence,
        )
        return {
            "status": "success",
            "data": data.model_dump(mode="json"),
            "method": method,
            "look_alike": look_alike,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "stage": "perception", "reason": str(exc)}