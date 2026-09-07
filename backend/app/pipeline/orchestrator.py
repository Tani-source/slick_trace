"""
orchestrator.py — Sequences pipeline stages and updates run status.
All stage errors are caught here, halt downstream stages, and update pipeline_status.json.
(rules.md §2 backend enforcement)
"""

import logging
from pathlib import Path

from app.services.run_store import update_stage, write_run_artifact, read_run_artifact, upload_path
from app.config import UPLOADS_DIR

logger = logging.getLogger(__name__)


def _fail(run_id: str, stage_name: str, reason: str) -> None:
    """Mark a stage failed and log it."""
    logger.error("Stage '%s' failed for run %s: %s", stage_name, run_id, reason)
    update_stage(run_id, stage_name, "failed", 0, reason)


def _find_upload(run_id: str, dataset_type: str) -> str | None:
    """Locate the uploaded file for a given dataset type."""
    p = upload_path(run_id, dataset_type)
    if p and p.exists():
        return str(p)
    return None


def run_stages_0_to_4(run_id: str) -> None:
    """
    Background task: run Stages 0–4 in sequence.
    Each stage failure halts downstream — no garbage propagation (rules.md §2).
    """
    import traceback
    current_stage = "perception"
    try:
        import datetime

        # ── Stage 0: Perception ──────────────────────────────────────────────────
        update_stage(run_id, "perception", "running", 0, "Loading SAR image…")

        sar_path = _find_upload(run_id, "sar")
        if sar_path is None:
            _fail(run_id, "perception", "SAR file not uploaded for this run.")
            return

        from app.pipeline.stage0_perception import run_perception

        update_stage(run_id, "perception", "running", 20, "Running segmentation…")

        # Read geo_transform + CRS from the uploaded file if it's a GeoTIFF,
        # so the slick polygon is produced in real geographic coordinates.
        geo_transform = None
        crs_wkt = None
        try:
            import rasterio as _rio
            with _rio.open(sar_path) as _src:
                geo_transform = _src.transform
                crs_wkt = _src.crs.to_wkt() if _src.crs else None
        except Exception as _e:
            logger.warning("Could not read geo_transform from SAR file: %s", _e)

        # Parse detection time from scenario.json if present alongside dataset, or fixed benchmark timestamp
        scenario_path = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "scenario.json"
        detection_time = "2024-09-14T18:00:00Z"
        if scenario_path.exists():
            try:
                import json as _json
                sc_data = _json.loads(scenario_path.read_text(encoding="utf-8"))
                detection_time = sc_data.get("detection_time", detection_time)
            except Exception:
                pass

        result = run_perception(
            sar_path=sar_path,
            detection_time_iso=detection_time,
            age_estimate_hours=12.0,
            wind_speed_ms=None,       # TODO: read from wind upload in Phase 1 hardening
            geo_transform=geo_transform,
            crs_wkt=crs_wkt,
        )


        if result["status"] == "failed":
            _fail(run_id, "perception", result["reason"])
            return

        write_run_artifact(run_id, "slick_polygon", result["data"])
        update_stage(run_id, "perception", "done", 100, f"Slick area: {result['data']['area_km2']:.2f} km²")

        # ── Stage 1: Backward Drift ──────────────────────────────────────────────
        current_stage = "backward_drift"
        from app.pipeline.stage1_backward_drift import run_backward_drift
        
        update_stage(run_id, "backward_drift", "running", 0, "Seeding particles…")
        
        # Needs slick polygon
        slick_data = result["data"]
        
        update_stage(run_id, "backward_drift", "running", 30, "Running reversed advection…")
        stage1_res = run_backward_drift(
            slick_polygon=slick_data["polygon"],
            age_hours=slick_data["age_estimate_hours"],
            detection_time_iso=slick_data.get("detection_time", datetime.datetime.utcnow().isoformat() + "Z"),
            current_path=_find_upload(run_id, "current"),
            wind_path=_find_upload(run_id, "wind")
        )
        
        if stage1_res["status"] == "failed":
            _fail(run_id, "backward_drift", stage1_res["reason"])
            return
            
        write_run_artifact(run_id, "origin_envelope", stage1_res["data"])
        update_stage(run_id, "backward_drift", "done", 100, f"Origin window: {stage1_res['data']['time_window_hours']:.1f}h")

        # ── Stage 2/3: AIS Ingestion & Filtering ─────────────────────────────────
        current_stage = "ais_ingestion"
        from app.services.ais_loader import load_and_filter as run_filter
        
        update_stage(run_id, "ais_ingestion", "running", 0, "Loading AIS data…")
        ais_path = _find_upload(run_id, "ais")
        
        stage2_res = run_filter(
            csv_path=ais_path,
            bbox=stage1_res["data"]["bbox"],
            start_time=datetime.datetime.fromisoformat(stage1_res["data"]["start_time"]),
            end_time=datetime.datetime.fromisoformat(stage1_res["data"]["end_time"]),
        )
        
        if stage2_res["status"] == "failed":
            _fail(run_id, "ais_ingestion", stage2_res.get("reason", "AIS ingestion failed"))
            return
            
        cands = stage2_res["data"]
        update_stage(run_id, "ais_ingestion", "done", 100, "Loaded AIS records")
        
        current_stage = "candidate_filtering"
        update_stage(run_id, "candidate_filtering", "running", 0, "Filtering by vessel type…")
        
        # Store intermediate candidates before scoring (if we want, or just pass them along)
        update_stage(run_id, "candidate_filtering", "done", 100, f"Found {len(cands)} candidates")

        # ── Stage 4: Anomaly Scoring ─────────────────────────────────────────────
        current_stage = "anomaly_scoring"
        from app.models.anomaly_weights import run_anomaly_scoring
        from app.config import TOP_N_SHORTLIST
        
        update_stage(run_id, "anomaly_scoring", "running", 0, f"Scoring {len(cands)} candidates…")
        
        stage4_res = run_anomaly_scoring(cands, top_n=TOP_N_SHORTLIST)
        
        if stage4_res["status"] == "failed":
            _fail(run_id, "anomaly_scoring", stage4_res["reason"])
            return
            
        final_cands = stage4_res["data"]["candidates"]
        
        # The frontend expects { "candidates": [...] } in shortlist.json
        write_run_artifact(run_id, "shortlist", {"candidates": final_cands})
        
        update_stage(run_id, "anomaly_scoring", "done", 100, f"Top {len(final_cands)} shortlisted")

    except Exception as e:
        logger.error(f"Unhandled exception in stage {current_stage}: {str(e)}", exc_info=True)
        _fail(run_id, current_stage, f"Internal error: {str(e)}")


def run_stages_5_to_6(run_id: str) -> None:
    """
    Background task: run Stages 5–6.
    ONLY called on the top-N shortlist (rules.md §3.8) — structurally enforced:
    this function reads shortlist.json and refuses to proceed if it's absent.
    """
    import traceback
    current_stage = "drift_simulation"
    try:
        shortlist = read_run_artifact(run_id, "shortlist")
        if shortlist is None or not shortlist.get("candidates"):
            _fail(run_id, "drift_simulation", "Shortlist is empty or missing — cannot run Stage 5.")
            return

        update_stage(run_id, "drift_simulation", "running", 0, "Starting forward drift simulation…")
        
        # Stage 5
        from app.pipeline.stage5_forward_drift import run_forward_simulation
        slick = read_run_artifact(run_id, "slick_polygon")
        target_time_iso = slick.get("detection_time")
        
        stage5_res = run_forward_simulation(
            shortlist_candidates=shortlist["candidates"], 
            target_time_iso=target_time_iso,
            current_path=_find_upload(run_id, "current"),
            wind_path=_find_upload(run_id, "wind")
        )
        if stage5_res["status"] == "failed":
            _fail(run_id, "drift_simulation", stage5_res["reason"])
            return
            
        simulations = stage5_res["data"]["simulations"]
        # Write intermediate output so frontend map can render footprints
        write_run_artifact(run_id, "simulated_footprints", {"simulations": simulations})
        
        update_stage(run_id, "drift_simulation", "done", 100, f"Simulated {len(simulations)} tracks")
        
        # Stage 6
        current_stage = "verification_matching"
        update_stage(run_id, "verification_matching", "running", 0, "Matching footprints…")
        
        from app.pipeline.stage6_matching import run_matching
        stage6_res = run_matching(simulations, slick["polygon"])
        
        if stage6_res["status"] == "failed":
            _fail(run_id, "verification_matching", stage6_res["reason"])
            return
            
        ranked_suspects = stage6_res["data"]["ranking"]
        write_run_artifact(run_id, "ranked_suspects", {"ranking": ranked_suspects})
        
        update_stage(run_id, "verification_matching", "done", 100, "Ranking complete")

    except Exception as e:
        logger.error(f"Unhandled exception in stage {current_stage}: {str(e)}", exc_info=True)
        _fail(run_id, current_stage, f"Internal error: {str(e)}")


# Aliases for API compatibility
run_pipeline = run_stages_0_to_4
simulate_pipeline = run_stages_5_to_6
