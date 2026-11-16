import { fireEvent, render, screen } from "@testing-library/react";
import AnomalyBars from "../components/AnomalyBars";
import Stripes from "../components/Stripes";
import { INCOMPLETE_COLOR } from "../lib/format";
import { STATION, YEARS } from "./fixtures";

test("one stripe per year, incomplete ones grey", () => {
  render(<Stripes years={YEARS} />);
  const stripes = screen.getAllByTestId("stripe");
  expect(stripes).toHaveLength(70);
  const grey = stripes.filter((s) => s.getAttribute("fill") === INCOMPLETE_COLOR);
  expect(grey).toHaveLength(1);
  expect(grey[0].getAttribute("data-complete")).toBe("false");
});

test("anomaly bars with hover details, rolling line and move markers", () => {
  render(<AnomalyBars years={YEARS} events={STATION.events} refLabel="1961–1990" />);
  expect(screen.getAllByTestId("bar")).toHaveLength(70);
  expect(screen.getByTestId("rolling").getAttribute("d")).toMatch(/^M[\d.]+,[\d.]+L/);
  fireEvent.mouseEnter(screen.getByTestId("hover-1975"));
  const tip = screen.getByRole("status");
  expect(tip).toHaveTextContent("1975");
  expect(tip).toHaveTextContent("Valid days300");
  expect(tip).toHaveTextContent("Incomplete year");
  expect(screen.getByText(/station moved \/ new thermometer/)).toBeInTheDocument();
});
