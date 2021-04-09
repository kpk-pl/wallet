from datetime import datetime, timedelta
from . import _operationNetValue, _valueOr

class HistoricalValue(object):
    def __init__(self, assetData, currencyData):
        super(HistoricalValue, self).__init__()
        self.data = assetData
        self.currencyData = currencyData

    def __call__(self):
        ops = self.data['operations']
        quotes = self.data['quoteHistory']

        result = {'t': [], 'y': [], 'q': []}
        if not ops:
            return result

        now = datetime.now().date()
        day = timedelta(days=1)

        operationIdx = 0
        quoteIdx = 0
        currencyIdx = 0
        dateIdx = ops[0]['date'].date()

        quantity = 0
        quote = None
        currencyQuote = None

        while dateIdx < now:
            # If this is the day the next operation happened, take new quantity
            while operationIdx < len(ops) and ops[operationIdx]['date'].date() <= dateIdx:
                quantity = ops[operationIdx]['finalQuantity']
                operationIdx += 1

            while quoteIdx < len(quotes) and quotes[quoteIdx]['timestamp'].date() <= dateIdx:
                quote = quotes[quoteIdx]['quote']
                quoteIdx += 1

            if self.currencyData is not None:
                while currencyIdx < len(self.currencyData) and self.currencyData[currencyIdx]['timestamp'].date() <= dateIdx:
                    currencyQuote = self.currencyData[currencyIdx]['quote']
                    currencyIdx += 1

            value = quantity
            value = value * quote if quote is not None else None
            if self.currencyData is not None:
                value = value * currencyQuote if currencyQuote is not None else None

            result['t'].append(dateIdx)
            result['y'].append(value)
            result['q'].append(quantity)
            dateIdx += day

        return result
