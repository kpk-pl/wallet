from dateutil.relativedelta import relativedelta
from .quote import Quote
from . import _operationNetValue

class Period(object):
    def __init__(self, assetData, currencyQuotes):
        super(Period, self).__init__()
        self.data = assetData
        self.currencyQuotes = currencyQuotes

        self.operations = self.data['operations']

        self._quoteAnalyzer = Quote(self.data, self.currencyQuotes)

    def calc(self, periodFrom, periodTo):
        fromOperationId = self._fromOperationId(periodFrom)

        self.data['_periodStats'] = {
            'firstOperation': fromOperationId + 1,
            'errors': []
        }
        self.stats = self.data['_periodStats']

        self._initialConditions(fromOperationId, periodFrom + relativedelta(hours=12))
        self._finalConditions(periodTo - relativedelta(hours=12))

        self.stats['profits'] = {
            'netValue': 0,
            'quoteValue': 0,
            'provisions': 0
        }

        if len(self.stats['errors']) == 0:
            self.stats['profits']['quoteValue'] = self.stats['finalNetValue'] - self.stats['initialNetValue']

        for operation in self.data['operations'][self.stats['firstOperation'] : ]:
            self._operationToProfit(operation)

        return self.data

    def _fromOperationId(self, periodFrom):
        fromOperationId = -1
        while fromOperationId < len(self.operations) - 1:
            if self.operations[fromOperationId + 1]['date'] > periodFrom:
                break
            fromOperationId += 1

        return fromOperationId

    def _initialConditions(self, fromOperationId, periodFrom):
        if fromOperationId < 0:  # asset has been initialized in the checked period, so it is a new asset
            self.stats['initialQuantity'] = 0
            self.stats['initialNetValue'] = 0
        else:  # asset existed before the checked period
            self.stats['initialQuantity'] = self.operations[fromOperationId]['finalQuantity']
            quote = self._quoteAnalyzer(periodFrom, self.stats['errors'])
            if quote is not None:
                self.stats['initialNetValue'] = self.stats['initialQuantity'] * quote

    def _finalConditions(self, periodTo):
        self.stats['finalQuantity'] = self.operations[-1]['finalQuantity']
        if self.stats['finalQuantity'] > 0:
            finalQuote = self._quoteAnalyzer(periodTo, self.stats['errors'])
            if finalQuote is not None:
                self.stats['finalNetValue'] = self.stats['finalQuantity'] * finalQuote
        else:
            self.stats['finalNetValue'] = 0

    def _operationToProfit(self, operation):
        if operation['type'] == 'BUY':
            self.stats['profits']['quoteValue'] -= _operationNetValue(operation)
        elif operation['type'] == 'SELL':
            self.stats['profits']['quoteValue'] += _operationNetValue(operation)

        if 'profits' in operation['_stats']:
            self.stats['profits']['netValue'] += operation['_stats']['profits']['netValue']
            self.stats['profits']['provisions'] += operation['_stats']['profits']['provisions']

