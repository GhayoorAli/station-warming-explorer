"""Endpoint tests against a throwaway PostgreSQL database with synthetic stations.

Skipped if PostgreSQL is unreachable. Set TEST_DATABASE_URL (admin DSN, default
postgresql://postgres:postgres@localhost:5432/postgres).
"""

import os
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
ADMIN_DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

SEED = """
INSERT INTO stations (id, name, state, latitude, longitude, height_m, from_date, to_date, loaded_at) VALUES
 ('99999', 'Teststadt-Süd', 'Baden-Württemberg', 48.0, 9.0, 300, '1951-01-01', '2020-12-31', now()),
 ('99998', 'Jungdorf', 'Hessen', 50.1, 8.7, 100, '2011-01-01', '2020-12-31', now()),
 ('99997', 'Ungeladen', 'Hessen', 50.11, 8.71, 100, '1951-01-01', '2020-12-31', NULL);

-- 70 years, +0.03 °C/year, seasonal cycle; daily max = mean + 12.
INSERT INTO daily_temp (station_id, day, tmk, txk, quality, source)
SELECT '99999', d::date,
       8 + 0.03 * (EXTRACT(YEAR FROM d) - 1951) - 9 * cos(2 * pi() * EXTRACT(DOY FROM d) / 365.25),
       20 + 0.03 * (EXTRACT(YEAR FROM d) - 1951) - 9 * cos(2 * pi() * EXTRACT(DOY FROM d) / 365.25),
       10, 'historical'
FROM generate_series('1951-01-01'::date, '2020-12-31'::date, '1 day') d;

-- 1975: March is missing completely. 1980-07-01: DWD wrote -999 (NULL).
DELETE FROM daily_temp WHERE station_id = '99999' AND day BETWEEN '1975-03-01' AND '1975-03-31';
UPDATE daily_temp SET tmk = NULL WHERE station_id = '99999' AND day = '1980-07-01';

INSERT INTO daily_temp (station_id, day, tmk, txk, quality, source)
SELECT '99998', d::date, 10, 15, 10, 'historical'
FROM generate_series('2011-01-01'::date, '2020-12-31'::date, '1 day') d;

INSERT INTO station_events VALUES ('99999', '1990-06-01', 'move', 'Station moved 1.2 km');

REFRESH MATERIALIZED VIEW yearly_temp;
"""


@pytest.fixture(scope="module")
def client():
    try:
        admin = psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not reachable")
    admin.execute("DROP DATABASE IF EXISTS swe_api_test WITH (FORCE)")
    admin.execute("CREATE DATABASE swe_api_test")
    dsn = psycopg.conninfo.make_conninfo(ADMIN_DSN, dbname="swe_api_test")
    with psycopg.connect(dsn) as c:
        c.execute((ROOT / "db" / "schema.sql").read_text())
        c.execute(SEED)
    os.environ["DATABASE_URL"] = dsn

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as tc:
        yield tc
    admin.execute("DROP DATABASE swe_api_test WITH (FORCE)")
    admin.close()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "stations_loaded": 2}


@pytest.mark.parametrize("q", ["süd", "sud", "sued", "TESTSTADT", "99999", "Teststadt-Süd"])
def test_search_is_umlaut_insensitive(client, q):
    r = client.get("/api/stations", params={"q": q})
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == ["99999"]
    assert r.json()[0]["name"] == "Teststadt-Süd"
    assert r.json()[0]["first_year"] == 1951 and r.json()[0]["last_year"] == 2020
    assert r.headers["cache-control"] == "public, max-age=86400"


def test_search_only_loaded_and_wildcards_escaped(client):
    assert client.get("/api/stations", params={"q": "ungeladen"}).json() == []
    assert client.get("/api/stations", params={"q": "%"}).json() == []
    assert len(client.get("/api/stations").json()) == 2


def test_near(client):
    r = client.get("/api/stations/near", params={"lat": 50.1, "lon": 8.7, "limit": 5})
    body = r.json()
    assert [s["id"] for s in body] == ["99998", "99999"]
    assert body[0]["distance_km"] == 0.0
    assert 230 < body[1]["distance_km"] < 240  # 50.1N 8.7E -> 48N 9E


def test_station_detail_with_events(client):
    r = client.get("/api/stations/99999")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "Baden-Württemberg"
    assert body["events"] == [{"date": "1990-06-01", "kind": "move", "note": "Station moved 1.2 km"}]
    assert "Deutscher Wetterdienst" in body["attribution"]


def test_unknown_and_unloaded_station_404(client):
    assert client.get("/api/stations/12345").status_code == 404
    assert client.get("/api/stations/99997/yearly").status_code == 404
    assert client.get("/api/stations/abc").status_code == 422


def test_yearly_series(client):
    r = client.get("/api/stations/99999/yearly")
    assert r.status_code == 200
    body = r.json()
    years = {y["year"]: y for y in body["years"]}
    assert len(years) == 70
    assert len(r.content) < 10_000  # compact payload
    # Missing month -> incomplete; single -999 day -> still complete, 365 valid days.
    assert years[1975]["complete"] is False
    assert years[1980]["complete"] is True and years[1980]["valid_days"] == 365
    # Sanity check of the maths: reference period anomalies average ~0.
    ref = [y["anomaly_c"] for y in body["years"] if 1961 <= y["year"] <= 1990 and y["complete"]]
    assert abs(sum(ref) / len(ref)) < 0.01
    assert body["trend_c_per_decade"] == pytest.approx(0.3, abs=0.01)
    assert body["trend_since"] == 1951
    assert body["ref_complete_years"] == 29
    assert body["message"] is None
    assert years[2000]["rolling_anomaly_c"] is not None and years[1955]["rolling_anomaly_c"] is None
    # Daily max peaks at 29 °C in 1951 and ~31 °C by 2020: only recent years have hot days.
    assert years[1951]["hot_days"] == 0 and years[2020]["hot_days"] > 0


def test_yearly_alternative_reference(client):
    body = client.get("/api/stations/99999/yearly", params={"ref": "1991-2020"}).json()
    assert body["ref"] == "1991-2020"
    ref = [y["anomaly_c"] for y in body["years"] if 1991 <= y["year"] <= 2020]
    assert abs(sum(ref) / len(ref)) < 0.01


def test_young_station_message(client):
    body = client.get("/api/stations/99998/yearly").json()
    assert body["ref_mean_c"] is None
    assert all(y["anomaly_c"] is None for y in body["years"])
    assert "1991–2020" in body["message"]


def test_bad_parameters(client):
    assert client.get("/api/stations/99999/yearly", params={"ref": "1990-1961"}).status_code == 422
    assert client.get("/api/stations/99999/yearly", params={"ref": "x"}).status_code == 422
    assert client.get("/api/stations/99999/yearly", params={"min_days": 0}).status_code == 422


def test_csv(client):
    r = client.get("/api/stations/99999/yearly.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="station_99999_Teststadt-S-d_yearly.csv"' in r.headers["content-disposition"]
    lines = r.text.splitlines()
    assert lines[0].startswith("year,mean_c,anomaly_c_vs_1961-1990,valid_days,complete")
    assert lines[1].startswith("1951,")
    assert len([l for l in lines if l[:4].isdigit()]) == 70
    assert "Deutscher Wetterdienst" in lines[-1]
