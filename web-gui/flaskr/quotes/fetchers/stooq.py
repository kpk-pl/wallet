from ..model import Quote
from flaskr.model import QuoteHistoryItem
from .base import BaseFetcher, FetchError
import csv
from decimal import Decimal
from io import StringIO
from typing import List
import requests
from flask import json
import dateutil.parser


class Stooq(BaseFetcher):
    _HEADERS = {"User-Agent": "Mozilla/5.0"}

    @staticmethod
    def validUrl(url):
        return url.startswith("https://stooq.pl/")

    def __init__(self, url):
        super(Stooq, self).__init__(url)
        self.symbol = Stooq.symbol(self.url)

    @staticmethod
    def symbol(url):
        s = url.find('s=')
        end = url.find('&', s)
        if end == -1:
            end = len(url)
        return url[s+2 : end]

    @classmethod
    def identify(cls, urls, stooqSymbol=None):
        if stooqSymbol:
            return stooqSymbol
        for url in urls:
            if cls.validUrl(url):
                return cls.symbol(url)
        return None

    def fetch(self):
        url = 'https://stooq.pl/q/l/?s={}&f=snd2t2c&e=json'.format(self.symbol)

        try:
            data = json.loads(requests.get(url, headers=self._HEADERS).text)
        except Exception as e:
            raise FetchError(url, e)

        symbols = data.get('symbols') or []
        if not symbols:
            raise FetchError(url, f"Stooq returned no data for symbol '{self.symbol}'")
        data = symbols[0]
        if 'date' not in data or 'close' not in data:
            raise FetchError(url, f"Stooq returned incomplete data for symbol '{self.symbol}'")

        timestamp = dateutil.parser.parse(data['date'] + ' ' + data['time'])

        return Quote(quote = data['close'], timestamp=timestamp, ticker=self.symbol, name = data['name'])

    def fetchHistory(self, fromDate, toDate) -> List[QuoteHistoryItem]:
        url = 'https://stooq.pl/q/d/l/?s={}&d1={:%Y%m%d}&d2={:%Y%m%d}&i=d'.format(self.symbol, fromDate, toDate)

        try:
            text = requests.get(url, headers=self._HEADERS).text
        except Exception as e:
            raise FetchError(url, e)

        if text.startswith("Przekroczony"):
            raise FetchError(url, "Stooq daily request limit exceeded")

        if text.startswith("Uzyskaj apikey") or "get_apikey" in text:
            raise FetchError(url, "Stooq requires an API key for this download (daily free quota exhausted for this IP)")

        rows = list(csv.reader(StringIO(text), delimiter=','))
        if not rows or not rows[0] or rows[0][0] != 'Data':
            raise FetchError(url, f"Stooq returned no history for symbol '{self.symbol}'")

        return [QuoteHistoryItem(timestamp=dateutil.parser.parse(r[0]), quote=Decimal(r[4]))
                for r in rows[1:] if len(r) > 4]
