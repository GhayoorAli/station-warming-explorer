-- Station Warming Explorer schema (PostgreSQL 16)

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS stations (
  id          CHAR(5) PRIMARY KEY,            -- '00433'
  name        TEXT NOT NULL,
  state       TEXT,
  latitude    DOUBLE PRECISION NOT NULL,
  longitude   DOUBLE PRECISION NOT NULL,
  height_m    INT,
  from_date   DATE,
  to_date     DATE,
  loaded_at   TIMESTAMPTZ                     -- NULL until its data is ingested
);

CREATE TABLE IF NOT EXISTS daily_temp (
  station_id  CHAR(5) REFERENCES stations ON DELETE CASCADE,
  day         DATE NOT NULL,
  tmk         REAL,                           -- daily mean, NULL where DWD wrote -999
  txk         REAL,                           -- daily max (for hot days), NULL where -999
  quality     SMALLINT,                       -- QN_4
  source      TEXT NOT NULL CHECK (source IN ('historical', 'recent')),
  PRIMARY KEY (station_id, day)
);

-- Station moves and instrument changes read from the Metadaten_* files in each zip.
CREATE TABLE IF NOT EXISTS station_events (
  station_id  CHAR(5) REFERENCES stations ON DELETE CASCADE,
  day         DATE NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('move', 'instrument')),
  note        TEXT NOT NULL,
  PRIMARY KEY (station_id, day, kind)
);

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
