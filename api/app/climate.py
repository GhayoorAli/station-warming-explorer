"""Climate logic: completeness rule, anomalies, rolling mean and linear trend.

Kept free of database and web code so it can be unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_MONTH_DAYS = 20          # every month needs at least this many valid days
MIN_REF_YEARS = 25           # of the 30 reference years, this many must be complete
ROLLING_WINDOW = 10
ROLLING_MIN_YEARS = 8        # complete years needed inside a 10-year window
DEFAULT_REF = (1961, 1990)
ALTERNATIVE_REF = (1991, 2020)


@dataclass(frozen=True)
class YearRow:
    year: int
    mean_c: float | None
    valid_days: int
    min_month_days: int
    hot_days: int = 0
    txk_days: int = 0


@dataclass(frozen=True)
class YearResult:
    year: int
    mean_c: float | None
    anomaly_c: float | None
    valid_days: int
    complete: bool
    rolling_mean_c: float | None
    rolling_anomaly_c: float | None
    hot_days: int | None


@dataclass(frozen=True)
class Series:
    years: list[YearResult]
    ref_start: int
    ref_end: int
    ref_mean_c: float | None
    ref_complete_years: int
    trend_c_per_decade: float | None
    trend_since: int | None
    message: str | None


def is_complete(row: YearRow, min_days: int) -> bool:
    return (
        row.mean_c is not None
        and row.valid_days >= min_days
        and row.min_month_days >= MIN_MONTH_DAYS
    )


def parse_ref(ref: str) -> tuple[int, int]:
    """'1961-1990' -> (1961, 1990). Raises ValueError on bad input."""
    parts = ref.split("-")
    if len(parts) != 2:
        raise ValueError("ref must look like 1961-1990")
    start, end = int(parts[0]), int(parts[1])
    if not (1700 <= start < end <= 2100):
        raise ValueError("ref years out of range")
    return start, end


def linear_trend(points: list[tuple[int, float]]) -> float | None:
    """Ordinary least squares slope in units per year."""
    n = len(points)
    if n < 10:
        return None
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in points)
    return sxy / sxx


def rolling_mean(values: dict[int, float], year: int) -> float | None:
    """Trailing 10-year mean ending at `year`, using complete years only."""
    window = [values[y] for y in range(year - ROLLING_WINDOW + 1, year + 1) if y in values]
    if len(window) < ROLLING_MIN_YEARS:
        return None
    return sum(window) / len(window)


def build_series(
    rows: list[YearRow],
    ref: tuple[int, int] = DEFAULT_REF,
    min_days: int = 330,
    trend_from: int = 1951,
) -> Series:
    rows = sorted(rows, key=lambda r: r.year)
    complete = {r.year: r.mean_c for r in rows if is_complete(r, min_days)}

    ref_start, ref_end = ref
    ref_vals = [v for y, v in complete.items() if ref_start <= y <= ref_end]
    span = ref_end - ref_start + 1
    needed = min(MIN_REF_YEARS, span)
    message = None
    if len(ref_vals) >= needed:
        ref_mean = sum(ref_vals) / len(ref_vals)
    else:
        ref_mean = None
        message = (
            f"Only {len(ref_vals)} of {span} years in {ref_start}–{ref_end} are complete "
            f"(at least {needed} needed), so anomalies cannot be calculated for this reference period."
        )
        if (ref_start, ref_end) == DEFAULT_REF:
            message += " Try the 1991–2020 reference period instead."

    years: list[YearResult] = []
    for r in rows:
        ok = r.year in complete
        anomaly = None
        if ref_mean is not None and r.mean_c is not None:
            anomaly = round(r.mean_c - ref_mean, 2)
        rm = rolling_mean(complete, r.year)
        hot = r.hot_days if r.txk_days >= min_days else None
        years.append(
            YearResult(
                year=r.year,
                mean_c=round(r.mean_c, 2) if r.mean_c is not None else None,
                anomaly_c=anomaly,
                valid_days=r.valid_days,
                complete=ok,
                rolling_mean_c=round(rm, 2) if rm is not None else None,
                rolling_anomaly_c=(
                    round(rm - ref_mean, 2) if rm is not None and ref_mean is not None else None
                ),
                hot_days=hot,
            )
        )

    # Trend over complete years from `trend_from` on (or the whole record if it starts later).
    trend_points = sorted((y, v) for y, v in complete.items() if y >= trend_from)
    slope = linear_trend(trend_points)
    return Series(
        years=years,
        ref_start=ref_start,
        ref_end=ref_end,
        ref_mean_c=round(ref_mean, 2) if ref_mean is not None else None,
        ref_complete_years=len(ref_vals),
        trend_c_per_decade=round(slope * 10, 2) if slope is not None else None,
        trend_since=trend_points[0][0] if slope is not None else None,
        message=message,
    )
