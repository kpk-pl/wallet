from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests
from datetime import time, date, datetime
import dateutil.parser
import re


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
            result['timestamp'] = dateutil.parser.parse(timeHtml['datetime']).timestamp()

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


def _getInvesting(url):
    result = {}
    if 'equities' in url:
        result['type'] = 'Equity'
    elif 'etfs' in url:
        result['type'] = 'ETF'

    nameTickerRe = re.compile(r"(.*?)\(([A-Z0-9]+)\)(?!.*\([A-Z0-9]+\))")
    html = requests.get(url, headers={"User-Agent" : "Mozilla/5.0"}).text
    soup = BeautifulSoup(html, 'html.parser')

    nameHeader = soup.select('.instrumentHead > h1')
    if len(nameHeader) > 0:
        nameHeader = nameHeader[0].text
        if nameHeader:
            nameHeader = nameHeader.strip()
            nameTickerMatch = nameTickerRe.fullmatch(nameHeader)
            if nameTickerMatch:
                if nameTickerMatch.group(1):
                    result['name'] = nameTickerMatch.group(1).strip()
                if nameTickerMatch.group(2):
                    result['ticker'] = nameTickerMatch.group(2).strip()
            else:
                result['name'] = nameHeader

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
                timeParsed = datetime.strptime(timeText, "%H:%M:%S")
                result['timestamp'] = datetime.combine(date.today(), timeParsed.time()).timestamp()

    return result


def getQuote(desc):
    if desc.startswith("https://pl.investing.com/"):
        return _getInvesting(desc)
    elif desc.startswith("https://www.biznesradar.pl/"):
        return _getBiznesRadar(desc)
    else:
        return None
