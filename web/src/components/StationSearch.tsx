import { useEffect, useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type NearStation, type StationSummary } from "../lib/api";

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

type Result = StationSummary & { distance_km?: number };

/** Search box with debounced calls to /api/stations?q= plus "use my location". */
export default function StationSearch({ autoFocus = false }: { autoFocus?: boolean }) {
  const navigate = useNavigate();
  const listId = useId();
  const [q, setQ] = useState("");
  const debounced = useDebounced(q.trim(), 250);
  const [results, setResults] = useState<Result[]>([]);
  const [mode, setMode] = useState<"search" | "near">("search");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState("");
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (mode !== "search") return;
    if (debounced.length < 2) {
      setResults([]);
      setStatus("idle");
      return;
    }
    const ctrl = new AbortController();
    setStatus("loading");
    api
      .search(debounced, 10, ctrl.signal)
      .then((r) => {
        setResults(r);
        setActive(0);
        setStatus("idle");
      })
      .catch((e) => {
        if (e.name === "AbortError") return;
        setError("Search failed. Is the API running?");
        setStatus("error");
      });
    return () => ctrl.abort();
  }, [debounced, mode]);

  function locate() {
    if (!navigator.geolocation) {
      setError("Your browser cannot share its location.");
      setStatus("error");
      return;
    }
    setMode("near");
    setQ("");
    setStatus("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        api
          .near(pos.coords.latitude, pos.coords.longitude, 5)
          .then((r: NearStation[]) => {
            setResults(r);
            setActive(0);
            setStatus("idle");
          })
          .catch(() => {
            setError("Could not load nearby stations.");
            setStatus("error");
          });
      },
      () => {
        setError("Location permission was denied. Type a town name instead.");
        setStatus("error");
        setMode("search");
      },
      { timeout: 10000, maximumAge: 600000 },
    );
  }

  function go(s: StationSummary) {
    navigate(`/station/${s.id}`);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!results.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(results[active]);
    }
  }

  const showEmpty = mode === "search" && debounced.length >= 2 && status === "idle" && results.length === 0;

  return (
    <div className="search">
      <div className="search-row">
        <label className="visually-hidden" htmlFor={`${listId}-q`}>Town or station name</label>
        <input
          id={`${listId}-q`}
          type="search"
          placeholder="Type a town, e.g. Frankfurt, München, Görlitz"
          value={q}
          autoFocus={autoFocus}
          autoComplete="off"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls={listId}
          aria-activedescendant={results.length ? `${listId}-${active}` : undefined}
          onChange={(e) => {
            setMode("search");
            setError("");
            setQ(e.target.value);
          }}
          onKeyDown={onKeyDown}
        />
        <button type="button" className="btn-secondary" onClick={locate}>
          Use my location
        </button>
      </div>

      {status === "loading" && <p className="muted small">Searching…</p>}
      {status === "error" && <p className="error small" role="alert">{error}</p>}
      {showEmpty && (
        <p className="muted small">
          No loaded station matches “{debounced}”. Try a nearby larger town or use your location.
        </p>
      )}
      {mode === "near" && results.length > 0 && <p className="muted small">Nearest stations to you:</p>}

      {results.length > 0 && (
        <ul className="results" id={listId} role="listbox">
          {results.map((s, i) => (
            <li
              key={s.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(s)}
            >
              <span className="r-name">{s.name}</span>
              <span className="r-meta">
                {s.state}
                {s.first_year ? ` · since ${s.first_year}` : ""}
                {s.distance_km != null ? ` · ${s.distance_km.toFixed(1)} km away` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
