import type { StationDetail, YearPoint, YearlySeries } from "../lib/api";

export function yp(year: number, anomaly: number | null, complete = true): YearPoint {
  return {
    year,
    mean_c: anomaly == null ? null : 9 + anomaly,
    anomaly_c: anomaly,
    valid_days: complete ? 365 : 300,
    complete,
    rolling_anomaly_c: year >= 1960 ? 0.1 * (year - 1960) : null,
    hot_days: 3,
  };
}

export const YEARS: YearPoint[] = Array.from({ length: 70 }, (_, i) =>
  yp(1951 + i, (i - 35) * 0.04, i !== 24),
);

export const SERIES: YearlySeries = {
  station_id: "01420",
  station_name: "Frankfurt/Main",
  ref: "1961-1990",
  ref_mean_c: 9.71,
  ref_complete_years: 29,
  min_days: 330,
  trend_c_per_decade: 0.39,
  trend_since: 1951,
  message: null,
  attribution: "Data: Deutscher Wetterdienst (DWD)",
  years: YEARS,
};

export const STATION: StationDetail = {
  id: "01420",
  name: "Frankfurt/Main",
  state: "Hessen",
  lat: 50.03,
  lon: 8.52,
  first_year: 1951,
  last_year: 2020,
  height_m: 100,
  from_date: "1935-07-01",
  to_date: "2026-11-13",
  events: [{ date: "2014-10-22", kind: "move", note: "Station moved 5.9 km, height 112 → 100 m" }],
  attribution: "Data: Deutscher Wetterdienst (DWD)",
};

export function mockFetch(routes: Record<string, unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    return new Response(JSON.stringify(routes[key]), { status: 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
