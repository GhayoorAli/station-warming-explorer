from datetime import date
from pathlib import Path

from swe_ingest.parse import (
    DailyRow,
    decode_latin1,
    merge_historical_recent,
    parse_produkt,
    parse_station_list,
    parse_zip,
)

FIX = Path(__file__).parent / "fixtures"


def stations():
    raw = (FIX / "KL_Tageswerte_Beschreibung_Stationen.txt").read_bytes()
    return {s.id: s for s in parse_station_list(decode_latin1(raw))}


def test_station_list_skips_header_and_parses_all_rows():
    s = stations()
    assert set(s) == {"00001", "01420", "02290", "03379", "04931", "05792"}


def test_station_list_latin1_umlauts():
    s = stations()
    assert s["00001"].state == "Baden-Württemberg"
    assert s["02290"].name == "Hohenpeißenberg"
    assert s["03379"].name == "München-Stadt"


def test_station_list_fields():
    f = stations()["01420"]
    assert f.name == "Frankfurt/Main"
    assert f.state == "Hessen"
    assert f.height_m == 100
    assert abs(f.latitude - 50.0259) < 1e-9 and abs(f.longitude - 8.5213) < 1e-9
    assert f.from_date == date(1935, 7, 1)
    assert stations()["05792"].height_m == 2956  # Zugspitze


def test_produkt_padding_eor_and_missing():
    text = (
        "STATIONS_ID;MESS_DATUM;QN_3;  FX;  FM;QN_4; RSK;RSKF; SDK;SHK_TAG;  NM; VPM;  PM; TMK; UPM; TXK; TNK; TGK;eor\n"
        "       1420;20250101;   10;   9.3;   2.7;    9;   0.0;   0;   1.4;   0;   1.0;   7.0; 1004.60;   -2.5;   36.00;   31.1;  -5.1;    8.4;eor\n"
        "       1420;20250102;   10;   9.3;   2.7;    9;   0.0;   0;   1.4;   0;   1.0;   7.0; 1004.60;   -999;   36.00;   -999;  -5.1;    8.4;eor\n"
    )
    rows = parse_produkt(text)
    assert rows[0] == DailyRow(day=date(2025, 1, 1), tmk=-2.5, txk=31.1, quality=9)
    assert rows[1].tmk is None and rows[1].txk is None


def test_zip_real_fixture_with_missing_days_and_metadata():
    z = parse_zip((FIX / "tageswerte_KL_02290_19440101_19461231_hist.zip").read_bytes())
    assert len(z.rows) == 366 + 365 + 365
    assert z.rows[0].day == date(1944, 1, 1)
    missing = [r for r in z.rows if r.tmk is None]
    assert len(missing) == 11  # real -999 days in May 1945
    assert all(r.day.year == 1945 and r.day.month == 5 for r in missing)
    assert all(r.tmk is None or -40 < r.tmk < 40 for r in z.rows)

    moves = [e for e in z.events if e.kind == "move"]
    assert [m.day for m in moves] == [date(1936, 12, 1), date(1940, 4, 10)]
    assert moves[0].note == "Height 985 → 986 m"
    assert moves[1].note == "Station moved 0.2 km, height 986 → 977 m"
    instruments = [e for e in z.events if e.kind == "instrument"]
    assert [i.day for i in instruments] == [date(1841, 9, 1), date(1993, 12, 9)]
    assert "PT 100" in instruments[-1].note


def test_merge_prefers_historical():
    hist = [DailyRow(date(2025, 12, d), 1.0, None, 10) for d in (30, 31)]
    rec = [
        DailyRow(date(2025, 12, 31), 99.0, None, 3),  # overlap: dropped
        DailyRow(date(2026, 1, 1), 2.0, None, 3),
    ]
    merged = merge_historical_recent(hist, rec)
    assert [(r.day, r.tmk, s) for r, s in merged] == [
        (date(2025, 12, 30), 1.0, "historical"),
        (date(2025, 12, 31), 1.0, "historical"),
        (date(2026, 1, 1), 2.0, "recent"),
    ]


def test_merge_recent_only_station():
    rec = [DailyRow(date(2026, 1, 1), 2.0, None, 3)]
    assert merge_historical_recent([], rec) == [(rec[0], "recent")]
