from ..model import Quote
from .base import BaseFetcher, FetchError
from datetime import date, time, datetime
from bs4 import BeautifulSoup
import requests
import re


class Investing(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("https://pl.investing.com/")

    def __init__(self, url):
        super(Investing, self).__init__(url)

    def fetch(self):
        result = {}
        if 'equities' in self.url:
            result['type'] = 'Equity'
        elif 'etfs' in self.url:
            result['type'] = 'ETF'

        html = requests.get(self.url, headers={"User-Agent" : "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, 'html.parser')

        name = None
        ticker = None

        nameHeader = soup.select('.instrumentHead > h1')
        if len(nameHeader) > 0:
            name, ticker = self._getNameTicker(nameHeader[0].text)
        else:
            nameHeader = soup.select('h1[class*="instrument-header_title__"]')
            if len(nameHeader) > 0:
                name, ticker = self._getNameTicker(nameHeader[0].text)

        if name:
            result['name'] = name
        if ticker:
            result['ticker'] = ticker

        quoteNode = soup.find(id="last_last")
        if quoteNode:
            quoteText = quoteNode.string
            if quoteText:
                result['quote'] = float(quoteText.string.replace(".", "").replace(",", '.'))

            bottomSpans = quoteNode.parent.parent.select(".bottom > span")
            if len(bottomSpans) >= 4:
                result['currency'] = bottomSpans[3].text

            if len(bottomSpans) >= 2:
                timeText = bottomSpans[1].text
                if timeText:
                    if len(timeText) == 8:
                        timeParsed = datetime.strptime(timeText, "%H:%M:%S")
                        result['timestamp'] = datetime.combine(date.today(), timeParsed.time())
                    elif len(timeText) == 5:
                        timeParsed = datetime.strptime(timeText, "%d/%m")
                        result['timestamp'] = datetime.combine(timeParsed, time())
        else:
            quoteNode = soup.select('span[class*="instrument-price_last__"]')
            if len(quoteNode):
                result['quote'] = float(quoteNode[0].text.replace(".", "").replace(",", '.'))
            quoteCurrency = soup.select('div[class*="instrument-metadata_currency__"] > span')
            if len(quoteCurrency) >= 2:
                result['currency'] = quoteCurrency[1].text
            quoteTimestamp = soup.select('div[class*="instrument-metadata_time__"] > time')
            if len(quoteTimestamp):
                timeText = quoteTimestamp[0].text
                if timeText:
                    if len(timeText) == 8:
                        timeParsed = datetime.strptime(timeText, "%H:%M:%S")
                        result['timestamp'] = datetime.combine(date.today(), timeParsed.time())
                    elif len(timeText) == 5:
                        timeParsed = datetime.strptime(timeText, "%d/%m")
                        result['timestamp'] = datetime.combine(timeParsed, time())

        return Quote(**result)

    @staticmethod
    def _getNameTicker(nameHeader):
        nameTickerRe = re.compile(r"(.*?)\(([A-Z0-9]+)\)(?!.*\([A-Z0-9]+\))")

        name = None
        ticker = None

        if nameHeader:
            name = nameHeader.strip()
            nameTickerMatch = nameTickerRe.fullmatch(name)
            if nameTickerMatch:
                if nameTickerMatch.group(1):
                    name = nameTickerMatch.group(1).strip()
                if nameTickerMatch.group(2):
                    ticker = nameTickerMatch.group(2).strip()

        return name, ticker
