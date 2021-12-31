from . import _operationNetValue, _valueOr
from datetime import datetime
from dataclasses import dataclass


@dataclass
class RunningTotals:
    quantity: float = 0
    price: float = 0
    netPrice: float = 0
    investment: float = 0
    provision: float = 0


class Profits(object):
    def __init__(self, assetData):
        super(Profits, self).__init__()
        self.data = assetData
        self._running = RunningTotals()

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
                elif operation['type'] == 'RECEIVE':
                    self._receive(operation)
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
        finalQuantity = operation['finalQuantity']
        self._running.quantity = operation['finalQuantity']

        self.averagePrice = (self.averagePrice * self.currentQuantity + operation['price']) / finalQuantity
        self._running.price += operation['price']
        self.averageNetPrice = (self.averageNetPrice * self.currentQuantity + _operationNetValue(operation)) / finalQuantity
        self._running.netPrice += _operationNetValue(operation)
        self._running.investment += _operationNetValue(operation)
        self.averageProvision = (self.averageProvision * self.currentQuantity + _valueOr(operation, 'provision', 0.0)) / finalQuantity
        self._running.provision += _valueOr(operation, 'provision', 0)

        if self.investmentStart is None:
            self.investmentStart = operation['date']

    # a RECEIVE is essentially a BUY with a price 0
    def _receive(self, operation):
        finalQuantity = operation['finalQuantity']
        self._running.quantity = operation['finalQuantity']

        self.averagePrice = (self.averagePrice * self.currentQuantity) / finalQuantity
        self.averageNetPrice = (self.averageNetPrice * self.currentQuantity) / finalQuantity
        self.averageProvision = (self.averageProvision * self.currentQuantity + _valueOr(operation, 'provision', 0.0)) / finalQuantity
        self._running.provision += _valueOr(operation, 'provision', 0)

        if self.investmentStart is None:
            self.investmentStart = operation['date']

    def _sell(self, operation):
        quantity = operation['quantity']

        operation['_stats']['profits'] = {}
        profits = operation['_stats']['profits']

        profits = {
            'value': operation['price'] - self.averagePrice * quantity,
            'netValue': _operationNetValue(operation) - self.averageNetPrice * quantity,
            'provisions': _valueOr(operation, 'provision', 0.0) + self.averageProvision * quantity
        }

        self._running.price = self._running.price * (self._running.quantity - quantity) / self._running.quantity
        self._running.netPrice = self._running.netPrice * (self._running.quantity - quantity) / self._running.quantity
        self._running.provision = self._running.provision * (self._running.quantity - quantity) / self._running.quantity
        self._running.investment = self._running.investment * (self._running.quantity - quantity) / self._running.quantity
        self._running.quantity = operation['finalQuantity']

        self.totalProfits['value'] += profits['value']
        self.totalProfits['netValue'] += profits['netValue']
        self.totalProfits['provisions'] += profits['provisions']

        if operation['finalQuantity'] == 0:
            self.averagePrice = 0.0
            self.averageNetPrice = 0.0
            self.averageProvision = 0.0
            self.investmentStart = None
