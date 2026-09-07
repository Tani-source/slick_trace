from __future__ import annotations

import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import DATASET_TYPES
from ..services import run_store

router = APIRouter(prefix="/datasets", tags=["datasets"])

DatasetType = Literal["wind", "current", "sar", "ais"]

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_TIFF_LE_MAGIC = b"II*\x00"
_TIFF_BE_MAGIC = b"MM\x00*"
_NPY_MAGIC = b"\x93NUMPY"
_NETCDF_CLASSIC_MAGIC = (b"CDF\x01", b"CDF\x02", b"CDF\x05")
_HDF5_MAGIC = b"\x89HDF"

_TIME_COLUMNS = {"timestamp", "time", "datetime", "date", "measurementtime"}
_AIS_MMSI_COLUMNS = {"mmsi", "mmsi_number", "shipid"}
_LAT_COLUMNS = {"lat", "latitude", "y"}
_LON_COLUMNS = {"lon", "longitude", "x"}
_WIND_U_COLUMNS = {"u", "u10", "uwnd", "wind_u", "x_wind"}
_WIND_V_COLUMNS = {"v", "v10", "vwnd", "wind_v", "y_wind"}
_CURRENT_U_COLUMNS = {"uo", "u_current", "u_velocity"}
_CURRENT_V_COLUMNS = {"vo", "v_current", "v_velocity"}


def _header_columns(data: bytes) -> list[str] | None:
    import pandas as pd

    try:
        df = pd.read_csv(io.BytesIO(data), nrows=0)
    except Exception:
        return None
    return [str(col).strip() for col in df.columns]


def _find(columns: list[str], candidates: set[str]) -> str | None:
    lowered = {col.lower() for col in columns}
    for col in candidates:
        if col in lowered:
            return col
    for col in columns:
        low = col.lower()
        if low.startswith("time") or low.endswith("timestamp"):
            return col
    return None


def _range_from_time(data: bytes, time_col: str) -> list[str] | None:
    import pandas as pd

    try:
        df = pd.read_csv(io.BytesIO(data), usecols=[time_col], nrows=50_000)
        parsed = pd.to_datetime(df[time_col], errors="coerce")
        parsed = parsed.dropna()
        if parsed.empty:
            return None
        return [parsed.min().isoformat(), parsed.max().isoformat()]
    except Exception:
        return None


def _bbox_from_columns(data: bytes, lat_col: str, lon_col: str) -> list[float] | None:
    import pandas as pd

    try:
        df = pd.read_csv(io.BytesIO(data), usecols=[lat_col, lon_col], nrows=50_000)
        return [
            round(float(df[lat_col].min()), 6),
            round(float(df[lon_col].min()), 6),
            round(float(df[lat_col].max()), 6),
            round(float(df[lon_col].max()), 6),
        ]
    except Exception:
        return None


def _validate_wind(data: bytes) -> tuple[bool, str | None, dict]:
    if len(data) == 0:
        return False, "file empty", {}
    if data.startswith(_NETCDF_CLASSIC_MAGIC) or data.startswith(_HDF5_MAGIC):
        return True, None, {"detail": "NetCDF recognized; column parsing is deferred to the drift stages"}
    columns = _header_columns(data)
    if columns is None:
        return False, "file format not recognized (expected CSV or NetCDF)", {}
    time_col = _find(columns, _TIME_COLUMNS)
    if time_col is None:
        return False, "missing timestamp column", {}
    if _find(columns, _WIND_U_COLUMNS) is None or _find(columns, _WIND_V_COLUMNS) is None:
        return False, "missing wind component column (u/v)", {}
    info: dict = {"bbox": None, "date_range": _range_from_time(data, time_col)}
    return True, None, info


def _validate_current(data: bytes) -> tuple[bool, str | None, dict]:
    if len(data) == 0:
        return False, "file empty", {}
    if data.startswith(_NETCDF_CLASSIC_MAGIC) or data.startswith(_HDF5_MAGIC):
        return True, None, {"detail": "NetCDF recognized; column parsing is deferred to the drift stages"}
    columns = _header_columns(data)
    if columns is None:
        return False, "file format not recognized (expected CSV or NetCDF)", {}
    time_col = _find(columns, _TIME_COLUMNS)
    if time_col is None:
        return False, "missing timestamp column", {}
    if _find(columns, _CURRENT_U_COLUMNS) is None or _find(columns, _CURRENT_V_COLUMNS) is None:
        return False, "missing current component column (uo/vo)", {}
    info: dict = {"bbox": None, "date_range": _range_from_time(data, time_col)}
    return True, None, info


def _validate_sar(data: bytes, bounds: str | None) -> tuple[bool, str | None, dict]:
    if len(data) == 0:
        return False, "file empty", {}
    suffix_known = data.startswith(_PNG_MAGIC) or data.startswith(_JPEG_MAGIC)
    suffix_known = suffix_known or data.startswith(_TIFF_LE_MAGIC) or data.startswith(_TIFF_BE_MAGIC)
    suffix_known = suffix_known or data.startswith(_NPY_MAGIC)
    if not suffix_known:
        return False, "file format not recognized (expected PNG, JPEG, TIFF, or .npy)", {}
    try:
        if not data.startswith(_NPY_MAGIC):
            from PIL import Image

            with Image.open(io.BytesIO(data)) as image:
                image.verify()
    except Exception:
        return False, "file not a decodable image", {}
    info: dict = {}
    if bounds:
        try:
            parsed = json.loads(bounds)
            if isinstance(parsed, list) and len(parsed) == 4:
                info["bbox"] = [float(v) for v in parsed]
        except (ValueError, TypeError):
            return False, "bounds not recognized (expected [minLat, minLon, maxLat, maxLon])", {}
    return True, None, info


def _validate_ais(data: bytes) -> tuple[bool, str | None, dict]:
    if len(data) == 0:
        return False, "file empty", {}
    columns = _header_columns(data)
    if columns is None:
        return False, "file format not recognized (expected CSV)", {}
    time_col = _find(columns, _TIME_COLUMNS)
    if time_col is None:
        return False, "missing timestamp column", {}
    mmsi_col = _find(columns, _AIS_MMSI_COLUMNS)
    if mmsi_col is None:
        return False, "missing mmsi column", {}
    lat_col = _find(columns, _LAT_COLUMNS)
    lon_col = _find(columns, _LON_COLUMNS)
    if lat_col is None or lon_col is None:
        return False, "missing latitude/longitude columns", {}
    info: dict = {
        "bbox": _bbox_from_columns(data, lat_col, lon_col),
        "date_range": _range_from_time(data, time_col),
    }
    return True, None, info


_VALIDATORS = {
    "wind": _validate_wind,
    "current": _validate_current,
    "sar": _validate_sar,
    "ais": _validate_ais,
}


@router.post("/{dataset_type}")
async def upload_dataset(
    dataset_type: DatasetType,
    file: UploadFile = File(...),
    provenance: str = Form("illustrative"),
    bounds: str | None = Form(None),
    wind_speed_ms: float | None = Form(None),
) -> dict:
    if dataset_type not in DATASET_TYPES:
        raise HTTPException(status_code=404, detail=f"unknown dataset type {dataset_type}")

    data = await file.read()
    validator = _VALIDATORS[dataset_type]
    if dataset_type == "sar":
        ok, reason, info = validator(data, bounds)
    else:
        ok, reason, info = validator(data)

    run_id = uuid.uuid4().hex[:12]
    run_store.create_run(run_id)

    record: dict = {
        "status": "uploaded" if ok else "invalid",
        "provenance": provenance if provenance in ("real", "synthetic", "illustrative") else "illustrative",
        "file_name": file.filename or "",
        "size_bytes": len(data),
        "uploaded_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    if not ok:
        record["reason"] = reason
    if ok:
        run_store.save_upload_bytes(run_id, dataset_type, file.filename or dataset_type, data)
    record.update(info)
    run_store.record_upload(run_id, dataset_type, record)

    if dataset_type == "sar" and ok:
        sar_record = run_store.get_dataset(run_id, "sar")
        if wind_speed_ms is not None:
            sar_record["wind_speed_ms"] = wind_speed_ms
        record["wind_speed_ms"] = wind_speed_ms
        run_store.record_upload(run_id, dataset_type, sar_record)

    if not ok:
        raise HTTPException(status_code=400, detail={"run_id": run_id, "reason": reason})

    return {
        "run_id": run_id,
        "type": dataset_type,
        "status": "uploaded",
        "provenance": record["provenance"],
        "file_name": record["file_name"],
        "size_bytes": record["size_bytes"],
        "bbox": info.get("bbox"),
        "date_range": info.get("date_range"),
        "detail": info.get("detail", ""),
        "wind_speed_ms": record.get("wind_speed_ms"),
    }
