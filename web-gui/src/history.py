import requests
import json
import time

def _getHistoryBiznesradar(desc, unixFrom, unixTo):
    url = 'https://www.biznesradar.pl/get-quotes-json/'

    ts = int(time.time())
    SECS_IN_DAY = 60*60*24
    if unixFrom >= ts-(365/2)*SECS_IN_DAY:
        rng = '6m'
    elif unixFrom >= ts-365*SECS_IN_DAY:
        rng = '1r'
    elif unixFrom >= ts-3*365*SECS_IN_DAY:
        rng = '3l'
    elif unixFrom >= ts-5*365*SECS_IN_DAY:
        rng = '5l'
    else:
        rng = 'max'

    print(rng)

    data = {'oid': desc['id'], 'range': rng, 'type': 'lin', 'without_operations': 0, 'currency_exchange': 0}
    headers = {'Accept': 'application/json, text/javascript, */*; q=0.01',
               'X-Requested-With': 'XMLHttpRequest'}

    response = requests.post(url, data=data, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(response)

    response = json.loads(response.text)
    if response['error'] != 0:
        raise RuntimeError("Response contains error: {}".format(response['error']))

    return {quote['ts']: quote['c'] for quote in response['data'][0]['quotes']}


def _getHistoryInvesting(desc, unixFrom, unixTo):
    timestamp = int(time.time())
    url = 'https://tvc4.forexpros.com/{}/{}/1/1/8/history'.format(desc['hash'], timestamp)
    params = {'symbol': desc['symbol'], 'resolution': 'D', 'from': unixFrom, 'to': unixTo}
    headers = {"User-Agent" : "Mozilla/5.0"}

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(response)

    response = json.loads(response.text)
    if response['s'] != 'ok':
        raise RuntimeError("Response contains error: {}".format(response['s']))

    return {response['t'][i]: response['c'][i] for i in range(len(response['t']))}


def getHistory(desc, unixFrom, unixTo):
    if desc['source'] == 'biznesradar':
        return _getHistoryBiznesradar(desc, unixFrom, unixTo)
    elif desc['source'] == 'investing':
        return _getHistoryInvesting(desc, unixFrom, unixTo)
