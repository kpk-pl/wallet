from . import _operationNetValue, _valueOr
from datetime import datetime


class Profits(object):
    def __init__(self, assetData):
        super(Profits, self).__init__()
        self.data = assetData

        self.data['_totalProfits'] = {
            'value' : 0.0,
            'netValue' : 0.0,
            'provisions' : 0.0
        }

        self.totalProfits = self.data['_totalProfits']

        self.investmentStart = None
        self.averagePrice = 0.0
        self.averageNetPrice = 0.0
        self.averageProvision = 0.0
        self.currentQuantity = 0.0

    def __call__(self):
        if 'operations' in self.data:
            for operation in self.data['operations']:
                operation['_stats'] = {}

                if operation['type'] == 'BUY':
                    self._buy(operation)
                elif operation['type'] == 'SELL':
                    self._sell(operation)
                else:
                    raise NotImplementedError("Did not implement profits for operation type {}" % (operation['type']))

                stats = operation['_stats']
                stats['averagePrice'] = self.averagePrice
                stats['averageNetPrice'] = self.averageNetPrice
                stats['averageProvision'] = self.averageProvision

                self.currentQuantity = operation['finalQuantity']

        self.data['_averagePrice'] = self.averagePrice
        self.data['_averageNetPrice'] = self.averageNetPrice
        self.data['_averageProvision'] = self.averageProvision
        self.data['_stillInvestedNetValue'] = self.averageNetPrice * self.currentQuantity

        if self.investmentStart is not None:
            self.data['_holdingDays'] = (datetime.now() - self.investmentStart).days

        return self.data

    def _buy(self, operation):
        quantity = operation['quantity']
        finalQuantity = operation['finalQuantity']

        self.averagePrice = (self.averagePrice * self.currentQuantity + operation['price']) / finalQuantity
        self.averageNetPrice = (self.averageNetPrice * self.currentQuantity + _operationNetValue(operation)) / finalQuantity
        self.averageProvision = (self.averageProvision * self.currentQuantity + _valueOr(operation, 'provision', 0.0)) / finalQuantity

        if self.investmentStart is None:
            self.investmentStart = operation['date']

    def _sell(self, operation):
        quantity = operation['quantity']

        operation['_stats']['profits'] = {
            'value': operation['price'] - self.averagePrice * quantity,
            'netValue': _operationNetValue(operation) - self.averageNetPrice * quantity,
            'provisions': _valueOr(operation, 'provision', 0.0) + self.averageProvision * quantity
        }

        profits = operation['_stats']['profits']
        self.totalProfits['value'] += profits['value']
        self.totalProfits['netValue'] += profits['netValue']
        self.totalProfits['provisions'] += profits['provisions']

        if operation['finalQuantity'] == 0:
            self.averagePrice = 0.0
            self.averageNetPrice = 0.0
            self.averageProvision = 0.0
            self.investmentStart = None
