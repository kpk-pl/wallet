from ..model import Quote
from .base import BaseFetcher, FetchError
import dateutil.parser
from bs4 import BeautifulSoup
import requests


class MarketWatch(BaseFetcher):
    @staticmethod
    def validUrl(url):
        return url.startswith("https://www.marketwatch.com/")

    def __init__(self, url):
        super(MarketWatch, self).__init__(url)

    def fetch(self):
        html = requests.get(self.url, headers={"User-Agent" : "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, 'html.parser')

        result = {}

        nameHtml = soup.select('h1[class*="company__name"]')
        if len(nameHtml) > 0:
            result['name'] = nameHtml[0].text

        tickerHtml = soup.select('span[class*="company__ticker"]')
        if len(tickerHtml) > 0:
            result['ticker'] = tickerHtml[0].text

        quoteHtml = soup.select('h2[class*="intraday__price"]')
        if len(quoteHtml) > 0:
            currencySymbol = quoteHtml[0].select('sup')
            if len(currencySymbol) > 0:
                currencySymbol = currencySymbol[0].text
                if currencySymbol == '€':
                    result['currency'] = 'EUR'
                elif currencySymbol == '$':
                    result['currency'] = 'USD'
                elif currencySymbol == 'p':
                    result['currency'] = 'GBX'
            quote = quoteHtml[0].select('quote-bg')
            if len(quote) > 0:
                result['quote'] = float(quote[0].text)
            else:
                quote = quoteHtml[0].select('span[class*="value"]')
                if len(quote) > 0:
                    result['quote'] = float(quote[0].text.replace(',', ''))

        timeHtml = soup.select('div[class*="intraday__timestamp"] > span[class*="timestamp__time"] > bg-quote')
        if len(timeHtml):
            text = timeHtml[0].text
            result['timestamp'] = dateutil.parser.parse(text[: text.rfind(' ')])

        return Quote(**result)
