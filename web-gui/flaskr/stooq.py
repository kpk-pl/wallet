from flask import json
import csv
from io import StringIO
import requests
import dateutil.parser

class Stooq(object):
    def __init__(self, ticker=None, url=None):
        super(Stooq, self).__init__()

        if ticker:
            self.ticker = ticker
        elif url:
            s = url.find('s=')
            end = url.find('&', s)
            if end == -1:
                end = len(url)
            self.ticker = url[s+2 : end]

    def name(self):
        url = f'https://stooq.pl/q/g/?s={self.ticker}'

        html = requests.get(url)
        html.encoding = html.apparent_encoding
        html = html.text

        marker = '>Ogólnie: '
        startPos = html.find(marker)
        endPos = html.find('<', startPos)

        result = html[startPos + len(marker) : endPos]

        if result.endswith(')'):
            result = result[:result.rfind('(') - 1]

        return result

    def quote(self):
        url = 'https://stooq.pl/q/l/?s={}&f=snd2t2c&h&e=json'.format(self.ticker)

        try:
            data = json.loads(requests.get(url).text)
        except:
            return None

        data = data['symbols'][0]
        data['timestamp'] = dateutil.parser.parse(data['date'] + ' ' + data['time'])

        return data

    def chart(self, timeRange = '3m'):
        url='https://stooq.pl/c/?p&s={}&c={}'.format(self.ticker, timeRange)
        return requests.get(url)

    def history(self, timeFrom, timeTo):
        url = f'https://stooq.pl/q/d/l/?s={self.ticker}&d1={timeFrom.year:04d}{timeFrom.month:02d}{timeFrom.day:02d}&d2={timeTo.year:04d}{timeTo.month:02d}{timeTo.day:02d}&i=d'

        csvIO = StringIO(requests.get(url).text)
        data = {}
        for entry in list(csv.reader(csvIO, delimiter=','))[1:]:
            d = dateutil.parser.parse(entry[0]).date()
            data[d] = {'open': entry[1], 'high': entry[2], 'low': entry[3], 'close': entry[4], 'volume': entry[5]}

        return data

    def assetAddData(self):
        q = self.quote()
        if q is None:
            return {}

        return {
            'quote': q['close'],
            'timestamp': q['timestamp'],
            'name': self.name(),
            'ticker': q['symbol']
        }
