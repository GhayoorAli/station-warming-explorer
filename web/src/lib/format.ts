import { scaleDiverging } from "d3-scale";
import { interpolateRdBu } from "d3-scale-chromatic";
import type { YearPoint } from "./api";

export const INCOMPLETE_COLOR = "#b8b8b8";

/** Symmetric blue–white–red scale for the station's anomalies (at least ±1 °C). */
export function anomalyColorScale(years: YearPoint[]) {
  const values = years.filter((y) => y.complete && y.anomaly_c != null).map((y) => Math.abs(y.anomaly_c!));
  const max = Math.max(1, ...values);
  // RdBu goes red -> blue, so flip the domain: cold (negative) = blue.
  return scaleDiverging<string>(interpolateRdBu).domain([max, 0, -max]).clamp(true);
}

export function colorFor(y: YearPoint, scale: (v: number) => string): string {
  if (!y.complete || y.anomaly_c == null) return INCOMPLETE_COLOR;
  return scale(y.anomaly_c);
}

const nf = (digits: number) =>
  new Intl.NumberFormat("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function signed(v: number, digits = 2): string {
  const s = nf(digits).format(Math.abs(v));
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

export function celsius(v: number | null | undefined, digits = 1): string {
  return v == null ? "–" : `${nf(digits).format(v).replace("-", "−")} °C`;
}
