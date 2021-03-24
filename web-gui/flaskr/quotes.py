from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests
from datetime import time, date, datetime
import dateutil.parser
import re
from flaskr.stooq import Stooq


def _getBiznesRadar(url):
    html = requests.get(url).text
    soup = BeautifulSoup(html, 'html.parser')

    result = {}

    quoteHtml = soup.find(id="pr_t_close")
    if quoteHtml:
        quoteHtml = quoteHtml.span
        if quoteHtml:
            result['quote'] = float(quoteHtml.string)


    timeHtml = soup.find(id="pr_t_date")
    if timeHtml:
        timeHtml = timeHtml.time
        if timeHtml:
            result['timestamp'] = dateutil.parser.parse(timeHtml['datetime'])

    headerHtml = soup.find(id="fullname-container")
    if headerHtml:
        nameHtml = headerHtml.h2
        if nameHtml:
            result['name'] = str(nameHtml.string)

    headerHtml = soup.find(id="profile-header")
    if headerHtml:
        nameHtml = headerHtml.h1
        if nameHtml:
            header = str(nameHtml.string)
            if header.startswith("Notowania "):
                result['ticker'] = header[10:header.find(' ', 10)]
            elif 'name' not in result.keys():
                result['name'] = header

    result['currency'] = "PLN"

    return result


def _investingNameHeader(nameHeader):
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

# TODO: Refactor this copy-paste hell
# TODO: Need to figure out some gracefull exception handling here when it's impossible to parse something
# because now the whole query just fails
def _getInvesting(url):
    result = {}
    if 'equities' in url:
        result['type'] = 'Equity'
    elif 'etfs' in url:
        result['type'] = 'ETF'

    html = requests.get(url, headers={"User-Agent" : "Mozilla/5.0"}).text
    soup = BeautifulSoup(html, 'html.parser')

    name = None
    ticker = None

    nameHeader = soup.select('.instrumentHead > h1')
    if len(nameHeader) > 0:
        name, ticker = _investingNameHeader(nameHeader[0].text)
    else:
        nameHeader = soup.select('h1[class*="instrument-header_title__"]')
        if len(nameHeader) > 0:
            name, ticker = _investingNameHeader(nameHeader[0].text)

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

    return result


# for the future maybe: https://www.quandl.com/
def getQuote(desc):
    if desc.startswith("https://pl.investing.com/"):
        return _getInvesting(desc)
    elif desc.startswith("https://www.biznesradar.pl/"):
        return _getBiznesRadar(desc)
    elif desc.startswith("https://stooq.pl/"):
        return Stooq(url = desc).assetAddData()
    else:
        return None
