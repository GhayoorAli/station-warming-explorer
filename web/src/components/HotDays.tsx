import type { YearPoint } from "../lib/api";

const W = 900;
const H = 140;
const M = { top: 10, right: 12, bottom: 24, left: 44 };

/** Days per year with a maximum of at least 30 °C (DWD column TXK). */
export default function HotDays({ years }: { years: YearPoint[] }) {
  const pts = years.filter((y) => y.hot_days != null);
  if (pts.length < 5) return null;
  const first = years[0].year;
  const span = years[years.length - 1].year - first + 1;
  const max = Math.max(5, ...pts.map((p) => p.hot_days!));
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const bw = iw / span;
  const y = (v: number) => M.top + ih - (v / max) * ih;
  const top = Math.ceil(max / 5) * 5;

  return (
    <figure className="chart hot-days">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Hot days per year (maximum ≥ 30 °C)">
        {[0, Math.round(top / 2), top].map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} className={t === 0 ? "axis-zero" : "grid"} />
            <text x={M.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="tick">{t}</text>
          </g>
        ))}
        {pts.map((p) => (
          <rect
            key={p.year}
            x={M.left + (p.year - first) * bw + bw * 0.1}
            width={Math.max(bw * 0.8, 0.8)}
            y={y(p.hot_days!)}
            height={ih - (y(p.hot_days!) - M.top)}
            className="hot-bar"
          >
            <title>{`${p.year}: ${p.hot_days} hot days`}</title>
          </rect>
        ))}
        {years.filter((p) => p.year % (span > 120 ? 20 : 10) === 0).map((p) => (
          <text key={p.year} x={M.left + (p.year - first) * bw + bw / 2} y={H - 6} textAnchor="middle" className="tick">
            {p.year}
          </text>
        ))}
      </svg>
    </figure>
  );
}
