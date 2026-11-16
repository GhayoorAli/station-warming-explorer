"""Integration tests against a real PostgreSQL (skipped if unreachable).

Set TEST_DATABASE_URL, default postgresql://postgres:postgres@localhost:5432/postgres.
A throwaway database `swe_test` is created from db/schema.sql.
"""

import os
from datetime import date
from pathlib import Path

import psycopg
import pytest

from swe_ingest import load
from swe_ingest.parse import (
    DailyRow,
    decode_latin1,
    merge_historical_recent,
    parse_station_list,
    parse_zip,
)

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
ADMIN_DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")


@pytest.fixture()
def conn():
    try:
        admin = psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not reachable")
    admin.execute("DROP DATABASE IF EXISTS swe_test WITH (FORCE)")
    admin.execute("CREATE DATABASE swe_test")
    dsn = psycopg.conninfo.make_conninfo(ADMIN_DSN, dbname="swe_test")
    c = psycopg.connect(dsn)
    c.execute((ROOT / "db" / "schema.sql").read_text())
    c.commit()
    stations = parse_station_list(
        decode_latin1((FIX / "KL_Tageswerte_Beschreibung_Stationen.txt").read_bytes())
    )
    load.upsert_stations(c, stations)
    yield c
    c.close()
    admin.execute("DROP DATABASE swe_test WITH (FORCE)")
    admin.close()


def counts(c):
    return {
        t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("stations", "daily_temp", "station_events")
    }


def ingest_fixture(c):
    z = parse_zip((FIX / "tageswerte_KL_02290_19440101_19461231_hist.zip").read_bytes())
    load.upsert_daily(c, "02290", merge_historical_recent(z.rows, []))
    load.replace_events(c, "02290", z.events)
    load.mark_loaded(c, "02290")
    load.refresh_yearly(c)


def test_umlaut_names_stored_correctly(conn):
    name, state = conn.execute("SELECT name, state FROM stations WHERE id='00001'").fetchone()
    assert state == "Baden-Württemberg"
    assert conn.execute("SELECT name FROM stations WHERE id='02290'").fetchone()[0] == "Hohenpeißenberg"


def test_missing_values_are_null_and_not_counted(conn):
    ingest_fixture(conn)
    nulls = conn.execute(
        "SELECT count(*) FROM daily_temp WHERE station_id='02290' AND tmk IS NULL"
    ).fetchone()[0]
    assert nulls == 11
    mean_c, valid, min_month = conn.execute(
        "SELECT mean_c, valid_days, min_month_days FROM yearly_temp WHERE station_id='02290' AND year=1945"
    ).fetchone()
    expected = conn.execute(
        "SELECT avg(m) FROM (SELECT avg(tmk) m FROM daily_temp WHERE station_id='02290'"
        " AND day BETWEEN '1945-01-01' AND '1945-12-31' GROUP BY date_trunc('month', day)) x"
    ).fetchone()[0]
    assert valid == 365 - 11
    assert min_month == 20
    assert abs(mean_c - expected) < 1e-6
    assert -5 < mean_c < 15  # -999 never leaked into the mean


def test_rerun_changes_no_row_counts(conn):
    ingest_fixture(conn)
    before = counts(conn)
    ingest_fixture(conn)
    assert counts(conn) == before
    assert before["daily_temp"] == 1096


def test_missing_month_gives_zero_min_month_days(conn):
    ingest_fixture(conn)
    conn.execute(
        "DELETE FROM daily_temp WHERE station_id='02290' AND day BETWEEN '1946-02-01' AND '1946-02-28'"
    )
    conn.commit()
    load.refresh_yearly(conn)
    valid, min_month = conn.execute(
        "SELECT valid_days, min_month_days FROM yearly_temp WHERE station_id='02290' AND year=1946"
    ).fetchone()
    assert valid == 365 - 28
    assert min_month == 0


def test_recent_never_overwrites_historical(conn):
    hist = [(DailyRow(date(2025, 12, 31), 1.0, None, 10), "historical")]
    load.upsert_daily(conn, "01420", hist)
    load.upsert_daily(
        conn,
        "01420",
        [
            (DailyRow(date(2025, 12, 31), 50.0, None, 3), "recent"),
            (DailyRow(date(2026, 1, 1), 2.0, None, 3), "recent"),
        ],
    )
    rows = conn.execute(
        "SELECT day, tmk, source FROM daily_temp WHERE station_id='01420' ORDER BY day"
    ).fetchall()
    assert rows == [(date(2025, 12, 31), 1.0, "historical"), (date(2026, 1, 1), 2.0, "recent")]
    # Historical data published later replaces the earlier recent value.
    load.upsert_daily(conn, "01420", [(DailyRow(date(2026, 1, 1), 2.5, None, 10), "historical")])
    assert conn.execute(
        "SELECT tmk, source FROM daily_temp WHERE station_id='01420' AND day='2026-01-01'"
    ).fetchone() == (2.5, "historical")


def test_events_and_loaded_at(conn):
    ingest_fixture(conn)
    kinds = conn.execute(
        "SELECT kind, count(*) FROM station_events WHERE station_id='02290' GROUP BY kind ORDER BY kind"
    ).fetchall()
    assert kinds == [("instrument", 2), ("move", 2)]
    assert conn.execute("SELECT loaded_at IS NOT NULL FROM stations WHERE id='02290'").fetchone()[0]
    assert conn.execute("SELECT loaded_at IS NULL FROM stations WHERE id='01420'").fetchone()[0]


def test_yearly_mean_matches_dwd_published_annual_values(conn):
    """DWD's annual file (jahreswerte_KL_02290, column JA_TT) gives 5.67 °C for 1944
    and 6.73 °C for 1946. DWD averages monthly means, so must we."""
    ingest_fixture(conn)
    got = dict(conn.execute(
        "SELECT year, round(mean_c::numeric, 2) FROM yearly_temp WHERE station_id='02290'"
        " AND year IN (1944, 1946)"
    ).fetchall())
    assert {y: float(v) for y, v in got.items()} == {1944: 5.67, 1946: 6.73}
