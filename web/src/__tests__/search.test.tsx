import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import StationSearch from "../components/StationSearch";
import { mockFetch } from "./fixtures";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("debounces typing into a single API call", async () => {
  vi.useFakeTimers();
  const fetch = mockFetch({
    "/api/stations?q=frank": [
      { id: "01420", name: "Frankfurt/Main", state: "Hessen", lat: 50, lon: 8.5, first_year: 1935, last_year: 2026 },
    ],
  });
  render(<MemoryRouter><StationSearch /></MemoryRouter>);
  const input = screen.getByRole("combobox");
  for (const q of ["f", "fr", "fra", "fran", "frank"]) {
    fireEvent.change(input, { target: { value: q } });
    await act(() => vi.advanceTimersByTimeAsync(50));
  }
  await act(() => vi.advanceTimersByTimeAsync(300));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(String(fetch.mock.calls[0][0])).toBe("/api/stations?q=frank&limit=10");
  expect(screen.getByRole("option")).toHaveTextContent("Frankfurt/Main");
  expect(screen.getByRole("option")).toHaveTextContent("since 1935");
});

test("use my location lists nearest stations with distance", async () => {
  mockFetch({
    "/api/stations/near?lat=50.1000&lon=8.7000": [
      { id: "01420", name: "Frankfurt/Main", state: "Hessen", lat: 50, lon: 8.5, first_year: 1935, last_year: 2026, distance_km: 15.2 },
    ],
  });
  vi.stubGlobal("navigator", {
    ...navigator,
    geolocation: { getCurrentPosition: (ok: PositionCallback) => ok({ coords: { latitude: 50.1, longitude: 8.7 } } as GeolocationPosition) },
  });
  render(<MemoryRouter><StationSearch /></MemoryRouter>);
  fireEvent.click(screen.getByText("Use my location"));
  expect(await screen.findByText(/15.2 km away/)).toBeInTheDocument();
});
