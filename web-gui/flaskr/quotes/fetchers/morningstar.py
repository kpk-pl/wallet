from ..model import Quote
from .base import BaseFetcher, FetchError
from datetime import date, time, datetime
from bs4 import BeautifulSoup
import requests
import re


class Morningstar(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("https://www.morningstar.co.uk/")

    def __init__(self, url):
        super(Morningstar, self).__init__(url)

    def fetch(self):
        result = {}
        if 'etf' in self.url:
            result['type'] = 'ETF'

        html = requests.get(self.url, headers={"User-Agent" : "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, 'html.parser')

        name = soup.select('.snapshotTitleBox > h1')
        if name:
            assetName, ticker = name[0].text.split('|')
            result['name'] = assetName.strip()
            result['ticker'] = ticker.strip()

        table = soup.select('.overviewKeyStatsTable')
        if not table:
            return Quote(**result)

        closingPrice = table[0].find_all(string="Closing Price")
        if closingPrice:
            date = closingPrice[0].parent.select("span.heading")[0].text
            dateParsed = datetime.strptime(date, "%d/%m/%Y")
            result['timestamp'] = datetime.combine(dateParsed, time(17))

            currency, quote = closingPrice[0].parent.parent.select("td.text")[0].text.split()
            result['quote'] = float(quote)
            result['currency'] = currency

        return Quote(**result)

