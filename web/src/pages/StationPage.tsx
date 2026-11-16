import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import AnomalyBars from "../components/AnomalyBars";
import Attribution from "../components/Attribution";
import Explainer from "../components/Explainer";
import HotDays from "../components/HotDays";
import StationSearch from "../components/StationSearch";
import Stripes from "../components/Stripes";
import { api, ApiError, type StationDetail, type YearlySeries } from "../lib/api";
import { celsius, signed } from "../lib/format";

const REFS = ["1961-1990", "1991-2020"] as const;
const DEFAULT_REF = REFS[0];

type Load =
  | { state: "loading" }
  | { state: "error"; notFound: boolean; message: string }
  | { state: "ok"; station: StationDetail; series: YearlySeries };

export default function StationPage() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const ref = REFS.includes(params.get("ref") as never) ? params.get("ref")! : DEFAULT_REF;
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoad((l) => (l.state === "ok" && l.station.id === id.padStart(5, "0") ? l : { state: "loading" }));
    Promise.all([api.station(id, ctrl.signal), api.yearly(id, ref, ctrl.signal)])
      .then(([station, series]) => {
        setLoad({ state: "ok", station, series });
        document.title = `${station.name} – Station Warming Explorer`;
      })
      .catch((e) => {
        if (e.name === "AbortError") return;
        const notFound = e instanceof ApiError && (e.status === 404 || e.status === 422);
        setLoad({
          state: "error",
          notFound,
          message: notFound ? `Station “${id}” is not available.` : "Could not load data. Please try again.",
        });
      });
    return () => ctrl.abort();
  }, [id, ref]);

  const setRef = (r: string) => {
    const next = new URLSearchParams(params);
    if (r === DEFAULT_REF) next.delete("ref");
    else next.set("ref", r);
    setParams(next, { replace: true });
  };

  if (load.state === "loading") {
    return (
      <main className="page" aria-busy="true">
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-stripes" />
        <div className="skeleton skeleton-chart" />
      </main>
    );
  }
  if (load.state === "error") {
    return (
      <main className="page">
        <div className="notice notice-error" role="alert">
          <p>{load.message}</p>
          {load.notFound && <p>It may not be loaded yet. Search for a nearby station instead:</p>}
        </div>
        <StationSearch />
        <p><Link to="/">← Back to start</Link></p>
      </main>
    );
  }

  const { station, series } = load;
  return (
    <StationView
      station={station}
      series={series}
      refLabel={ref}
      setRef={setRef}
      copied={copied}
      onCopy={async () => {
        const url = `${window.location.origin}/station/${station.id}${ref === DEFAULT_REF ? "" : `?ref=${ref}`}`;
        try {
          await navigator.clipboard.writeText(url);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          window.prompt("Copy this link:", url);
        }
      }}
    />
  );
}

function StationView({
  station,
  series,
  refLabel,
  setRef,
  copied,
  onCopy,
}: {
  station: StationDetail;
  series: YearlySeries;
  refLabel: string;
  setRef: (r: string) => void;
  copied: boolean;
  onCopy: () => void;
}) {
  const years = series.years;
  const hasAnomalies = years.some((y) => y.anomaly_c != null);
  const refPretty = refLabel.replace("-", "–");

  const facts = useMemo(() => {
    const complete = years.filter((y) => y.complete && y.mean_c != null);
    const warmest = complete.reduce<(typeof complete)[number] | null>(
      (a, b) => (a == null || b.mean_c! > a.mean_c! ? b : a),
      null,
    );
    const lastRolling = [...years].reverse().find((y) => y.complete && y.rolling_anomaly_c != null);
    return { warmest, lastRolling, completeCount: complete.length };
  }, [years]);

  const moves = station.events;

  return (
    <main className="page station">
      <nav className="no-print crumbs">
        <Link to="/">← Other station</Link>
      </nav>

      <header className="station-head">
        <h1>{station.name}</h1>
        <p className="muted">
          {station.state} · {station.height_m} m above sea level · station {station.id} · records{" "}
          {station.first_year}–{station.last_year}
        </p>
      </header>

      {hasAnomalies && series.trend_c_per_decade != null && (
        <section className="headline">
          <div className="stat">
            <span className="stat-value">{signed(series.trend_c_per_decade)} °C</span>
            <span className="stat-label">per decade since {series.trend_since}</span>
          </div>
          {facts.lastRolling && (
            <div className="stat">
              <span className="stat-value">{signed(facts.lastRolling.rolling_anomaly_c!, 1)} °C</span>
              <span className="stat-label">
                last 10 years vs {refPretty} (to {facts.lastRolling.year})
              </span>
            </div>
          )}
          {facts.warmest && (
            <div className="stat">
              <span className="stat-value">{facts.warmest.year}</span>
              <span className="stat-label">warmest year, {celsius(facts.warmest.mean_c)}</span>
            </div>
          )}
        </section>
      )}

      <div className="toolbar no-print">
        <fieldset className="segmented">
          <legend className="visually-hidden">Reference period</legend>
          <span className="seg-label">Compared with</span>
          {REFS.map((r) => (
            <label key={r} className={r === refLabel ? "on" : ""}>
              <input type="radio" name="ref" value={r} checked={r === refLabel} onChange={() => setRef(r)} />
              {r.replace("-", "–")}
            </label>
          ))}
        </fieldset>
        <div className="actions">
          <a className="btn-secondary" href={api.csvUrl(station.id, refLabel)} download>
            Download CSV
          </a>
          <button type="button" className="btn-secondary" onClick={onCopy}>
            {copied ? "Link copied ✓" : "Copy share link"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => window.print()}>
            Print (A4)
          </button>
        </div>
      </div>

      {series.message && (
        <div className="notice" role="status">
          <p>{series.message}</p>
          {refLabel === DEFAULT_REF && (
            <button type="button" className="btn-link" onClick={() => setRef("1991-2020")}>
              Switch to 1991–2020
            </button>
          )}
        </div>
      )}

      {hasAnomalies ? (
        <>
          <section className="block">
            <h2>Warming stripes</h2>
            <p className="muted small">
              One stripe per year, {years[0].year}–{years[years.length - 1].year}. Colour shows the
              anomaly against {refPretty}; grey years are incomplete.
            </p>
            <Stripes years={years} />
            <Attribution />
          </section>

          <section className="block">
            <h2>Yearly anomaly (°C) against {refPretty}</h2>
            <p className="muted small no-print">Hover over a year for details.</p>
            <AnomalyBars years={years} events={moves} refLabel={refPretty} />
            <Attribution />
          </section>
        </>
      ) : (
        <section className="block">
          <h2>Yearly mean temperature</h2>
          <p className="muted small">
            Without a usable reference period, only the yearly means are shown ({facts.completeCount} complete years).
          </p>
          <table className="means">
            <thead><tr><th>Year</th><th>Mean</th><th>Valid days</th></tr></thead>
            <tbody>
              {years.map((y) => (
                <tr key={y.year} className={y.complete ? "" : "incomplete"}>
                  <td>{y.year}</td><td>{celsius(y.mean_c, 2)}</td><td>{y.valid_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Attribution />
        </section>
      )}

      {years.some((y) => y.hot_days != null && y.hot_days > 0) && (
        <section className="block">
          <h2>Hot days per year</h2>
          <p className="muted small">Days on which the maximum temperature reached 30 °C or more.</p>
          <HotDays years={years} />
          <Attribution />
        </section>
      )}

      {moves.length > 0 && (
        <section className="block notes">
          <h2>Station history</h2>
          <p className="muted small">
            A move or a new thermometer can cause a small step in the series. These dates are marked
            on the chart.
          </p>
          <ul>
            {moves.map((e) => (
              <li key={e.date + e.kind}>
                <time dateTime={e.date}>{e.date}</time> – {e.note}
              </li>
            ))}
          </ul>
        </section>
      )}

      <Explainer refLabel={refLabel} />

      <section className="block no-print">
        <h2>Another station</h2>
        <StationSearch />
      </section>
    </main>
  );
}
