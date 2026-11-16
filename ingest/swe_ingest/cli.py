"""Typer CLI.

    python -m swe_ingest.cli stations                 # station list -> stations
    python -m swe_ingest.cli station 01420            # one station (historical + recent)
    python -m swe_ingest.cli all --state Hessen       # every station in a state
    python -m swe_ingest.cli starter                  # ~30 long-record stations
    python -m swe_ingest.cli refresh-recent           # nightly: recent/ for loaded stations
"""

from __future__ import annotations

import time
from typing import Annotated, Optional

import httpx
import typer

from . import load
from .dwd import DWDClient
from .parse import decode_latin1, merge_historical_recent, parse_station_list, parse_zip

app = typer.Typer(add_completion=False, help="Load DWD daily climate data into PostgreSQL.")

# Long-record stations across Germany (DWD ids), used by `starter`.
STARTER_STATIONS = [
    "00433",  # Berlin-Tempelhof
    "00403",  # Berlin-Dahlem (FU)
    "01420",  # Frankfurt/Main
    "01975",  # Hamburg-Fuhlsbüttel
    "03379",  # München-Stadt
    "03987",  # Potsdam
    "02667",  # Köln-Bonn
    "01048",  # Dresden-Klotzsche
    "04931",  # Stuttgart-Echterdingen
    "00691",  # Bremen
    "02014",  # Hannover
    "03668",  # Nürnberg
    "02932",  # Leipzig/Halle
    "05705",  # Würzburg
    "01270",  # Erfurt-Weimar
    "04887",  # Stötten
    "01766",  # Münster/Osnabrück
    "02261",  # Hof
    "05792",  # Zugspitze
    "01358",  # Fichtelberg
    "02290",  # Hohenpeißenberg
    "05906",  # Mannheim
    "01303",  # Essen-Bredeney
    "04104",  # Regensburg
    "04271",  # Rostock-Warnemünde
    "05100",  # Trier-Petrisberg
    "03032",  # List auf Sylt
    "01443",  # Freiburg
    "00232",  # Augsburg
    "02483",  # Kahler Asten
    "01684",  # Görlitz
    "02712",  # Konstanz
    "04336",  # Saarbrücken-Ensheim
    "02564",  # Kiel-Holtenau
    "15000",  # Aachen-Orsbach (young station, tests the 1991-2020 fallback)
    "03231",  # Meiningen
]


def _echo(msg: str) -> None:
    typer.echo(msg)


def _ingest_one(client: DWDClient, conn, station_id: str) -> int:
    station_id = station_id.zfill(5)
    if not load.station_exists(conn, station_id):
        raise typer.BadParameter(f"station {station_id} unknown — run `stations` first")

    hist_rows, rec_rows, events = [], [], []
    hist_name = client.find_zip("historical", station_id)
    if hist_name:
        parsed = parse_zip(client.download("historical", hist_name))
        hist_rows, events = parsed.rows, parsed.events
    rec_name = client.find_zip("recent", station_id)
    if rec_name:
        parsed = parse_zip(client.download("recent", rec_name))
        rec_rows = parsed.rows
        if not events:
            events = parsed.events
    if not hist_rows and not rec_rows:
        _echo(f"  {station_id}: no daily data on DWD server, skipped")
        return 0

    merged = merge_historical_recent(hist_rows, rec_rows)
    n = load.upsert_daily(conn, station_id, merged)
    load.replace_events(conn, station_id, events)
    load.mark_loaded(conn, station_id)
    _echo(
        f"  {station_id}: {len(hist_rows)} historical + "
        f"{len(merged) - len(hist_rows)} recent days, {len(events)} events ({n} rows written)"
    )
    return n


@app.command()
def stations(dsn: Annotated[Optional[str], typer.Option(help="PostgreSQL DSN")] = None) -> None:
    """Download the DWD station list and upsert it into `stations`."""
    with DWDClient() as client, load.connect(dsn) as conn:
        parsed = parse_station_list(decode_latin1(client.station_list_bytes()))
        load.upsert_stations(conn, parsed)
        _echo(f"{len(parsed)} stations upserted")


@app.command()
def station(
    station_id: Annotated[str, typer.Argument(help="DWD station id, e.g. 00433")],
    dsn: Annotated[Optional[str], typer.Option(help="PostgreSQL DSN")] = None,
) -> None:
    """Ingest historical + recent daily data for one station."""
    with DWDClient() as client, load.connect(dsn) as conn:
        _ingest_one(client, conn, station_id)
        load.refresh_yearly(conn)
        _echo("yearly_temp refreshed")


def _ingest_many(ids: list[str], dsn: str | None, pause: float) -> None:
    ok = failed = 0
    with DWDClient(pause_s=pause) as client, load.connect(dsn) as conn:
        for i, sid in enumerate(ids, 1):
            _echo(f"[{i}/{len(ids)}] {sid}")
            try:
                _ingest_one(client, conn, sid)
                ok += 1
            except (httpx.HTTPError, ValueError) as e:
                conn.rollback()
                failed += 1
                _echo(f"  {sid}: failed ({e})")
        load.refresh_yearly(conn)
    _echo(f"done: {ok} loaded, {failed} failed; yearly_temp refreshed")


@app.command(name="all")
def all_(
    state: Annotated[Optional[str], typer.Option(help="Bundesland, e.g. Hessen")] = None,
    active_since: Annotated[int, typer.Option(help="Only stations reporting since this year")] = 0,
    pause: Annotated[float, typer.Option(help="Seconds between downloads")] = 1.0,
    dsn: Annotated[Optional[str], typer.Option(help="PostgreSQL DSN")] = None,
) -> None:
    """Ingest every station (optionally of one state), one download at a time."""
    with load.connect(dsn) as conn:
        ids = load.station_ids(conn, state=state)
        if active_since:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM stations WHERE id = ANY(%s) AND to_date >= make_date(%s, 1, 1)",
                    (ids, active_since),
                )
                ids = sorted(r[0] for r in cur.fetchall())
    _ingest_many(ids, dsn, pause)


@app.command()
def starter(
    pause: Annotated[float, typer.Option(help="Seconds between downloads")] = 1.0,
    dsn: Annotated[Optional[str], typer.Option(help="PostgreSQL DSN")] = None,
) -> None:
    """Ingest ~30 long-record stations across Germany."""
    _ingest_many(STARTER_STATIONS, dsn, pause)


@app.command(name="refresh-recent")
def refresh_recent(
    pause: Annotated[float, typer.Option(help="Seconds between downloads")] = 1.0,
    dsn: Annotated[Optional[str], typer.Option(help="PostgreSQL DSN")] = None,
) -> None:
    """Nightly job: re-download recent/ for every loaded station.

    Recent values never overwrite historical ones (enforced in the upsert)."""
    with DWDClient(pause_s=pause) as client, load.connect(dsn) as conn:
        ids = load.station_ids(conn, loaded_only=True)
        for sid in ids:
            name = client.find_zip("recent", sid)
            if not name:
                continue
            try:
                rows = parse_zip(client.download("recent", name)).rows
            except (httpx.HTTPError, ValueError) as e:
                _echo(f"  {sid}: failed ({e})")
                continue
            load.upsert_daily(conn, sid, [(r, "recent") for r in rows])
            load.mark_loaded(conn, sid)
            _echo(f"  {sid}: {len(rows)} recent days checked")
        load.refresh_yearly(conn)
    _echo(f"refreshed {len(ids)} stations at {time.strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    app()
