import { useMemo, useState } from "react";
import type { StationEvent, YearPoint } from "../lib/api";
import { anomalyColorScale, celsius, colorFor, signed } from "../lib/format";

interface Props {
  years: YearPoint[];
  events?: StationEvent[];
  refLabel: string;
}

const W = 900;
const H = 320;
const M = { top: 16, right: 12, bottom: 28, left: 44 };

/** Bars above/below zero per year, 10-year rolling mean line, station-move markers. */
export default function AnomalyBars({ years, events = [], refLabel }: Props) {
  const [hover, setHover] = useState<YearPoint | null>(null);
  const scale = useMemo(() => anomalyColorScale(years), [years]);

  const first = years[0]?.year ?? 0;
  const last = years[years.length - 1]?.year ?? 0;
  const span = last - first + 1;
  const vals = years.flatMap((y) => (y.anomaly_c != null ? [y.anomaly_c] : []));
  // Scale from complete years only: a partial current year (e.g. no December yet)
  // can be far off and would squash the real data. Incomplete bars are clipped.
  const scaleVals = years.flatMap((y) => (y.complete && y.anomaly_c != null ? [Math.abs(y.anomaly_c)] : []));
  const lim = Math.max(1, Math.ceil(Math.max(...scaleVals, 0) * 2) / 2);
  const clip = (v: number) => Math.max(-lim, Math.min(lim, v));
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const bw = iw / span;
  const x = (year: number) => M.left + (year - first) * bw;
  const y = (v: number) => M.top + ((lim - v) / (2 * lim)) * ih;

  const ticks: number[] = [];
  const step = lim > 2 ? 1 : 0.5;
  for (let t = -lim; t <= lim + 1e-9; t += step) ticks.push(Math.round(t * 10) / 10);
  const decadeStep = span > 120 ? 20 : 10;
  const xTicks = years.filter((p) => p.year % decadeStep === 0).map((p) => p.year);

  // Rolling-mean path, broken where the mean is undefined.
  let path = "";
  let pen = false;
  for (const p of years) {
    if (p.rolling_anomaly_c == null) {
      pen = false;
      continue;
    }
    path += `${pen ? "L" : "M"}${(x(p.year) + bw / 2).toFixed(1)},${y(p.rolling_anomaly_c).toFixed(1)}`;
    pen = true;
  }

  const markers = events.filter((e) => {
    const yr = Number(e.date.slice(0, 4));
    return yr >= first && yr <= last;
  });

  if (vals.length === 0) return null;

  return (
    <figure className="chart">
      <div className="chart-box">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`Yearly temperature anomaly against ${refLabel}, ${first} to ${last}`}
          onMouseLeave={() => setHover(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} className={t === 0 ? "axis-zero" : "grid"} />
              <text x={M.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="tick">
                {t === 0 ? "0" : signed(t, 1)}
              </text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} x={x(t) + bw / 2} y={H - 8} textAnchor="middle" className="tick">
              {t}
            </text>
          ))}

          {years.map((p) =>
            p.anomaly_c == null ? null : (
              <rect
                key={p.year}
                data-testid="bar"
                x={x(p.year) + bw * 0.1}
                width={Math.max(bw * 0.8, 0.8)}
                y={Math.min(y(0), y(clip(p.anomaly_c)))}
                height={Math.max(Math.abs(y(clip(p.anomaly_c)) - y(0)), 0.5)}
                fill={colorFor(p, scale)}
                opacity={p.complete ? 1 : 0.6}
              />
            ),
          )}

          {markers.map((e) => (
            <g key={e.date + e.kind} className={`marker marker-${e.kind}`}>
              <line
                x1={x(Number(e.date.slice(0, 4))) + bw / 2}
                x2={x(Number(e.date.slice(0, 4))) + bw / 2}
                y1={M.top}
                y2={H - M.bottom}
              />
              <path
                d={`M${x(Number(e.date.slice(0, 4))) + bw / 2 - 5},${M.top - 2}h10l-5,7z`}
              >
                <title>{`${e.date}: ${e.note}`}</title>
              </path>
            </g>
          ))}

          <path d={path} className="rolling" data-testid="rolling" />

          {/* Invisible hover targets, one per year */}
          {years.map((p) => (
            <rect
              key={`h${p.year}`}
              data-testid={`hover-${p.year}`}
              x={x(p.year)}
              width={bw}
              y={M.top}
              height={ih}
              fill="transparent"
              onMouseEnter={() => setHover(p)}
            />
          ))}
          {hover && (
            <rect x={x(hover.year)} width={bw} y={M.top} height={ih} className="hover-band" pointerEvents="none" />
          )}
        </svg>
        {hover && (
          <div
            className="tooltip"
            role="status"
            style={{
              left: `${((x(hover.year) + bw / 2) / W) * 100}%`,
              transform: `translateX(${hover.year - first > span / 2 ? "-105%" : "5%"})`,
            }}
          >
            <strong>{hover.year}</strong>
            <dl>
              <dt>Mean</dt>
              <dd>{celsius(hover.mean_c, 2)}</dd>
              <dt>Anomaly</dt>
              <dd>{hover.anomaly_c == null ? "–" : `${signed(hover.anomaly_c)} °C`}</dd>
              <dt>Valid days</dt>
              <dd>{hover.valid_days}</dd>
              {hover.rolling_anomaly_c != null && (
                <>
                  <dt>10-yr mean</dt>
                  <dd>{signed(hover.rolling_anomaly_c)} °C</dd>
                </>
              )}
            </dl>
            {!hover.complete && <p className="tooltip-warn">Incomplete year – not used for trend</p>}
          </div>
        )}
      </div>
      <figcaption className="legend">
        <span><i className="sw sw-warm" /> warmer than {refLabel}</span>
        <span><i className="sw sw-cold" /> colder</span>
        <span><i className="sw sw-grey" /> incomplete year</span>
        <span><i className="sw-line" /> 10-year mean</span>
        {markers.length > 0 && <span><i className="sw-marker" /> station moved / new thermometer</span>}
      </figcaption>
    </figure>
  );
}
