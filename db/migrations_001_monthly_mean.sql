-- Upgrade an existing database to the DWD-style yearly mean (mean of monthly means).
-- Run once:  docker compose exec -T postgres psql -U postgres -d climate < db/migrations_001_monthly_mean.sql
BEGIN;
DROP MATERIALIZED VIEW IF EXISTS yearly_temp;
-- Yearly summary. Aggregates per month first so that a month with no rows at all
-- still counts as a month with 0 valid days (min_month_days = 0).
-- mean_c is the mean of the monthly means, which is how DWD computes its annual
-- values (JA_TT). Averaging all days instead gives short, cold February less
-- weight and comes out ~0.04 °C warmer than DWD's published figures.
CREATE MATERIALIZED VIEW IF NOT EXISTS yearly_temp AS
WITH monthly AS (
  SELECT station_id,
         EXTRACT(YEAR FROM day)::INT                AS year,
         EXTRACT(MONTH FROM day)::INT               AS month,
         AVG(tmk)::DOUBLE PRECISION                 AS mean_tmk,
         COUNT(tmk)                                 AS n_tmk,
         COUNT(*) FILTER (WHERE txk >= 30)          AS hot_days,
         COUNT(txk)                                 AS n_txk
  FROM daily_temp
  GROUP BY station_id, year, month
)
SELECT station_id,
       year,
       AVG(mean_tmk)                                 AS mean_c,
       SUM(n_tmk)::INT                               AS valid_days,
       CASE WHEN COUNT(*) FILTER (WHERE n_tmk > 0) < 12 THEN 0
            ELSE MIN(n_tmk) END::INT                 AS min_month_days,
       SUM(hot_days)::INT                            AS hot_days,
       SUM(n_txk)::INT                               AS txk_days
FROM monthly
GROUP BY station_id, year;

CREATE UNIQUE INDEX IF NOT EXISTS yearly_temp_pk ON yearly_temp (station_id, year);
COMMIT;
