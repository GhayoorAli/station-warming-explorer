import { useMemo } from "react";
import type { YearPoint } from "../lib/api";
import { anomalyColorScale, colorFor, signed } from "../lib/format";

interface Props {
  years: YearPoint[];
  height?: number;
}

/** Warming stripes: one SVG <rect> per year, coloured by anomaly, grey if incomplete. */
export default function Stripes({ years, height = 140 }: Props) {
  const scale = useMemo(() => anomalyColorScale(years), [years]);
  if (years.length === 0) return null;
  const first = years[0].year;
  const last = years[years.length - 1].year;
  const span = last - first + 1;

  return (
    <figure className="stripes">
      <svg
        viewBox={`0 0 ${span} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Warming stripes ${first} to ${last}`}
        width="100%"
        height={height}
      >
        {years.map((y) => (
          <rect
            key={y.year}
            data-testid="stripe"
            data-complete={y.complete}
            x={y.year - first}
            y={0}
            width={1.02}
            height={height}
            fill={colorFor(y, scale)}
          >
            <title>
              {y.complete && y.anomaly_c != null
                ? `${y.year}: ${signed(y.anomaly_c)} °C`
                : `${y.year}: incomplete (${y.valid_days} valid days)`}
            </title>
          </rect>
        ))}
      </svg>
      <div className="stripes-axis" aria-hidden="true">
        <span>{first}</span>
        <span>{last}</span>
      </div>
    </figure>
  );
}
