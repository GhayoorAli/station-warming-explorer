import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type StationSummary } from "../lib/api";

// Bounding box of Germany; equirectangular with a cos(51°) squeeze on longitude.
const LAT0 = 55.2, LAT1 = 47.2, LON0 = 5.7, LON1 = 15.2;
const K = Math.cos((51 * Math.PI) / 180);
const W = (LON1 - LON0) * K * 100;
const H = (LAT0 - LAT1) * 100;
const px = (lon: number) => (lon - LON0) * K * 100;
const py = (lat: number) => (LAT0 - lat) * 100;

/** A small dot map of all loaded stations; click a dot to open it. */
export default function StationMap() {
  const [stations, setStations] = useState<StationSummary[] | null>(null);
  const [hover, setHover] = useState<StationSummary | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.all(ctrl.signal).then(setStations).catch(() => setStations([]));
    return () => ctrl.abort();
  }, []);

  if (!stations) return <div className="map map-loading" aria-busy="true" />;
  if (stations.length === 0) return null;

  return (
    <figure className="map">
      <svg viewBox={`-20 -20 ${W + 40} ${H + 40}`} role="img" aria-label={`Map of ${stations.length} loaded stations`}>
        <rect x={0} y={0} width={W} height={H} className="map-frame" rx={8} />
        {stations.map((s) => (
          <Link key={s.id} to={`/station/${s.id}`} aria-label={s.name}>
            <circle
              cx={px(s.lon)}
              cy={py(s.lat)}
              r={hover?.id === s.id ? 14 : 9}
              className="map-dot"
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
            />
          </Link>
        ))}
        {hover && (
          <text
            x={px(hover.lon)}
            y={py(hover.lat) - 22}
            textAnchor={px(hover.lon) > W * 0.7 ? "end" : px(hover.lon) < W * 0.3 ? "start" : "middle"}
            className="map-label"
          >
            {hover.name}
          </text>
        )}
      </svg>
      <figcaption className="muted small">{stations.length} stations loaded · click a dot</figcaption>
    </figure>
  );
}
