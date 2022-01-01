from flaskr.pricing import Pricing, Context
from flaskr import typing
from dateutil.relativedelta import relativedelta
from . import _operationNetValue


class Period(object):
    def __init__(self, startDate, finalDate, debug=False):
        super(Period, self).__init__()

        self.startDate = startDate
        self.finalDate = finalDate
        self._debug = debug

        self.pricingStart = Pricing(ctx=Context(finalDate=startDate))
        self.pricingEnd = Pricing(ctx=Context(finalDate=finalDate))

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

        stats['initialNetValue'], stats['initialQuantity'] = self.pricingStart(asset, debug=debug)

    def _finalConditions(self, asset):
        stats = asset['_periodStats']
        debug = None
        if self._debug:
            stats['finalConditions'] = {}
            debug = stats['finalConditions']

        stats['finalNetValue'], stats['finalQuantity'] = self.pricingEnd(asset, debug=debug)

    def _operationToProfit(self, stats, operation):
        if operation['type'] == typing.Operation.Type.buy:
            stats['profits']['total'] -= _operationNetValue(operation)
        elif operation['type'] == typing.Operation.Type.sell:
            stats['profits']['total'] += _operationNetValue(operation)
        elif operation['type'] == typing.Operation.Type.receive:
            stats['profits']['total'] += _operationNetValue(operation)
        elif operation['type'] == typing.Operation.Type.earning:
            stats['profits']['total'] += _operationNetValue(operation)
        else:
            raise NotImplementedError("Did not implement period for operation type {}" % (operation['type']))

        if 'profits' in operation['_stats']:
            stats['profits']['netValue'] += operation['_stats']['profits']['netValue']
            stats['profits']['provisions'] += operation['_stats']['profits']['provisions']

