"""PostgreSQL loading: COPY into a temp table, then idempotent upserts."""

from __future__ import annotations

import os

import psycopg

from .parse import DailyRow, Station, StationEvent

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/climate"


def connect(dsn: str | None = None) -> psycopg.Connection:
    return psycopg.connect(dsn or os.environ.get("DATABASE_URL", DEFAULT_DSN))


def upsert_stations(conn: psycopg.Connection, stations: list[Station]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE tmp_stations (LIKE stations INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        with cur.copy(
            "COPY tmp_stations (id, name, state, latitude, longitude, height_m, from_date, to_date)"
            " FROM STDIN"
        ) as copy:
            for s in stations:
                copy.write_row(
                    (s.id, s.name, s.state, s.latitude, s.longitude, s.height_m, s.from_date, s.to_date)
                )
        cur.execute(
            """
            INSERT INTO stations (id, name, state, latitude, longitude, height_m, from_date, to_date)
            SELECT id, name, state, latitude, longitude, height_m, from_date, to_date FROM tmp_stations
            ON CONFLICT (id) DO UPDATE SET
              name = EXCLUDED.name, state = EXCLUDED.state,
              latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
              height_m = EXCLUDED.height_m, from_date = EXCLUDED.from_date,
              to_date = EXCLUDED.to_date
            """
        )
        n = cur.rowcount
    conn.commit()
    return n


def upsert_daily(
    conn: psycopg.Connection, station_id: str, rows: list[tuple[DailyRow, str]]
) -> int:
    """Load (row, source) pairs for one station. Re-running is safe."""
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE tmp_daily (LIKE daily_temp INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        with cur.copy(
            "COPY tmp_daily (station_id, day, tmk, txk, quality, source) FROM STDIN"
        ) as copy:
            for r, source in rows:
                copy.write_row((station_id, r.day, r.tmk, r.txk, r.quality, source))
        # A recent value never overwrites an existing historical value.
        cur.execute(
            """
            INSERT INTO daily_temp (station_id, day, tmk, txk, quality, source)
            SELECT station_id, day, tmk, txk, quality, source FROM tmp_daily
            ON CONFLICT (station_id, day) DO UPDATE SET
              tmk = EXCLUDED.tmk, txk = EXCLUDED.txk,
              quality = EXCLUDED.quality, source = EXCLUDED.source
            WHERE daily_temp.source = 'recent' OR EXCLUDED.source = 'historical'
            """
        )
        n = cur.rowcount
    conn.commit()
    return n


def replace_events(conn: psycopg.Connection, station_id: str, events: list[StationEvent]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM station_events WHERE station_id = %s", (station_id,))
        cur.executemany(
            "INSERT INTO station_events (station_id, day, kind, note) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            [(station_id, e.day, e.kind, e.note) for e in events],
        )
    conn.commit()


def mark_loaded(conn: psycopg.Connection, station_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE stations SET loaded_at = now() WHERE id = %s", (station_id,))
    conn.commit()


def refresh_yearly(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY yearly_temp")
    conn.commit()


def station_exists(conn: psycopg.Connection, station_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM stations WHERE id = %s", (station_id,))
        return cur.fetchone() is not None


def station_ids(conn: psycopg.Connection, state: str | None = None, loaded_only: bool = False) -> list[str]:
    sql = "SELECT id FROM stations WHERE true"
    params: list = []
    if state:
        sql += " AND state = %s"
        params.append(state)
    if loaded_only:
        sql += " AND loaded_at IS NOT NULL"
    sql += " ORDER BY id"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]
