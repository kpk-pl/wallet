from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests
import time
import datetime


def _getQuoteBR(ticker):
    url = "https://www.biznesradar.pl/notowania/{}".format(ticker)
    html = requests.get(url).text
    soup = BeautifulSoup(html, 'html.parser')

    return {
        'quote': float(soup.find(id="pr_t_close").span.string),
        'timestamp': int(time.time())
    }

def _getQuoteInvesting(ticker):
    url = "https://pl.investing.com/{}".format(ticker)
    html = requests.get(url, headers={"User-Agent" : "Mozilla/5.0"}).text
    soup = BeautifulSoup(html, 'html.parser')

    quote = soup.find(id="last_last")

    return {
        'quote': float(quote.string.replace(".", "").replace(",", '.')),
        'timestamp': int(time.time())
    }

def getQuote(desc):
    if desc['source'] == "biznesradar":
        return _getQuoteBR(desc['ticker'])
    elif desc['source'] == "investing":
        return _getQuoteInvesting(desc['ticker'])
    elif desc['source'] == 'identity':
        return {'quote': 1.0, 'timestamp': int(time.time())}
    else:
        return None
