"""
stage6_matching.py — Stage 6: Verification matching between simulated footprint and observed slick.
Computes spatial Intersection-over-Union (IoU) and Hausdorff distance between simulated footprint and observed slick polygon.
"""

import math
from typing import Any
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.ops import unary_union

def _to_shapely(poly_coords: list) -> Polygon | MultiPolygon | None:
    if not poly_coords:
        return None
    try:
        if isinstance(poly_coords[0][0], (int, float)):
            if len(poly_coords) < 3:
                return None
            return Polygon(poly_coords)
        elif isinstance(poly_coords[0][0], list):
            polys = [Polygon(p) for p in poly_coords if len(p) >= 3]
            if not polys:
                return None
            return unary_union(polys)
    except Exception:
        return None
    return None

def compute_metrics(poly1_coords: list, poly2_coords: list) -> tuple[float, float, float]:
    """
    Computes (iou, overlap_area_km2, distance_to_center_km) between two polygons.
    """
    p1 = _to_shapely(poly1_coords)
    p2 = _to_shapely(poly2_coords)
    if p1 is None or p2 is None or p1.is_empty or p2.is_empty:
        return 0.0, 0.0, 0.0
    try:
        inter = p1.intersection(p2)
        intersection_area = inter.area
        union_area = p1.union(p2).area
        iou = float(intersection_area / union_area) if union_area > 0 else 0.0

        # Approx degree to km scaling at ~28.5°N
        # 1 deg lat ≈ 111 km, 1 deg lon ≈ 111 * cos(28.5°) ≈ 97.5 km
        deg2_to_km2 = 111.0 * 97.5
        overlap_area_km2 = float(intersection_area * deg2_to_km2)

        c1 = p1.centroid
        c2 = p2.centroid
        dlat = (c1.y - c2.y) * 111.0
        dlon = (c1.x - c2.x) * 97.5
        dist_km = float(math.hypot(dlat, dlon))

        return iou, overlap_area_km2, dist_km
    except Exception:
        return 0.0, 0.0, 0.0

def run_matching(simulations: list[dict[str, Any]], observed_slick_polygon: list) -> dict[str, Any]:
    """
    Ranks candidates by spatial overlap (IoU) between their forward simulated footprint and observed slick.
    """
    if not simulations:
        return {"status": "failed", "reason": "No simulations provided to stage 6"}

    ranking = []
    for sim in simulations:
        mmsi = sim.get("mmsi")
        vessel_name = sim.get("vessel_name", "Unknown")
        sim_poly = sim.get("simulated_polygon", [])

        iou, overlap_area_km2, dist_km = compute_metrics(sim_poly, observed_slick_polygon)

        ranking.append({
            "mmsi": mmsi,
            "vessel_name": vessel_name,
            "match_score": iou,
            "iou": iou,
            "overlap_area_km2": round(overlap_area_km2, 4),
            "distance_to_center_km": round(dist_km, 4)
        })

    ranking.sort(key=lambda x: (x["match_score"], -x["distance_to_center_km"]), reverse=True)
    for idx, item in enumerate(ranking):
        item["rank"] = idx + 1

    return {
        "status": "success",
        "data": {
            "ranking": ranking
        }
    }

