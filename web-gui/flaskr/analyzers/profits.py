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

    def avgPrice(self):
        return self.price / self.quantity if self.quantity else 0

    def avgNetPrice(self):
        return self.netPrice / self.quantity if self.quantity else 0

    def avgProvision(self):
        return self.provision / self.quantity if self.quantity else 0

    def partPrice(self, quantity):
        return self.price * quantity / self.quantity

    def partNetPrice(self, quantity):
        return self.netPrice * quantity / self.quantity

    def partProvision(self, quantity):
        return self.provision * quantity / self.quantity

    def scaleTo(self, quantity):
        self.price = self.price * quantity / self.quantity
        self.netPrice = self.netPrice * quantity / self.quantity
        self.provision = self.provision * quantity / self.quantity
        self.investment = self.investment * quantity / self.quantity
        self.quantity = quantity


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
                elif operation['type'] == 'EARNING':
                    self._earning(operation)
                else:
                    raise NotImplementedError("Did not implement profits for operation type {}" % (operation['type']))

                stats = operation['_stats']
                stats['averagePrice'] = self._running.avgPrice()
                stats['averageNetPrice'] = self._running.avgNetPrice()
                stats['averageProvision'] = self._running.avgProvision()

                self.currentQuantity = operation['finalQuantity']

        self.data['_averagePrice'] = self._running.avgPrice()
        self.data['_averageNetPrice'] = self._running.avgNetPrice()
        self.data['_averageProvision'] = self._running.avgProvision()
        self.data['_stillInvestedNetValue'] = self._running.investment

        if self.investmentStart is not None:
            self.data['_holdingDays'] = (datetime.now() - self.investmentStart).days

        return self.data

    def _buy(self, operation):
        self._running.quantity = operation['finalQuantity']
        self._running.price += operation['price']
        self._running.netPrice += _operationNetValue(operation)
        self._running.investment += _operationNetValue(operation)
        self._running.provision += _valueOr(operation, 'provision', 0)

        if self.investmentStart is None:
            self.investmentStart = operation['date']

    # a RECEIVE is essentially a BUY with a price 0
    def _receive(self, operation):
        self._running.quantity = operation['finalQuantity']
        self._running.provision += _valueOr(operation, 'provision', 0)

        if self.investmentStart is None:
            self.investmentStart = operation['date']

    def _sell(self, operation):
        quantity = operation['quantity']

        profits = {
            'value': operation['price'] - self._running.partPrice(quantity),
            'netValue': _operationNetValue(operation) - self._running.partNetPrice(quantity),
            'provisions': _valueOr(operation, 'provision', 0.0) + self._running.partProvision(quantity)
        }
        operation['_stats']['profits'] = profits

        self._running.scaleTo(operation['finalQuantity'])

        self.totalProfits['value'] += profits['value']
        self.totalProfits['netValue'] += profits['netValue']
        self.totalProfits['provisions'] += profits['provisions']

        if operation['finalQuantity'] == 0:
            self.investmentStart = None

    def _earning(self, operation):
        profits = {
            'value': operation['price'],
            'netValue': operation['price'] * _valueOr(operation, 'currencyConversion', 1.0),
            'provisions': _valueOr(operation, 'provision', 0.0)
        }
        operation['_stats']['profits'] = profits

        self.totalProfits['value'] += profits['value']
        self.totalProfits['netValue'] += profits['netValue']
        self.totalProfits['provisions'] += profits['provisions']
