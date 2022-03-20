from ..model import Quote
from .base import BaseFetcher, FetchError
import requests
from flask import json
import dateutil.parser


class Stooq(BaseFetcher):
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

    def fetch(self):
        url = 'https://stooq.pl/q/l/?s={}&f=snd2t2c&e=json'.format(self.symbol)

        try:
            data = json.loads(requests.get(url).text)
        except Exception as e:
            raise FetchError(url, e)

        data = data['symbols'][0]
        # Here is a potential error, when the symbol is incorrect the api returns just the 'symbol' field
        timestamp = dateutil.parser.parse(data['date'] + ' ' + data['time'])

        return Quote(quote = data['close'], timestamp=timestamp, ticker=self.symbol, name = data['name'])
