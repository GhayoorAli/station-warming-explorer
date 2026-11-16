#!/bin/sh
# Runs `refresh-recent` once a day at $REFRESH_AT (container local time, default 04:30).
# DWD updates recent/ each morning.
set -u
AT="${REFRESH_AT:-04:30}"
while true; do
  now=$(date +%s)
  next=$(date -d "today $AT" +%s)
  [ "$next" -le "$now" ] && next=$(date -d "tomorrow $AT" +%s)
  echo "next refresh at $(date -d "@$next")"
  sleep $((next - now))
  python -m swe_ingest.cli refresh-recent || echo "refresh failed, retrying tomorrow"
done
