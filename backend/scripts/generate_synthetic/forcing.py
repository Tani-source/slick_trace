"""Generate realistic forcing fields (ocean currents + wind) as NetCDF.

Outputs two NetCDF-3 files compatible with OpenDrift's ``reader_netcdf_CF_generic``:
- ``currents.nc``  — variables ``uo``, ``vo`` (eastward / northward water velocity)
- ``wind.nc``      — variables ``u10``, ``v10`` (eastward / northward 10 m wind)

Both share the same regular lat/lon/time grid and the same epoch so
particle advection through the two fields is trivially consistent.

Physics
-------
Currents:
  * Uniform westward shelf current (Louisiana–Texas Coastal Current).
  * Anticyclonic mesoscale eddy (warm-core ring shed from Loop Current).
  * M2 semidiurnal tidal oscillation.

Wind:
  * Synoptic-scale mean from south-southeast (typical Gulf summer).
  * Diurnal cycle (afternoon acceleration).
  * Gentle north–south spatial gradient.
  * Temporal autocorrelation via a red-noise process.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.io import netcdf_file

from . import config as C


def _epoch_dt() -> datetime:
    return datetime.fromisoformat(C.FORCING_START).replace(tzinfo=timezone.utc)


def _time_values() -> tuple[np.ndarray, datetime]:
    """Return (time_array_in_days, epoch)."""
    epoch = _epoch_dt()
    t0 = datetime.fromisoformat(C.FORCING_START).replace(tzinfo=timezone.utc)
    t1 = datetime.fromisoformat(C.FORCING_END).replace(tzinfo=timezone.utc)
    n_steps = int((t1 - t0).total_seconds() / (C.TIME_STEP_HOURS * 3600)) + 1
    times_s = np.linspace(0, (t1 - t0).total_seconds(), n_steps)
    return times_s / 86400.0, epoch  # days since epoch


def _make_grid() -> tuple[np.ndarray, np.ndarray]:
    min_lat, min_lon, max_lat, max_lon = C.BBOX
    lats = np.arange(min_lat, max_lat + C.GRID_RES_DEG * 0.5, C.GRID_RES_DEG)
    lons = np.arange(min_lon, max_lon + C.GRID_RES_DEG * 0.5, C.GRID_RES_DEG)
    return lats, lons


def _eddy_velocity(lat_grid: np.ndarray, lon_grid: np.ndarray, t_frac: float) -> tuple[np.ndarray, np.ndarray]:
    """Anticyclonic (clockwise) Gaussian eddy velocity field."""
    dlat = lat_grid - C.EDDY_CENTER_LAT
    dlon = (lon_grid - C.EDDY_CENTER_LON) * np.cos(np.radians(C.EDDY_CENTER_LAT))
    r_deg = np.sqrt(dlat**2 + dlon**2)
    r_km = r_deg * 111.0
    R_km = C.EDDY_RADIUS_DEG * 111.0
    profile = (r_km / R_km) * np.exp(0.5 * (1.0 - (r_km / R_km) ** 2))
    # Tangential direction: clockwise = (-sin θ, cos θ) in (u, v)
    theta = np.arctan2(dlat, dlon)
    v_t = C.EDDY_MAX_VEL * profile * (1.0 + 0.05 * np.sin(2 * np.pi * t_frac))
    u_eddy = -v_t * np.sin(theta)
    v_eddy = v_t * np.cos(theta)
    return u_eddy, v_eddy


def _tidal_velocity(t_hours: float) -> tuple[float, float]:
    omega = 2.0 * np.pi / C.TIDAL_PERIOD_H
    return C.TIDAL_AMP_U * np.sin(omega * t_hours), C.TIDAL_AMP_V * np.cos(omega * t_hours)


def _wind_red_noise(n_steps: int, rng: np.random.Generator) -> np.ndarray:
    alpha = 0.92  # temporal autocorrelation
    noise = rng.standard_normal(n_steps)
    out = np.empty(n_steps)
    out[0] = noise[0]
    for i in range(1, n_steps):
        out[i] = alpha * out[i - 1] + np.sqrt(1 - alpha**2) * noise[i]
    return out


def generate_currents(out_dir: Path, rng: np.random.Generator) -> Path:
    """Write currents.nc and return its path."""
    lats, lons = _make_grid()
    time_days, epoch = _time_values()
    n_time = len(time_days)
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    uo = np.empty((n_time, len(lats), len(lons)), dtype=np.float32)
    vo = np.empty((n_time, len(lats), len(lons)), dtype=np.float32)
    for ti in range(n_time):
        t_hours = time_days[ti] * 24.0
        t_frac = time_days[ti] / time_days[-1] if time_days[-1] > 0 else 0.0
        u_eddy, v_eddy = _eddy_velocity(lat_grid, lon_grid, t_frac)
        u_tide, v_tide = _tidal_velocity(t_hours)
        uo[ti] = C.CURRENT_U_BG + u_eddy + u_tide
        vo[ti] = C.CURRENT_V_BG + v_eddy + v_tide
    nc_path = out_dir / "currents.nc"
    _write_netCDF(nc_path, lats, lons, time_days, epoch, uo, vo,
                  u_name="uo", v_name="vo",
                  u_std="eastward_water_velocity",
                  v_std="northward_water_velocity",
                  u_long="Eastward Current Velocity",
                  v_long="Northward Current Velocity")
    return nc_path


def generate_wind(out_dir: Path, rng: np.random.Generator) -> Path:
    """Write wind.nc and return its path."""
    lats, lons = _make_grid()
    time_days, epoch = _time_values()
    n_time = len(time_days)
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    from_dir_rad = np.radians(C.WIND_FROM_DEG)
    u_mean = -C.WIND_SPEED_MS * np.sin(from_dir_rad)
    v_mean = -C.WIND_SPEED_MS * np.cos(from_dir_rad)
    grad_v = C.WIND_GRAD_PER_DEG_LAT * (lat_grid - np.mean(lats))
    n_synoptic = n_time
    red_u = _wind_red_noise(n_synoptic, rng) * 0.5
    red_v = _wind_red_noise(n_synoptic, rng) * 0.5
    u10 = np.empty((n_time, len(lats), len(lons)), dtype=np.float32)
    v10 = np.empty((n_time, len(lats), len(lons)), dtype=np.float32)
    epoch_hours = epoch.hour + epoch.minute / 60.0
    for ti in range(n_time):
        t_hours = time_days[ti] * 24.0
        local_hour = (epoch_hours + t_hours) % 24.0
        diurnal = C.WIND_DIURNAL_AMP * np.exp(-0.5 * ((local_hour - 15.0) / 4.0) ** 2)
        u10[ti] = (u_mean + red_u[ti] + grad_v * 0.0 + diurnal * 0.1).astype(np.float32)
        v10[ti] = (v_mean + red_v[ti] + grad_v + diurnal).astype(np.float32)
    nc_path = out_dir / "wind.nc"
    _write_netCDF(nc_path, lats, lons, time_days, epoch, u10, v10,
                  u_name="u10", v_name="v10",
                  u_std="eastward_wind", v_std="northward_wind",
                  u_long="10m Eastward Wind", v_long="10m Northward Wind")
    return nc_path


def _write_netCDF(
    path: Path,
    lats: np.ndarray,
    lons: np.ndarray,
    time_days: np.ndarray,
    epoch: datetime,
    u: np.ndarray,
    v: np.ndarray,
    *,
    u_name: str,
    v_name: str,
    u_std: str,
    v_std: str,
    u_long: str,
    v_long: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    epoch_str = epoch.strftime("%Y-%m-%dT%H:%M:%S")
    with netcdf_file(str(path), "w") as f:
        f.history = f"Synthetic forcing - {C.REGION_NAME} - provenance: synthetic"
        f.source = "slicktrace/generate_synthetic"
        f.Conventions = "CF-1.8"
        f.createDimension("latitude", len(lats))
        f.createDimension("longitude", len(lons))
        f.createDimension("time", len(time_days))
        lat_v = f.createVariable("latitude", "f", ("latitude",))
        lat_v[:] = lats
        lat_v.units = "degrees_north"
        lat_v.standard_name = "latitude"
        lat_v.axis = "Y"
        lon_v = f.createVariable("longitude", "f", ("longitude",))
        lon_v[:] = lons
        lon_v.units = "degrees_east"
        lon_v.standard_name = "longitude"
        lon_v.axis = "X"
        t_v = f.createVariable("time", "f8", ("time",))
        t_v[:] = time_days
        t_v.units = f"days since {epoch_str}"
        t_v.standard_name = "time"
        t_v.axis = "T"
        t_v.calendar = "standard"
        for data, name, std, long_name in [(u, u_name, u_std, u_long),
                                           (v, v_name, v_std, v_long)]:
            var = f.createVariable(name, "f", ("time", "latitude", "longitude"))
            var[:] = data
            var.units = "m s-1"
            var.standard_name = std
            var.long_name = long_name


def load_currents_at(nc_path: Path, lat: float, lon: float,
                     time_s: float) -> tuple[float, float]:
    """Bilinearly interpolate currents at (lat, lon, time_s) — used by slick.py."""
    with netcdf_file(str(nc_path), "r") as f:
        lats = np.array(f.variables["latitude"][:], copy=True)
        lons = np.array(f.variables["longitude"][:], copy=True)
        t_s = np.array(f.variables["time"][:], copy=True) * 86400.0
        uo = np.array(f.variables["uo"][:], copy=True)
        vo = np.array(f.variables["vo"][:], copy=True)
    return _interp3d(uo, lats, lons, t_s, lat, lon, time_s), \
           _interp3d(vo, lats, lons, t_s, lat, lon, time_s)


def load_wind_at(nc_path: Path, lat: float, lon: float,
                 time_s: float) -> tuple[float, float]:
    """Bilinearly interpolate wind at (lat, lon, time_s) — used by slick.py."""
    with netcdf_file(str(nc_path), "r") as f:
        lats = np.array(f.variables["latitude"][:], copy=True)
        lons = np.array(f.variables["longitude"][:], copy=True)
        t_s = np.array(f.variables["time"][:], copy=True) * 86400.0
        u10 = np.array(f.variables["u10"][:], copy=True)
        v10 = np.array(f.variables["v10"][:], copy=True)
    return _interp3d(u10, lats, lons, t_s, lat, lon, time_s), \
           _interp3d(v10, lats, lons, t_s, lat, lon, time_s)


def _interp3d(field: np.ndarray, lats: np.ndarray, lons: np.ndarray,
              t_s: np.ndarray, lat: float, lon: float, time_s: float) -> float:
    """Trilinear interpolation of a (time, lat, lon) field."""
    j = int(np.clip(np.searchsorted(lats, lat) - 1, 0, len(lats) - 2))
    i = int(np.clip(np.searchsorted(lons, lon) - 1, 0, len(lons) - 2))
    k = int(np.clip(np.searchsorted(t_s, time_s) - 1, 0, len(t_s) - 2))
    fj = (lat - lats[j]) / max(lats[j + 1] - lats[j], 1e-12)
    fi = (lon - lons[i]) / max(lons[i + 1] - lons[i], 1e-12)
    fk = (time_s - t_s[k]) / max(t_s[k + 1] - t_s[k], 1e-12)
    fj, fi, fk = np.clip(fj, 0, 1), np.clip(fi, 0, 1), np.clip(fk, 0, 1)
    c000 = field[k, j, i]
    c001 = field[k, j, i + 1]
    c010 = field[k, j + 1, i]
    c011 = field[k, j + 1, i + 1]
    c100 = field[k + 1, j, i]
    c101 = field[k + 1, j, i + 1]
    c110 = field[k + 1, j + 1, i]
    c111 = field[k + 1, j + 1, i + 1]
    c00 = c000 * (1 - fi) + c001 * fi
    c01 = c010 * (1 - fi) + c011 * fi
    c10 = c100 * (1 - fi) + c101 * fi
    c11 = c110 * (1 - fi) + c111 * fi
    c0 = c00 * (1 - fj) + c01 * fj
    c1 = c10 * (1 - fj) + c11 * fj
    return float(c0 * (1 - fk) + c1 * fk)


def batch_load_velocities(
    nc_currents: Path,
    nc_wind: Path,
    lats: np.ndarray,
    lons: np.ndarray,
    times_s: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised trilinear interpolation for many particles × one timestep.

    Returns (u_total, v_total) each shaped (N,) where
    u_total = current_u + wind_drag × wind_u etc.
    """
    with netcdf_file(str(nc_currents), "r") as f:
        clats = np.array(f.variables["latitude"][:], copy=True)
        clons = np.array(f.variables["longitude"][:], copy=True)
        ct_s = np.array(f.variables["time"][:], copy=True) * 86400.0
        uo = np.array(f.variables["uo"][:], copy=True)
        vo = np.array(f.variables["vo"][:], copy=True)
    with netcdf_file(str(nc_wind), "r") as f:
        u10 = np.array(f.variables["u10"][:], copy=True)
        v10 = np.array(f.variables["v10"][:], copy=True)
    N = len(lats)
    u_tot = np.empty(N, dtype=np.float64)
    v_tot = np.empty(N, dtype=np.float64)
    for n in range(N):
        cu, cv = _interp3d(uo, clats, clons, ct_s, lats[n], lons[n], times_s[n]), \
                  _interp3d(vo, clats, clons, ct_s, lats[n], lons[n], times_s[n])
        wu, wv = _interp3d(u10, clats, clons, ct_s, lats[n], lons[n], times_s[n]), \
                  _interp3d(v10, clats, clons, ct_s, lats[n], lons[n], times_s[n])
        u_tot[n] = cu + C.WIND_DRAG_FACTOR * wu
        v_tot[n] = cv + C.WIND_DRAG_FACTOR * wv
    return u_tot, v_tot
