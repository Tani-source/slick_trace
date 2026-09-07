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