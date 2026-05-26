from ..model import Quote
from .base import BaseFetcher, FetchError
from datetime import datetime
import requests
import re


class JustETF(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("https://www.justetf.com/") and "isin=" in url

    def __init__(self, url):
        super(JustETF, self).__init__(url)

    def fetch(self):
        m = re.search(r'isin=([A-Z]{2}[A-Z0-9]{10})', self.url)
        if not m:
            raise FetchError(self.url, "Could not extract ISIN from URL")
        isin = m.group(1)

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
