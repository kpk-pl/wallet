from flaskr.pricing import Pricing, PricingContext
from dateutil.relativedelta import relativedelta
from . import _operationNetValue


class Period(object):
    def __init__(self, startDate, finalDate, debug=False):
        super(Period, self).__init__()

        self.startDate = startDate
        self.finalDate = finalDate
        self._debug = debug

        self.pricingStart = Pricing(ctx=PricingContext(finalDate=startDate))
        self.pricingEnd = Pricing(ctx=PricingContext(finalDate=finalDate))

    def __call__(self, asset):
        asset['_periodStats'] = {
            'profits': {
                'total': 0,
                'netValue': 0,
                'provisions': 0
            }
        }

        self._initialConditions(asset)
        self._finalConditions(asset)

        stats = asset['_periodStats']
        if stats['initialNetValue'] is None or stats['finalNetValue'] is None:
            stats['error'] = True
            return

        stats['profits']['total'] = stats['finalNetValue'] - stats['initialNetValue']

        operations = [op for op in asset['operations'] if op['date'] >= self.startDate and op['date'] <= self.finalDate]
        for operation in operations:
            self._operationToProfit(stats, operation)

    def _fromOperationId(self, asset):
        fromOperationId = -1
        while fromOperationId < len(asset['operations']) - 1:
            if asset['operations'][fromOperationId + 1]['date'] > self.startDate:
                break
            fromOperationId += 1

        return fromOperationId

    def _initialConditions(self, asset):
        stats = asset['_periodStats']
        debug = None
        if self._debug:
            stats['initialConditions'] = {}
            debug = stats['initialConditions']

        stats['initialNetValue'], stats['initialQuantity'] = self.pricingStart.priceAsset(asset, debug=debug)

    def _finalConditions(self, asset):
        stats = asset['_periodStats']
        debug = None
        if self._debug:
            stats['finalConditions'] = {}
            debug = stats['finalConditions']

        stats['finalNetValue'], stats['finalQuantity'] = self.pricingEnd.priceAsset(asset, debug=debug)

    def _operationToProfit(self, stats, operation):
        if operation['type'] == 'BUY':
            stats['profits']['total'] -= _operationNetValue(operation)
        elif operation['type'] == 'SELL':
            stats['profits']['total'] += _operationNetValue(operation)

        if 'profits' in operation['_stats']:
            stats['profits']['netValue'] += operation['_stats']['profits']['netValue']
            stats['profits']['provisions'] += operation['_stats']['profits']['provisions']

