from ..model import Quote
from .base import BaseFetcher, FetchError
from datetime import datetime
from decimal import Decimal
import requests
import csv
import io


class BIS(BaseFetcher):
    """Fetches central-bank policy rates from the BIS statistics API.

    Stored URLs point at a BIS WS_CBPOL data query (e.g.
    https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.PL); the
    fetcher requests the most recent observations as CSV and returns the
    latest one that carries a value. The daily series reports NaN on
    weekends and holidays, so we pull a short window and pick the newest
    real observation. BIS sources these rates from the national central
    banks, so D.PL is the NBP reference rate.
    """

    _HEADERS = {"User-Agent": "Mozilla/5.0"}
    # Pull a short window so a run of NaNs (weekend + holiday) can't hide the
    # last real observation.
    _WINDOW = 30

    @staticmethod
    def validUrl(url):
        return url.startswith("https://stats.bis.org/")

    def __init__(self, url):
        super(BIS, self).__init__(url)

    def fetch(self, unit=None):
        # Preserve the stored data-query path, forcing CSV and a bounded
        # observation window regardless of how the URL was saved.
        base = self.url.split('?', 1)[0]
        apiUrl = f'{base}?lastNObservations={self._WINDOW}&format=csv'
        try:
            r = requests.get(apiUrl, headers=self._HEADERS)
            r.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(r.text)))
        except Exception as e:
            raise FetchError(apiUrl, e)

        # Pick the observation with the newest date that actually has a value.
        latest = None
        for row in rows:
            value = (row.get('OBS_VALUE') or '').strip()
            period = (row.get('TIME_PERIOD') or '').strip()
            if value and value.upper() != 'NAN' and period:
                if latest is None or period > latest['TIME_PERIOD'].strip():
                    latest = row

        if latest is None:
            raise FetchError(apiUrl, "BIS returned no usable observations")

        return Quote(
            quote=Decimal(latest['OBS_VALUE'].strip()),
            timestamp=datetime.strptime(latest['TIME_PERIOD'].strip(), '%Y-%m-%d'),
            ticker=(latest.get('REF_AREA') or '').strip() or None,
            name=(latest.get('TITLE') or '').strip() or None,
        )
