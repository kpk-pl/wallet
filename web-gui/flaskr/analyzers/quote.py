import bisect
from datetime import timedelta

class Quote(object):
    CLOSE_DELTA = timedelta(days=3)

    def __init__(self, assetData, currencyQuotes):
        super(Quote, self).__init__()
        self.data = assetData
        self.currencyQuotes = currencyQuotes

    def __call__(self, timepoint, errors):
        value = Quote._findQuote(self.data['quoteHistory'], timepoint)
        if not value:
            errors.append({
                'type': 'asset',
                'assetName': self.data['ticker'] if 'ticker' in self.data else self.data['name'],
                'id': self.data['_id'],
                'timestamp': timepoint
            })
            return None

        if self.data['currency'] != 'PLN':
            conversion = Quote._findQuote(self.currencyQuotes[self.data['currency']]['quoteHistory'], timepoint)
            if not conversion:
                errors.append({
                    'type': 'currency',
                    'assetName': self.data['currency'],
                    'id': currencyQuotes[self.data['currency']]['_id'],
                    'timestamp': timepoint
                })
                return None

            value *= conversion

        return value

    def _findQuote(assetQuotes, timepoint):
        if not assetQuotes:
            return None

        timestamps = [a['timestamp'] for a in assetQuotes]
        idx = bisect.bisect_left(timestamps, timepoint)

        def isClose(a, b):
            return abs(a-b) < Quote.CLOSE_DELTA

        if idx == 0:
            return assetQuotes[0]['quote'] if isClose(timestamps[0], timepoint) else None

        if idx == len(timestamps):
            return assetQuotes[-1]['quote'] if isClose(timestamps[-1], timepoint) else None

        before = timestamps[idx - 1]
        after = timestamps[idx]
        if after - timepoint < timepoint - before:
            return assetQuotes[idx]['quote'] if isClose(timestamps[idx], timepoint) else None
        else:
            return assetQuotes[idx - 1]['quote'] if isClose(timestamps[idx - 1], timepoint) else None
