"""DWD open-data access: folder listing and downloads."""

from __future__ import annotations

import os
import re
import time

import httpx

BASE_URL = os.environ.get(
    "DWD_BASE_URL",
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl",
)
STATION_LIST = "KL_Tageswerte_Beschreibung_Stationen.txt"
USER_AGENT = "station-warming-explorer/0.1 (educational; open-data ingest)"

_HREF_RE = re.compile(r'href="([^"]+)"')


class DWDClient:
    def __init__(self, base_url: str = BASE_URL, pause_s: float = 1.0, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.pause_s = pause_s
        self._client = httpx.Client(
            timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        )
        self._listing_cache: dict[str, list[str]] = {}
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DWDClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, url: str) -> httpx.Response:
        # Polite pacing: one request at a time with a short pause between them.
        wait = self.pause_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            try:
                resp = self._client.get(url)
                self._last_request = time.monotonic()
                resp.raise_for_status()
                return resp
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                    raise
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    def listing(self, folder: str) -> list[str]:
        """File names in historical/ or recent/ (cached per run)."""
        if folder not in self._listing_cache:
            html = self._get(f"{self.base_url}/{folder}/").text
            self._listing_cache[folder] = [h for h in _HREF_RE.findall(html) if not h.startswith("..")]
        return self._listing_cache[folder]

    def station_list_bytes(self) -> bytes:
        return self._get(f"{self.base_url}/historical/{STATION_LIST}").content

    def find_zip(self, folder: str, station_id: str) -> str | None:
        prefix = f"tageswerte_KL_{station_id}_"
        matches = [f for f in self.listing(folder) if f.startswith(prefix) and f.endswith(".zip")]
        return sorted(matches)[-1] if matches else None

    def download(self, folder: str, filename: str) -> bytes:
        return self._get(f"{self.base_url}/{folder}/{filename}").content
