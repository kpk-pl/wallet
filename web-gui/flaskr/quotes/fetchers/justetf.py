from ..model import Quote
from flaskr.model import QuoteHistoryItem
from .base import BaseFetcher, FetchError
from datetime import datetime
from decimal import Decimal
from typing import List
import requests
import re


class JustETF(BaseFetcher):
    _ISIN_RE = re.compile(r'isin=([A-Z]{2}[A-Z0-9]{10})')

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
    def identify(cls, quote):
        return cls.isin(quote.get('url') or '')

    def __init__(self, url):
        super(JustETF, self).__init__(url)

    def fetch(self):
        isin = JustETF.isin(self.url)
        if not isin:
            raise FetchError(self.url, "Could not extract ISIN from URL")

        apiUrl = f'https://www.justetf.com/api/etfs/{isin}/quote?locale=en&currency=EUR'
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
        return Quote(quote=quote, timestamp=timestamp, ticker=isin, currency='EUR')

    def fetchHistory(self, fromDate, toDate) -> List[QuoteHistoryItem]:
        isin = JustETF.isin(self.url)
        if not isin:
            raise FetchError(self.url, "Could not extract ISIN from URL")

        apiUrl = ('https://www.justetf.com/api/etfs/{}/performance-chart'
                  '?locale=en&currency=EUR&valuesType=MARKET_VALUE&reduceData=false'
                  '&includeDividends=false&features=DIVIDENDS'
                  '&dateFrom={:%Y-%m-%d}&dateTo={:%Y-%m-%d}').format(isin, fromDate, toDate)
        try:
            r = requests.get(apiUrl, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
            series = r.json()['series']
        except Exception as e:
            raise FetchError(apiUrl, e)

        return [QuoteHistoryItem(
                    timestamp=datetime.strptime(p['date'], '%Y-%m-%d'),
                    quote=Decimal(str(p['value']['raw'])))
                for p in series]
