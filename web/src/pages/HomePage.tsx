import { useEffect } from "react";
import Attribution from "../components/Attribution";
import StationMap from "../components/StationMap";
import StationSearch from "../components/StationSearch";

export default function HomePage() {
  useEffect(() => {
    document.title = "Station Warming Explorer";
  }, []);
  return (
    <main className="page home">
      <section className="hero">
        <h1>How much has your town warmed?</h1>
        <p className="lede">
          Warming stripes and yearly temperature anomalies for German weather stations, from the
          measurements of the Deutscher Wetterdienst. Made for lessons in geography, physics and
          climate.
        </p>
        <StationSearch autoFocus />
      </section>
      <section className="block">
        <h2>Or pick a station on the map</h2>
        <StationMap />
      </section>
      <Attribution />
    </main>
  );
}
