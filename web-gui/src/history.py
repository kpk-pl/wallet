import requests
import json
import time
import re

def _getHistoryBiznesradar(url):
    html = requests.get(url).text
    oid = re.search(r"{symbol_oid: (.*?)}", html)
    if not oid:
        return {}
    oid = oid.group(1)

    quotesUrl = 'https://www.biznesradar.pl/get-quotes-json/'
    data = {'oid': oid, 'range': 'max', 'type': 'lin', 'without_operations': 0, 'currency_exchange': 0}
    headers = {'Accept': 'application/json, text/javascript, */*; q=0.01',
               'X-Requested-With': 'XMLHttpRequest'}

    response = requests.post(quotesUrl, data=data, headers=headers)
    if response.status_code != 200:
        return {}

    response = json.loads(response.text)
    if response['error'] != 0:
        {}

    return {quote['ts']: quote['c'] for quote in response['data'][0]['quotes']}


def _getHistoryInvesting(url):
    headers = {"User-Agent" : "Mozilla/5.0"}

    if '?' in url:
        pos = url.find('?')
        chartUrl = url[:pos] + '-chart' + url[pos:]
    else:
        chartUrl = url + '-chart'

    html = requests.get(chartUrl, headers=headers).text
    carrier = html.find('carrier=')
    carrier = html[carrier+8:carrier+40]

    timestamp = int(time.time())
    url = 'https://tvc4.forexpros.com/{}/{}/32/15/57/history'.format(carrier, timestamp)

    response = requests.get(url, headers=headers)
    print(response)
    if response.status_code != 200:
        raise RuntimeError(response)

    response = json.loads(response.text)
    if response['s'] != 'ok':
        raise RuntimeError("Response contains error: {}".format(response['s']))

    return {response['t'][i]: response['c'][i] for i in range(len(response['t']))}


def getHistory(desc):
    if desc.startswith("https://pl.investing.com/"):
        return _getHistoryInvesting(desc)
    elif desc.startswith("https://www.biznesradar.pl/"):
        return _getHistoryBiznesradar(desc)
    else:
        return {}
