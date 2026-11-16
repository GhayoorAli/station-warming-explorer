export interface StationSummary {
  id: string;
  name: string;
  state: string | null;
  lat: number;
  lon: number;
  first_year: number | null;
  last_year: number | null;
}

export interface NearStation extends StationSummary {
  distance_km: number;
}

export interface StationEvent {
  date: string;
  kind: "move" | "instrument";
  note: string;
}

export interface StationDetail extends StationSummary {
  height_m: number | null;
  from_date: string | null;
  to_date: string | null;
  events: StationEvent[];
  attribution: string;
}

export interface YearPoint {
  year: number;
  mean_c: number | null;
  anomaly_c: number | null;
  valid_days: number;
  complete: boolean;
  rolling_anomaly_c: number | null;
  hot_days: number | null;
}

export interface YearlySeries {
  station_id: string;
  station_name: string;
  ref: string;
  ref_mean_c: number | null;
  ref_complete_years: number;
  min_days: number;
  trend_c_per_decade: number | null;
  trend_since: number | null;
  message: string | null;
  attribution: string;
  years: YearPoint[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  search: (q: string, limit = 10, signal?: AbortSignal) =>
    getJson<StationSummary[]>(`/api/stations?q=${encodeURIComponent(q)}&limit=${limit}`, signal),
  all: (signal?: AbortSignal) => getJson<StationSummary[]>(`/api/stations?limit=2000`, signal),
  near: (lat: number, lon: number, limit = 5, signal?: AbortSignal) =>
    getJson<NearStation[]>(
      `/api/stations/near?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}&limit=${limit}`,
      signal,
    ),
  station: (id: string, signal?: AbortSignal) =>
    getJson<StationDetail>(`/api/stations/${encodeURIComponent(id)}`, signal),
  yearly: (id: string, ref: string, signal?: AbortSignal) =>
    getJson<YearlySeries>(
      `/api/stations/${encodeURIComponent(id)}/yearly?ref=${encodeURIComponent(ref)}`,
      signal,
    ),
  csvUrl: (id: string, ref: string) =>
    `/api/stations/${encodeURIComponent(id)}/yearly.csv?ref=${encodeURIComponent(ref)}`,
};
