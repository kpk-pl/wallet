from ..model import Quote
from .base import BaseFetcher
import requests
import datetime


class Kraken(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("https://api.kraken.com/0/public/Ticker")

    def __init__(self, url):
        super(Kraken, self).__init__(url)

    def fetch(self):
        response = requests.get(self.url, headers={"User-Agent" : "Mozilla/5.0"}).json()
        jsonElement = next(iter(response['result'].values()))

        ticker = self.url[self.url.rfind('=')+1:]
        result = {
            'ask': jsonElement['a'][0],
            'bid': jsonElement['b'][0],
            'quote': jsonElement['c'][0],
            'volume': jsonElement['v'][0],
            'vwap': jsonElement['p'][0],
            'timestamp': datetime.datetime.now(),
            'ticker': ticker,
            'currency': ticker[-3:],
        }

        return Quote(**result)
