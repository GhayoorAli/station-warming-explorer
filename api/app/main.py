"""Station Warming Explorer API. Interactive docs at /docs."""

from __future__ import annotations

import csv
import io
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse

from . import db
from .climate import Series, YearRow, build_series, parse_ref
from .models import (
    ATTRIBUTION,
    Health,
    NearStation,
    StationDetail,
    StationEvent,
    StationSummary,
    YearlySeries,
    YearPoint,
)

CACHE = {"Cache-Control": "public, max-age=86400"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.open_pool()
    yield
    db.close_pool()


app = FastAPI(
    title="Station Warming Explorer API",
    description=(
        "Yearly temperature means, anomalies and trends for German weather stations, "
        f"built from DWD open data. {ATTRIBUTION}."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

_SUMMARY_SELECT = """
    SELECT s.id, s.name, s.state, s.latitude AS lat, s.longitude AS lon,
           y.first_year, y.last_year
    FROM stations s
    LEFT JOIN (
      SELECT station_id, MIN(year) AS first_year, MAX(year) AS last_year
      FROM yearly_temp GROUP BY station_id
    ) y ON y.station_id = s.id
    WHERE s.loaded_at IS NOT NULL
"""

StationId = Path(pattern=r"^\d{1,5}$", description="DWD station id, e.g. 01420")


def _norm_id(station_id: str) -> str:
    return station_id.zfill(5)


def _like_escape(s: str) -> str:
    return re.sub(r"([\\%_])", r"\\\1", s)


@app.get("/api/health", response_model=Health, tags=["meta"])
def health(response: Response):
    try:
        row = db.fetch_one("SELECT count(*) AS n FROM stations WHERE loaded_at IS NOT NULL")
        return Health(status="ok", database="ok", stations_loaded=row["n"])
    except Exception:  # noqa: BLE001 - report any DB failure as unhealthy
        response.status_code = 503
        return Health(status="error", database="unreachable")


@app.get("/api/stations", response_model=list[StationSummary], tags=["stations"])
def search_stations(
    response: Response,
    q: str = Query("", max_length=60, description="Part of the station name or its id"),
    limit: int = Query(10, ge=1, le=2000),
):
    """Loaded stations matching `q` (umlaut-insensitive: 'munchen', 'muenchen' and
    'München' all match). An empty `q` lists all loaded stations."""
    q = q.strip()
    sql = _SUMMARY_SELECT
    params: dict = {"limit": limit}
    if q:
        params.update(
            pat=f"%{_like_escape(q.lower())}%",
            prefix=f"{_like_escape(q.lower())}%",
            id=q.zfill(5) if q.isdigit() else None,
        )
        sql += """
          AND (unaccent(lower(s.name)) LIKE unaccent(%(pat)s)
               OR replace(replace(replace(replace(lower(s.name),
                    'ä','ae'),'ö','oe'),'ü','ue'),'ß','ss') LIKE %(pat)s
               OR s.id = %(id)s)
          ORDER BY (unaccent(lower(s.name)) LIKE unaccent(%(prefix)s)) DESC, s.name
        """
    else:
        sql += " ORDER BY s.name"
    sql += " LIMIT %(limit)s"
    response.headers.update(CACHE)
    return db.fetch_all(sql, params)


@app.get("/api/stations/near", response_model=list[NearStation], tags=["stations"])
def near_stations(
    response: Response,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    limit: int = Query(5, ge=1, le=50),
):
    """Nearest loaded stations, distance in km (haversine, computed in SQL)."""
    sql = f"""
      SELECT * FROM (
        SELECT t.*, 2 * 6371 * asin(sqrt(
                 power(sin(radians(t.lat - %(lat)s) / 2), 2)
               + cos(radians(%(lat)s)) * cos(radians(t.lat))
               * power(sin(radians(t.lon - %(lon)s) / 2), 2))) AS distance_km
        FROM ({_SUMMARY_SELECT}) t
      ) d
      ORDER BY distance_km
      LIMIT %(limit)s
    """
    response.headers.update(CACHE)
    rows = db.fetch_all(sql, {"lat": lat, "lon": lon, "limit": limit})
    for r in rows:
        r["distance_km"] = round(r["distance_km"], 1)
    return rows


def _station_or_404(station_id: str) -> dict:
    row = db.fetch_one(_SUMMARY_SELECT + " AND s.id = %(id)s", {"id": station_id})
    if row is None:
        raise HTTPException(404, f"Station {station_id} not found or not loaded yet")
    return row


@app.get("/api/stations/{station_id}", response_model=StationDetail, tags=["stations"])
def station_detail(response: Response, station_id: str = StationId):
    """Station details plus metadata notes (station moves, thermometer changes)."""
    sid = _norm_id(station_id)
    summary = _station_or_404(sid)
    extra = db.fetch_one(
        "SELECT height_m, from_date, to_date, loaded_at FROM stations WHERE id = %s", (sid,)
    )
    events = db.fetch_all(
        "SELECT day AS date, kind, note FROM station_events WHERE station_id = %s ORDER BY day",
        (sid,),
    )
    response.headers.update(CACHE)
    return StationDetail(
        **summary,
        height_m=extra["height_m"],
        from_date=extra["from_date"],
        to_date=extra["to_date"],
        loaded_at=extra["loaded_at"].isoformat() if extra["loaded_at"] else None,
        events=[StationEvent(**e) for e in events],
    )


def _series(sid: str, ref: str, min_days: int, trend_from: int) -> tuple[YearlySeries, Series]:
    try:
        ref_tuple = parse_ref(ref)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    station = _station_or_404(sid)
    rows = db.fetch_all(
        """SELECT year, mean_c, valid_days, min_month_days, hot_days, txk_days
           FROM yearly_temp WHERE station_id = %s ORDER BY year""",
        (sid,),
    )
    s = build_series([YearRow(**r) for r in rows], ref_tuple, min_days, trend_from)
    out = YearlySeries(
        station_id=sid,
        station_name=station["name"],
        ref=f"{s.ref_start}-{s.ref_end}",
        ref_mean_c=s.ref_mean_c,
        ref_complete_years=s.ref_complete_years,
        min_days=min_days,
        trend_c_per_decade=s.trend_c_per_decade,
        trend_since=s.trend_since,
        message=s.message,
        years=[YearPoint(**y.__dict__) for y in s.years],
    )
    return out, s


_RefQ = Query("1961-1990", pattern=r"^\d{4}-\d{4}$", description="Reference period")
_MinDaysQ = Query(330, ge=1, le=366, description="Valid days a year needs to count as complete")
_TrendFromQ = Query(1951, ge=1700, le=2100, description="First year used for the linear trend")


@app.get("/api/stations/{station_id}/yearly", response_model=YearlySeries, tags=["data"])
def yearly(
    response: Response,
    station_id: str = StationId,
    ref: str = _RefQ,
    min_days: int = _MinDaysQ,
    trend_from: int = _TrendFromQ,
):
    """Yearly means with anomalies against the reference period, completeness flag,
    10-year rolling mean and the linear trend in °C per decade."""
    response.headers.update(CACHE)
    return _series(_norm_id(station_id), ref, min_days, trend_from)[0]


@app.get(
    "/api/stations/{station_id}/yearly.csv",
    response_class=PlainTextResponse,
    tags=["data"],
    responses={200: {"content": {"text/csv": {}}}},
)
def yearly_csv(
    station_id: str = StationId,
    ref: str = _RefQ,
    min_days: int = _MinDaysQ,
    trend_from: int = _TrendFromQ,
):
    """Same data as /yearly, as CSV for spreadsheets."""
    s, full = _series(_norm_id(station_id), ref, min_days, trend_from)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(
        ["year", "mean_c", f"anomaly_c_vs_{s.ref}", "valid_days", "complete",
         "rolling_10y_mean_c", "hot_days_txk_30"]
    )
    for y in full.years:
        w.writerow(
            [y.year, y.mean_c, y.anomaly_c, y.valid_days, int(y.complete),
             y.rolling_mean_c, y.hot_days]
        )
    buf.write(f"\n# Station {s.station_id} {s.station_name}. {ATTRIBUTION} - opendata.dwd.de\n")
    safe = re.sub(r"[^A-Za-z0-9]+", "-", s.station_name).strip("-")
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            **CACHE,
            "Content-Disposition": f'attachment; filename="station_{s.station_id}_{safe}_yearly.csv"',
        },
    )
