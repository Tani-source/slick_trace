"""Shared configuration for the synthetic data generator.

All physical constants, region geometry, timestamps, and output paths are
defined here. Every other module imports from this file so the four datasets
(AIS, forcing, SAR, scenario) are guaranteed to be internally consistent.

Convention: lat/lon are always (latitude, longitude) in degrees, positive
north/east. Velocities are eastward-positive (u) and northward-positive (v)
in m/s. Times are naive UTC strings; convert with
``datetime.fromisoformat(t).replace(tzinfo=timezone.utc)`` before use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Region geometry (Gulf of Mexico, offshore Louisiana)
# ---------------------------------------------------------------------------

# Bounding box: [min_lat, min_lon, max_lat, max_lon]
BBOX: list[float] = [28.50, -90.00, 29.00, -89.00]
REGION_NAME: str = "gulf_of_mexico_louisiana_offshore"

# Grid resolution in degrees (0.02 ≈ 2.2 km at this latitude)
GRID_RES_DEG: float = 0.02

# Forcing time window (72 hours, 1-hour steps)
FORCING_START: str = "2024-09-13T00:00:00"
FORCING_END: str = "2024-09-16T00:00:00"
TIME_STEP_HOURS: float = 1.0

# ---------------------------------------------------------------------------
# Slick / spill scenario (the ground truth that ties everything together)
# ---------------------------------------------------------------------------

# Culprit vessel identity
CULPRIT_MMSI: str = "538009972"
CULPRIT_NAME: str = "PACIFIC TRADER"
CULPRIT_IMO: str = "9876543"
CULPRIT_CALLSIGN: str = "V7RF2"
CULPRIT_FLAG: str = "MH"  # Marshall Islands
CULPRIT_TYPE: int = 80  # tanker (AIS type 80)
CULPRIT_LENGTH: int = 183  # metres
CULPRIT_WIDTH: int = 32
CULPRIT_DRAFT: float = 12.0  # metres (laden)

# Origin (release) point — where the illegal discharge occurs
ORIGIN_LAT: float = 28.80
ORIGIN_LON: float = -89.62

# Times
RELEASE_TIME: str = "2024-09-14T06:00:00"
DETECTION_TIME: str = "2024-09-14T18:00:00"
SLICK_AGE_HOURS: float = 12.0

# Particle advection
NUM_PARTICLES: int = 900
PARTICLE_SEED_RADIUS_M: float = 900.0
WIND_DRAG_FACTOR: float = 0.03  # 3% of 10 m wind (standard for oil)
ADVECTION_DT_S: float = 600.0  # 10-minute sub-steps

# Horizontal turbulent diffusion (Fay-type spreading proxy)
DIFFUSION_K_M2_PER_S: float = 8.0  # m²/s (open-ocean turbulence)

# ---------------------------------------------------------------------------
# Ocean currents (background + mesoscale eddy + tidal)
# ---------------------------------------------------------------------------

# Background flow (Louisiana–Texas shelf current, westward)
CURRENT_U_BG: float = -0.12  # m/s eastward
CURRENT_V_BG: float = -0.02  # m/s northward

# Mesoscale eddy (anticyclonic, warm-core ring from Loop Current)
EDDY_CENTER_LAT: float = 28.75
EDDY_CENTER_LON: float = -89.50
EDDY_RADIUS_DEG: float = 0.22  # ≈ 24 km
EDDY_MAX_VEL: float = 0.18  # m/s tangential at radius R

# Tidal (M2 semidiurnal)
TIDAL_PERIOD_H: float = 12.42
TIDAL_AMP_U: float = 0.025
TIDAL_AMP_V: float = 0.015

# ---------------------------------------------------------------------------
# Wind field (synoptic + diurnal cycle)
# ---------------------------------------------------------------------------

# Mean wind: from 150° (SSE) at 5.5 m/s → blows toward 330° (NNW)
WIND_FROM_DEG: float = 150.0
WIND_SPEED_MS: float = 5.5

# Diurnal amplitude (afternoon peak at ~15:00 local)
WIND_DIURNAL_AMP: float = 1.0  # m/s

# Spatial gradient (gentle N–S increase)
WIND_GRAD_PER_DEG_LAT: float = 0.3  # m/s per degree latitude

# ---------------------------------------------------------------------------
# SAR scene rendering
# ---------------------------------------------------------------------------

SAR_SCENE_SIZE: int = 512  # pixels per side
SAR_PIXEL_SIZE_M: float = 50.0  # metres per pixel → footprint ≈ 25.6 km
SAR_INCIDENCE_DEG: float = 35.0  # mid-swath Sentinel-1

# Backscatter model: σ⁰_VV(dB) = BASELINE + ALPHA×log10(U10) + GAMMA×log10(sin θ)
SAR_BASELINE_DB: float = -20.0
SAR_ALPHA: float = 12.0  # wind speed sensitivity
SAR_GAMMA: float = 20.0  # incidence-angle sensitivity

# VH offset from VV (cross-pol)
SAR_VH_OFFSET_DB: float = -18.5

# Speckle: number of looks
SAR_NUM_LOOKS: int = 4

# Slick damping: fractional reduction of σ⁰ linear (0.15 → 8.2 dB reduction)
SLICK_DAMPING_MIN: float = 0.15  # thick crude
SLICK_DAMPING_MAX: float = 0.40  # thin / biogenic

# Ship target: dB above local background
SHIP_PEAK_DB: float = 30.0
SHIP_PSF_RADIUS_PX: int = 3

# ---------------------------------------------------------------------------
# AIS vessel fleet
# ---------------------------------------------------------------------------

# Vessel names and types (realistic Gulf of Mexico traffic)
FLEET_SPEC: list[dict] = [
    # Tankers
    {"name": "PACIFIC TRADER", "type": 80, "draft": 12.0, "length": 183, "width": 32, "speed_kn": 12.5, "role": "culprit"},
    {"name": "ATLANTIC VOYAGER", "type": 80, "draft": 11.5, "length": 175, "width": 28, "speed_kn": 13.0, "role": "suspect"},
    {"name": "GULF HORIZON", "type": 80, "draft": 10.0, "length": 155, "width": 25, "speed_kn": 11.5, "role": "innocent"},
    {"name": "NORTHERN SPIRIT", "type": 80, "draft": 9.5, "length": 140, "width": 22, "speed_kn": 12.0, "role": "innocent"},
    {"name": "SOUTHERN STAR", "type": 81, "draft": 11.0, "length": 170, "width": 30, "speed_kn": 11.0, "role": "innocent"},
    # Cargo / bulk
    {"name": "EVERGREEN WAVE", "type": 70, "draft": 8.5, "length": 160, "width": 25, "speed_kn": 14.0, "role": "innocent"},
    {"name": "COSCO FORTUNE", "type": 70, "draft": 9.0, "length": 180, "width": 28, "speed_kn": 13.5, "role": "innocent"},
    {"name": "MAERSK SELETAR", "type": 70, "draft": 7.5, "length": 130, "width": 21, "speed_kn": 14.5, "role": "innocent"},
    {"name": "YANG MING UNITED", "type": 71, "draft": 8.0, "length": 145, "width": 23, "speed_kn": 13.0, "role": "innocent"},
    {"name": "ONE INNOVATION", "type": 70, "draft": 7.0, "length": 120, "width": 20, "speed_kn": 15.0, "role": "innocent"},
    {"name": "PIL PHILIPPINES", "type": 72, "draft": 6.5, "length": 110, "width": 18, "speed_kn": 12.5, "role": "innocent"},
    # Supply / tug
    {"name": "SEACOR WARRIOR", "type": 52, "draft": 4.5, "length": 65, "width": 14, "speed_kn": 10.0, "role": "innocent"},
    {"name": "BOIS BLOUIN", "type": 52, "draft": 4.0, "length": 55, "width": 12, "speed_kn": 9.5, "role": "innocent"},
    {"name": "GULF TUG 12", "type": 52, "draft": 3.5, "length": 35, "width": 10, "speed_kn": 8.0, "role": "innocent"},
    # Fishing
    {"name": "LOUISIANA REEL", "type": 30, "draft": 3.0, "length": 25, "width": 8, "speed_kn": 6.0, "role": "innocent"},
    {"name": "DELTA CATCH", "type": 30, "draft": 2.8, "length": 22, "width": 7, "speed_kn": 5.5, "role": "innocent"},
    {"name": "BAYOU FISHER", "type": 35, "draft": 2.5, "length": 18, "width": 6, "speed_kn": 5.0, "role": "innocent"},
    # Passenger / other
    {"name": "CARNIVAL SPIRIT", "type": 60, "draft": 8.0, "length": 290, "width": 36, "speed_kn": 18.0, "role": "innocent"},
    {"name": "USCG RESCUE 4412", "type": 51, "draft": 2.0, "length": 27, "width": 6, "speed_kn": 20.0, "role": "innocent"},
]

# MMSI range for generated vessels (vessel 0 is the culprit)
MMSI_BASE: int = 538009972

# AIS reporting interval (seconds) — realistic for different speeds
AIS_INTERVAL_S: int = 120  # 2-minute pings

# Culprit blackout window (hours before/after release)
CULPRIT_BLACKOUT_BEFORE_H: float = 2.0
CULPRIT_BLACKOUT_AFTER_H: float = 3.0

# ---------------------------------------------------------------------------
# Output paths (relative to backend/)
# ---------------------------------------------------------------------------

OUTPUT_DIR_NAME: str = "data/synthetic"

TRAIN_RATIO: float = 0.8  # 80% train, 20% test


@dataclass
class ScenarioMeta:
    """Consistent ground-truth metadata for the synthetic scenario."""

    region_name: str = REGION_NAME
    bbox: list[float] = field(default_factory=lambda: list(BBOX))
    origin_lat: float = ORIGIN_LAT
    origin_lon: float = ORIGIN_LON
    release_time: str = RELEASE_TIME
    detection_time: str = DETECTION_TIME
    slick_age_hours: float = SLICK_AGE_HOURS
    culprit_mmsi: str = CULPRIT_MMSI
    culprit_name: str = CULPRIT_NAME
    wind_drag_factor: float = WIND_DRAG_FACTOR
    forcing_start: str = FORCING_START
    forcing_end: str = FORCING_END
    provenance: str = "synthetic"
