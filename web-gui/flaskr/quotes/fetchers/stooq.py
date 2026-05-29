from ..model import Quote
from .base import BaseFetcher, FetchError
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

    def fetch(self, unit=None):
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
