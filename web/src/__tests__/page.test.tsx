import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import StationPage from "../pages/StationPage";
import { mockFetch, SERIES, STATION, yp } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/station/:id" element={<StationPage />} /></Routes>
    </MemoryRouter>,
  );
}

test("station page shows trend headline, charts, CSV link and attribution", async () => {
  mockFetch({ "/api/stations/01420/yearly": SERIES, "/api/stations/01420": STATION });
  renderAt("/station/01420");
  expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Frankfurt/Main");
  expect(screen.getByText("+0.39 °C")).toBeInTheDocument();
  expect(screen.getByText("per decade since 1951")).toBeInTheDocument();
  expect(screen.getByText("Download CSV")).toHaveAttribute("href", "/api/stations/01420/yearly.csv?ref=1961-1990");
  expect(screen.getAllByText(/Data: Deutscher Wetterdienst \(DWD\)/).length).toBeGreaterThanOrEqual(3);
  // in the station history list and as a marker on the chart
  expect(screen.getAllByText(/Station moved 5.9 km/)).toHaveLength(2);
  expect(screen.getByText("What is a temperature anomaly?")).toBeInTheDocument();
});

test("young station shows the message and offers 1991–2020", async () => {
  const young = {
    ...SERIES,
    ref_mean_c: null,
    trend_c_per_decade: null,
    message: "Only 0 of 30 years in 1961–1990 are complete. Try the 1991–2020 reference period instead.",
    years: [yp(2015, null), yp(2016, null)],
  };
  mockFetch({ "/api/stations/15000/yearly": young, "/api/stations/15000": { ...STATION, id: "15000", events: [] } });
  renderAt("/station/15000");
  expect(await screen.findByText(/Only 0 of 30 years/)).toBeInTheDocument();
  expect(screen.getByText("Switch to 1991–2020")).toBeInTheDocument();
  expect(screen.queryByText("Warming stripes")).not.toBeInTheDocument();
});

test("unknown station shows a not-found error", async () => {
  mockFetch({});
  renderAt("/station/12345");
  expect(await screen.findByRole("alert")).toHaveTextContent("Station “12345” is not available.");
});
