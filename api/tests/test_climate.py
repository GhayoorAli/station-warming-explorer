import math

import pytest

from app.climate import YearRow, build_series, is_complete, linear_trend, parse_ref


def full(year, mean, valid=365, min_month=28, hot=0):
    return YearRow(year=year, mean_c=mean, valid_days=valid, min_month_days=min_month,
                   hot_days=hot, txk_days=valid)


def test_completeness_rule():
    assert is_complete(full(2000, 9.0), 330)
    assert not is_complete(full(2000, 9.0, valid=329), 330)
    assert not is_complete(full(2000, 9.0, min_month=19), 330)   # a thin month
    assert not is_complete(full(2000, 9.0, min_month=0), 330)    # a missing month
    assert not is_complete(full(2000, None), 330)


def test_reference_mean_anomaly_is_zero():
    rows = [full(y, 8 + 0.5 * math.sin(y)) for y in range(1951, 2021)]
    s = build_series(rows)
    ref = [y.anomaly_c for y in s.years if 1961 <= y.year <= 1990]
    assert abs(sum(ref) / len(ref)) < 0.005  # values are rounded to 0.01 °C
    assert s.ref_complete_years == 30
    assert s.message is None


def test_trend_per_decade():
    rows = [full(y, 8 + 0.031 * (y - 1951)) for y in range(1951, 2021)]
    s = build_series(rows)
    assert s.trend_c_per_decade == pytest.approx(0.31, abs=1e-3)
    assert s.trend_since == 1951


def test_trend_from_skips_old_years():
    rows = [full(y, 5.0) for y in range(1900, 1951)] + [
        full(y, 8 + 0.02 * (y - 1951)) for y in range(1951, 2021)
    ]
    s = build_series(rows, trend_from=1951)
    assert s.trend_c_per_decade == pytest.approx(0.2, abs=1e-3)


def test_incomplete_year_excluded_from_reference_and_trend():
    rows = [full(y, 8.0) for y in range(1951, 2021)]
    rows[20] = full(1971, 30.0, min_month=0)  # absurd value but incomplete
    s = build_series(rows)
    assert s.ref_mean_c == pytest.approx(8.0)
    assert s.trend_c_per_decade == pytest.approx(0.0, abs=1e-9)
    y1971 = next(y for y in s.years if y.year == 1971)
    assert not y1971.complete
    assert y1971.anomaly_c == pytest.approx(22.0)  # still reported, greyed out in UI


def test_young_station_gets_null_anomaly_and_message():
    rows = [full(y, 10.0) for y in range(2011, 2026)]
    s = build_series(rows)
    assert s.ref_mean_c is None
    assert all(y.anomaly_c is None for y in s.years)
    assert "1991–2020" in s.message
    # 1991–2020 still needs 25 complete years; 10 is not enough
    s2 = build_series(rows, ref=(1991, 2020))
    assert s2.ref_mean_c is None and "1991–2020" not in s2.message.split(".")[-1]


def test_reference_needs_25_of_30_years():
    rows = [full(y, 8.0) for y in range(1966, 2021)]  # 25 ref years
    assert build_series(rows).ref_mean_c == pytest.approx(8.0)
    rows = [full(y, 8.0) for y in range(1967, 2021)]  # 24 ref years
    assert build_series(rows).ref_mean_c is None


def test_rolling_mean_needs_8_of_10_years():
    rows = [full(y, float(y - 2000)) for y in range(2000, 2015)]
    s = build_series(rows, ref=(2000, 2014))
    by = {y.year: y for y in s.years}
    assert by[2006].rolling_mean_c is None          # only 7 years
    assert by[2007].rolling_mean_c == pytest.approx(3.5)  # 2000..2007
    assert by[2014].rolling_mean_c == pytest.approx(9.5)  # 2005..2014
    assert by[2014].rolling_anomaly_c == pytest.approx(9.5 - 7.0)


def test_hot_days_null_when_txk_incomplete():
    rows = [YearRow(2000, 9.0, 365, 28, hot_days=12, txk_days=200)]
    assert build_series(rows, ref=(2000, 2001)).years[0].hot_days is None


def test_parse_ref_and_trend_helpers():
    assert parse_ref("1961-1990") == (1961, 1990)
    with pytest.raises(ValueError):
        parse_ref("1990-1961")
    assert linear_trend([(1, 1.0)] * 5) is None
