from ..model import Quote
from .base import BaseFetcher, FetchError
from bs4 import BeautifulSoup
import requests
import dateutil.parser
from decimal import Decimal


class BiznesRadar(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("https://www.biznesradar.pl/")

    def __init__(self, url):
        super(BiznesRadar, self).__init__(url)

    def fetch(self):
        html = requests.get(self.url).text
        soup = BeautifulSoup(html, 'html.parser')

        quoteValue = self._getQuote(soup)
        timestamp = self._getTimestamp(soup)
        name = self._getName(soup)
        ticker, alternateName = self._getTicker(soup)

        return Quote(quote = quoteValue, timestamp = timestamp, name = name or alternateName, currency = "PLN")

    def _getQuote(self, soup):
        quoteHtml = soup.find(id="pr_t_close")
        if not quoteHtml:
            raise FetchError(self.url, "Cannot find quote tag")

        if not quoteHtml.span:
            raise BaseFetcher(self.url, "Cannot recognize quote tag's content")

        return Decimal(quoteHtml.span.string)

    def _getTimestamp(self, soup):
        timeHtml = soup.find(id="pr_t_date")
        if not timeHtml:
            raise FetchError(self.url, "Cannot find timestamp tag")

        if not timeHtml.time:
            raise FetchError(self.url, "Cannot recognize timestamp tag's content")

        return dateutil.parser.parse(timeHtml.time['datetime'])

    def _getName(self, soup):
        headerHtml = soup.find(id="fullname-container")

        if not headerHtml:
            return None

        if not headerHtml.h2:
            return None

        return str(headerHtml.h2.string)

    def _getTicker(self, soup):
        headerHtml = soup.find(id="profile-header")
        if not headerHtml or not headerHtml.h1:
            return None, None

        header = str(headerHtml.h1.string)
        if header.startswith("Notowania "):
            return header[10:header.find(' ', 10)], None
        else:
            return None, header
