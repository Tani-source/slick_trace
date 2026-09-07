"""Anomaly scoring weights — hand-tuned stand-in for a future learned model.

These constants implement PRD F4's weighted-sum AnomalyScore. They are
explicitly rule-based for this build and must be presented as such in the
dashboard (rules.md §3.6); replace with logistic-regression/GBM coefficients
once labeled incident data exists (PRD §6.1 F4, §9).
"""

from __future__ import annotations

BLACKOUT_WEIGHT = 0.40
SPEED_WEIGHT = 0.25
ROUTE_WEIGHT = 0.20
DRAFT_WEIGHT = 0.15

ANOMALY_WEIGHTS = {
    "blackout": BLACKOUT_WEIGHT,
    "speed": SPEED_WEIGHT,
    "route": ROUTE_WEIGHT,
    "draft": DRAFT_WEIGHT,
}

assert abs(sum(ANOMALY_WEIGHTS.values()) - 1.0) < 1e-9


def run_anomaly_scoring(candidates: list[dict], top_n: int = 10) -> dict:
    scored = []
    for c in candidates:
        cand = dict(c)
        ab = cand.get("anomaly_breakdown", {})
        blackout = float(ab.get("blackout", ab.get("gap", 0.0)))
        speed = float(ab.get("speed", 0.0))
        route = float(ab.get("route", 0.0))
        draft = float(ab.get("draft", 0.0))
        score = (
            blackout * BLACKOUT_WEIGHT +
            speed * SPEED_WEIGHT +
            route * ROUTE_WEIGHT +
            draft * DRAFT_WEIGHT
        )
        cand["anomaly_score"] = round(score, 4)
        scored.append(cand)
    scored.sort(key=lambda c: c["anomaly_score"], reverse=True)
    return {"status": "success", "data": {"candidates": scored[:top_n]}}