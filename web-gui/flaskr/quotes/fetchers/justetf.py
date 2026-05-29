from ..model import Quote
from flaskr.model import QuoteHistoryItem
from flaskr.typing import CurrencyConversion
from .base import BaseFetcher, FetchError
from datetime import datetime
from decimal import Decimal
from typing import List
import requests
import re


class JustETF(BaseFetcher):
    _ISIN_RE = re.compile(r'isin=([A-Z]{2}[A-Z0-9]{10})')

    # justETF prices in real ISO currencies only. GBX (pence) isn't one, so we
    # request GBP and scale the result to the quote's unit afterwards. Any unit
    # not listed is assumed to be a currency justETF understands directly.
    _API_CURRENCY = {'GBX': 'GBP'}

    @classmethod
    def _apiCurrency(cls, unit):
        """The ISO currency to request from justETF for a given quote unit."""
        return cls._API_CURRENCY.get(unit, unit or 'EUR')

    @staticmethod
    def validUrl(url):
        return url.startswith("https://www.justetf.com/") and "isin=" in url

    @classmethod
    def isin(cls, url):
        if not url or not cls.validUrl(url):
            return None
        m = cls._ISIN_RE.search(url)
        return m.group(1) if m else None

    @classmethod
    def identify(cls, urls):
        for url in urls:
            isin = cls.isin(url)
            if isin:
                return isin
        return None

    def __init__(self, url):
        super(JustETF, self).__init__(url)

    def fetch(self, unit=None):
        isin = JustETF.isin(self.url)
        if not isin:
            raise FetchError(self.url, "Could not extract ISIN from URL")

        # Request the currency matching the quote's unit (GBX -> GBP) and
        # convert the result back, so the value matches the stored unit.
        apiCurrency = self._apiCurrency(unit)
        currency = unit or apiCurrency
        apiUrl = f'https://www.justetf.com/api/etfs/{isin}/quote?locale=en&currency={apiCurrency}'
        try:
            r = requests.get(apiUrl, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            raise FetchError(apiUrl, e)

        try:
            quote = data['latestQuote']['raw']
            dateStr = data['latestQuoteDate']
        except (KeyError, TypeError):
            raise FetchError(apiUrl, f"Unexpected response shape: {data!r}")

        timestamp = datetime.strptime(dateStr, '%Y-%m-%d')
        value = CurrencyConversion.staticConvert(apiCurrency, currency, Decimal(str(quote)))
        return Quote(quote=value, timestamp=timestamp, ticker=isin, currency=currency)

    def fetchHistory(self, fromDate, toDate, unit='EUR') -> List[QuoteHistoryItem]:
        isin = JustETF.isin(self.url)
        if not isin:
            raise FetchError(self.url, "Could not extract ISIN from URL")

        # Ask justETF for the currency matching the quote's unit (GBX is mapped
        # to GBP), then convert each returned value back into the unit so the
        # imported series matches the existing history (e.g. GBP -> GBX = x100).
        apiCurrency = self._apiCurrency(unit)
        apiUrl = ('https://www.justetf.com/api/etfs/{}/performance-chart'
                  '?locale=en&currency={}&valuesType=MARKET_VALUE&reduceData=false'
                  '&includeDividends=false&features=DIVIDENDS'
                  '&dateFrom={:%Y-%m-%d}&dateTo={:%Y-%m-%d}').format(isin, apiCurrency, fromDate, toDate)
        try:
            r = requests.get(apiUrl, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
            series = r.json()['series']
        except Exception as e:
            raise FetchError(apiUrl, e)

        return [QuoteHistoryItem(
                    timestamp=datetime.strptime(p['date'], '%Y-%m-%d'),
                    quote=CurrencyConversion.staticConvert(
                        apiCurrency, unit, Decimal(str(p['value']['raw']))))
                for p in series]
