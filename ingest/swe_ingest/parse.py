"""Parsers for DWD daily climate (KL) files.

Quirks handled here:
- The station list is fixed-width and Latin-1 encoded.
- produkt_klima_tag_*.txt files are semicolon-separated, padded with spaces,
  end every row with an `eor` column, and use -999 for missing values.
- Metadata files (moves, instruments) are Latin-1, semicolon-separated, and
  some end with a footer line ("generiert: ...").
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date

MISSING = -999.0

# Station list: id, from, to, height, lat, lon are whitespace-separated numbers;
# then name and state are fixed-width (41 chars each, including one space gap).
_STATION_RE = re.compile(
    r"^(\d{5})\s+(\d{8})\s+(\d{8})\s+(-?\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s(.*)$"
)
NAME_WIDTH = 41
STATE_WIDTH = 41


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    state: str | None
    latitude: float
    longitude: float
    height_m: int | None
    from_date: date | None
    to_date: date | None


@dataclass(frozen=True)
class DailyRow:
    day: date
    tmk: float | None
    txk: float | None
    quality: int | None


@dataclass(frozen=True)
class StationEvent:
    day: date
    kind: str  # 'move' | 'instrument'
    note: str


def parse_yyyymmdd(s: str) -> date | None:
    s = s.strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def decode_latin1(raw: bytes) -> str:
    return raw.decode("latin-1")


def parse_station_list(text: str) -> list[Station]:
    """Parse KL_Tageswerte_Beschreibung_Stationen.txt (already decoded)."""
    stations: list[Station] = []
    for line in text.splitlines():
        m = _STATION_RE.match(line)
        if not m:
            continue  # header, dashes, blank lines
        sid, von, bis, height, lat, lon, rest = m.groups()
        name = rest[:NAME_WIDTH].strip()
        state = rest[NAME_WIDTH : NAME_WIDTH + STATE_WIDTH].strip() or None
        stations.append(
            Station(
                id=sid,
                name=name,
                state=state,
                latitude=float(lat),
                longitude=float(lon),
                height_m=int(height),
                from_date=parse_yyyymmdd(von),
                to_date=parse_yyyymmdd(bis),
            )
        )
    return stations


def _num(value: str) -> float | None:
    v = value.strip()
    if v == "":
        return None
    f = float(v)
    return None if f == MISSING else f


def parse_produkt(text: str) -> list[DailyRow]:
    """Parse a produkt_klima_tag_*.txt file into daily rows (TMK, TXK, QN_4)."""
    lines = text.splitlines()
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split(";")]
    # Drop the trailing eor column (and any empty trailing field).
    while header and header[-1] in ("eor", ""):
        header.pop()
    idx = {name: i for i, name in enumerate(header)}
    for required in ("MESS_DATUM", "TMK"):
        if required not in idx:
            raise ValueError(f"column {required} missing in produkt file")
    i_day, i_tmk = idx["MESS_DATUM"], idx["TMK"]
    i_txk, i_q = idx.get("TXK"), idx.get("QN_4")

    rows: list[DailyRow] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(";")]
        day = parse_yyyymmdd(parts[i_day])
        if day is None:
            continue
        q = _num(parts[i_q]) if i_q is not None else None
        rows.append(
            DailyRow(
                day=day,
                tmk=_num(parts[i_tmk]),
                txk=_num(parts[i_txk]) if i_txk is not None else None,
                quality=int(q) if q is not None else None,
            )
        )
    return rows


def _read_member(zf: zipfile.ZipFile, prefix: str) -> str | None:
    for name in zf.namelist():
        if name.startswith(prefix) and name.endswith(".txt"):
            return decode_latin1(zf.read(name))
    return None


def _semicolon_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines()[1:]:
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 3 or not parts[0].isdigit():
            continue  # footer / blank
        rows.append(parts)
    return rows


def parse_moves(text: str) -> list[StationEvent]:
    """Metadaten_Geographie_*.txt: one row per location period.

    Columns: Stations_id;Stationshoehe;Geogr.Breite;Geogr.Laenge;von_datum;bis_datum;Stationsname
    A new row with a different position or height is a move.
    """
    events: list[StationEvent] = []
    prev: tuple[float, float, float] | None = None
    for parts in _semicolon_rows(text):
        height, lat, lon = float(parts[1]), float(parts[2]), float(parts[3])
        start = parse_yyyymmdd(parts[4])
        if prev is not None and start is not None:
            dh = height - prev[2]
            km = _approx_km(prev[0], prev[1], lat, lon)
            # Ignore coordinate re-surveys of a few metres; keep real moves.
            if km >= 0.1 or abs(dh) > 0.5:
                parts = []
                if km >= 0.1:
                    parts.append(f"Station moved {km:.1f} km")
                if abs(dh) > 0.5:
                    parts.append(f"height {prev[2]:.0f} → {height:.0f} m")
                note = ", ".join(parts)
                note = note[0].upper() + note[1:]
                events.append(StationEvent(day=start, kind="move", note=note))
        prev = (lat, lon, height)
    return events


def parse_instruments(text: str) -> list[StationEvent]:
    """Metadaten_Geraete_Lufttemperatur_*.txt: an event whenever a new instrument
    type starts being used (ignoring the very first one)."""
    events: list[StationEvent] = []
    seen: set[str] = set()
    for parts in _semicolon_rows(text):
        if len(parts) < 9:
            continue
        start = parse_yyyymmdd(parts[6])
        device = parts[8]
        if device and device not in seen:
            if seen and start is not None:
                events.append(
                    StationEvent(day=start, kind="instrument", note=f"New thermometer: {device}")
                )
            seen.add(device)
    return events


def _approx_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


@dataclass
class ZipContents:
    rows: list[DailyRow]
    events: list[StationEvent]


def parse_zip(data: bytes) -> ZipContents:
    """Open a DWD tageswerte_KL_*.zip in memory and parse data + metadata."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        produkt = _read_member(zf, "produkt_klima_tag_")
        if produkt is None:
            raise ValueError("no produkt_klima_tag_*.txt in zip")
        rows = parse_produkt(produkt)
        events: list[StationEvent] = []
        geo = _read_member(zf, "Metadaten_Geographie_")
        if geo:
            events += parse_moves(geo)
        instr = _read_member(zf, "Metadaten_Geraete_Lufttemperatur_")
        if instr:
            events += parse_instruments(instr)
    return ZipContents(rows=rows, events=events)


def merge_historical_recent(
    historical: list[DailyRow], recent: list[DailyRow]
) -> list[tuple[DailyRow, str]]:
    """Prefer historical (quality-controlled) values; only append recent days
    after the historical end date."""
    out = [(r, "historical") for r in historical]
    last = max((r.day for r in historical), default=None)
    out += [(r, "recent") for r in recent if last is None or r.day > last]
    return out
