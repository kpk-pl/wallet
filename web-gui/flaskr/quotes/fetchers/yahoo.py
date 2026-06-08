from ..model import Quote
from .base import BaseFetcher, FetchError
from datetime import datetime
from decimal import Decimal
import requests
import re


class Yahoo(BaseFetcher):
    """Fetches quotes from Yahoo Finance.

    Stored URLs are the human-facing quote pages
    (e.g. https://finance.yahoo.com/quote/EURPLN=X); the lightweight chart
    JSON endpoint is derived from the symbol. Yahoo updates intraday, which
    makes it a good realtime FX source for the PLN pairs that used to come
    from stooq.
    """

    _HEADERS = {"User-Agent": "Mozilla/5.0"}
    _SYMBOL_RE = re.compile(r'/quote/([^/?#]+)')
    # query1 occasionally 401s asking for a crumb; query2 serves the same
    # chart payload, so we fall back to it before giving up.
    _HOSTS = ['query1.finance.yahoo.com', 'query2.finance.yahoo.com']

    @staticmethod
    def validUrl(url):
        return url.startswith("https://finance.yahoo.com/quote/")

    def __init__(self, url):
        super(Yahoo, self).__init__(url)
        self.symbol = Yahoo.symbol(url)

    @classmethod
    def symbol(cls, url):
        m = cls._SYMBOL_RE.search(url or '')
        return m.group(1) if m else None

    @classmethod
    def identify(cls, urls):
        for url in urls:
            if cls.validUrl(url):
                return cls.symbol(url)
        return None

    def fetch(self, unit=None):
        if not self.symbol:
            raise FetchError(self.url, "Could not extract symbol from URL")

        path = ('/v8/finance/chart/{}?interval=1d&range=1d'.format(self.symbol))
        lastError = None
        for host in self._HOSTS:
            apiUrl = 'https://{}{}'.format(host, path)
            try:
                r = requests.get(apiUrl, headers=self._HEADERS)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                lastError = (apiUrl, e)
        else:
            raise FetchError(*lastError)

        try:
            meta = data['chart']['result'][0]['meta']
            price = meta['regularMarketPrice']
            timestamp = meta['regularMarketTime']
        except (KeyError, TypeError, IndexError):
            raise FetchError(apiUrl, f"Unexpected response shape: {data!r}")

        if price is None or timestamp is None:
            raise FetchError(apiUrl, f"Yahoo returned no price for symbol '{self.symbol}'")

        return Quote(
            quote=Decimal(str(price)),
            timestamp=datetime.fromtimestamp(timestamp).replace(microsecond=0),
            ticker=meta.get('symbol', self.symbol),
            currency=meta.get('currency'),
        )
