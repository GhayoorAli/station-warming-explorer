from datetime import date

from pydantic import BaseModel, Field

ATTRIBUTION = "Data: Deutscher Wetterdienst (DWD)"


class StationSummary(BaseModel):
    id: str = Field(examples=["01420"])
    name: str = Field(examples=["Frankfurt/Main"])
    state: str | None = Field(examples=["Hessen"])
    lat: float
    lon: float
    first_year: int | None
    last_year: int | None


class NearStation(StationSummary):
    distance_km: float


class StationEvent(BaseModel):
    date: date
    kind: str = Field(description="'move' or 'instrument'")
    note: str


class StationDetail(StationSummary):
    height_m: int | None
    from_date: date | None
    to_date: date | None
    loaded_at: str | None
    events: list[StationEvent]
    attribution: str = ATTRIBUTION


class YearPoint(BaseModel):
    year: int
    mean_c: float | None
    anomaly_c: float | None
    valid_days: int
    complete: bool
    rolling_anomaly_c: float | None = Field(
        description="Trailing 10-year mean of complete years, as anomaly (CSV also has it in °C)"
    )
    hot_days: int | None = Field(description="Days with TXK >= 30 °C (null if TXK too incomplete)")


class YearlySeries(BaseModel):
    station_id: str
    station_name: str
    ref: str = Field(examples=["1961-1990"])
    ref_mean_c: float | None
    ref_complete_years: int
    min_days: int
    trend_c_per_decade: float | None
    trend_since: int | None
    message: str | None
    attribution: str = ATTRIBUTION
    years: list[YearPoint]


class Health(BaseModel):
    status: str
    database: str
    stations_loaded: int | None = None
