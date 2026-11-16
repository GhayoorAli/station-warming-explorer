import { anomalyColorScale, celsius, colorFor, INCOMPLETE_COLOR, signed } from "../lib/format";
import { yp } from "./fixtures";

test("cold years are blue, warm years red, zero near white", () => {
  const years = [yp(2000, -2), yp(2001, 0), yp(2002, 2)];
  const s = anomalyColorScale(years);
  const rgb = (c: string) => c.match(/\d+/g)!.map(Number);
  const [rc, , bc] = rgb(s(-2));
  const [rw, , bw] = rgb(s(2));
  expect(bc).toBeGreaterThan(rc);
  expect(rw).toBeGreaterThan(bw);
  expect(Math.min(...rgb(s(0)))).toBeGreaterThan(230);
});

test("incomplete years are grey", () => {
  const s = anomalyColorScale([yp(2000, 1)]);
  expect(colorFor(yp(2001, 1, false), s)).toBe(INCOMPLETE_COLOR);
  expect(colorFor(yp(2002, null), s)).toBe(INCOMPLETE_COLOR);
});

test("number formatting", () => {
  expect(signed(0.314)).toBe("+0.31");
  expect(signed(-1.5, 1)).toBe("−1.5");
  expect(celsius(9.712)).toBe("9.7 °C");
  expect(celsius(null)).toBe("–");
});
