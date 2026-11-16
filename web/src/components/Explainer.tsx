/** Plain-language explanation of anomalies for students, in English and German. */
export default function Explainer({ refLabel }: { refLabel: string }) {
  const [a, b] = refLabel.split("-");
  return (
    <section className="explainer">
      <h2>What is a temperature anomaly?</h2>
      <p>
        Each year gets one number: the average of its twelve monthly mean temperatures, the same way
        the Deutscher Wetterdienst calculates it. The{" "}
        <strong>anomaly</strong> is how much warmer or colder that year was than the average of the
        years {a}–{b} at the same station. A red stripe means warmer than that normal, a blue stripe
        colder. Comparing a station with itself removes differences such as height or city
        location, so the change over time is what remains.
      </p>
      <p>
        A year only counts if it has at least 330 days of measurements and every month has at least
        20. Otherwise it is shown in <span className="grey-chip">grey</span>, because a year with a
        missing winter would look too warm. The black line is the average of the last 10 years and
        smooths out single hot or cold years.
      </p>
      <details>
        <summary>Auf Deutsch</summary>
        <p>
          Für jedes Jahr wird der Mittelwert der zwölf Monatsmitteltemperaturen berechnet, so wie es
          auch der Deutsche Wetterdienst macht. Die{" "}
          <strong>Anomalie</strong> gibt an, um wie viel wärmer oder kälter dieses Jahr war als der
          Durchschnitt der Jahre {a}–{b} an derselben Station. Rote Streifen bedeuten wärmer, blaue
          kälter. Ein Jahr zählt nur, wenn es mindestens 330 Messtage hat und jeder Monat mindestens
          20; sonst wird es grau dargestellt. Die schwarze Linie ist der Mittelwert der letzten zehn
          Jahre.
        </p>
      </details>
    </section>
  );
}
