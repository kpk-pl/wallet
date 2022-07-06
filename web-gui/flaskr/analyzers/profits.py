# The profits analyzer takes an asset and its operations to calculate profits taken from each of them.
# If a BUY operation is followed by a SELL operation, this means that there is profit taken proportional to the
# quantity bought and sold and its prices. The EARNING and RECEIVE operations are also taken into account


from . import _operationNetValue
from datetime import datetime
from dataclasses import dataclass, field, asdict
import flaskr.model as model
from decimal import Decimal
from typing import List, Optional


def _valueOr(value, default):
    if value is not None:
        return value
    return default


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


class Profits:
    @dataclass
    class Result:
        @dataclass
        class Breakdown:
            profit: Decimal = field(default_factory=Decimal)
            netProfit: Decimal = field(default_factory=Decimal)
            provisions: Decimal = field(default_factory=Decimal)
            avgPrice: Decimal = field(default_factory=Decimal)
            avgNetPrice: Decimal = field(default_factory=Decimal)
            netInvestment: Decimal = field(default_factory=Decimal)
            quantity: Decimal = field(default_factory=Decimal)

        investmentStart: Optional[datetime] = None
        holdingDays: Optional[int] = None

        breakdown: List[Breakdown] = field(default_factory=list)

        profit: Decimal = field(default_factory=Decimal)
        netProfit: Decimal = field(default_factory=Decimal)
        provisions: Decimal = field(default_factory=Decimal)
        avgPrice: Optional[Decimal] = None
        avgNetPrice: Optional[Decimal] = None
        quantity: Decimal = field(default_factory=Decimal)

    def __init__(self):
        pass

    def __call__(self, asset:model.Asset, debug=None):
        self._result = self.Result()
        self._running = RunningTotals()
        self._debug = debug if isinstance(debug, dict) else None
        # if isinstance(debug, dict):
            # debug.update(asdict(self._data))

        if self._debug is not None:
            self._debug["running"] = []

        for operation in asset.operations:
            if operation.type is model.AssetOperationType.buy:
                breakdown = self._buy(operation)
            elif operation.type is model.AssetOperationType.sell:
                breakdown = self._sell(operation)
            elif operation.type is model.AssetOperationType.receive:
                breakdown = self._receive(operation)
            elif operation.type is model.AssetOperationType.earning:
                breakdown = self._earning(operation, asset.type)
            else:
                raise NotImplementedError("Did not implement profits for operation type {}" % (operation.type))

            breakdown.avgPrice = self._running.avgPrice()
            breakdown.avgNetPrice = self._running.avgNetPrice()
            breakdown.netInvestment = self._running.investment
            breakdown.quantity = self._running.quantity

            self._result.breakdown.append(breakdown)

            if self._debug is not None:
                self._debug["running"].append(asdict(self._running))

        if self._result.breakdown:
            self._result.profit = sum([b.profit for b in self._result.breakdown])
            self._result.netProfit = sum([b.netProfit for b in self._result.breakdown])
            self._result.provisions = sum([b.provisions for b in self._result.breakdown]) + self._running.provision
            self._result.avgPrice = self._result.breakdown[-1].avgPrice
            self._result.avgNetPrice = self._result.breakdown[-1].avgNetPrice
            self._result.quantity = self._result.breakdown[-1].quantity

        if self._result.investmentStart is not None:
            self._result.holdingDays = (datetime.now() - self._result.investmentStart).days

        return self._result

    def _buy(self, operation):
        breakdown = self.Result.Breakdown()

        assert self._running.quantity + operation.quantity == operation.finalQuantity

        self._running.quantity = operation.finalQuantity
        self._running.price += operation.price
        self._running.netPrice += operation.price * _valueOr(operation.currencyConversion, Decimal(1))
        self._running.investment += operation.price * _valueOr(operation.currencyConversion, Decimal(1))
        self._running.provision += _valueOr(operation.provision, Decimal(0))

        if self._result.investmentStart is None:
            self._result.investmentStart = operation.date

        return breakdown

    # a RECEIVE is essentially a BUY with a price 0
    def _receive(self, operation):
        breakdown = self.Result.Breakdown()

        assert self._running.quantity + operation.quantity == operation.finalQuantity

        self._running.quantity = operation.finalQuantity
        self._running.provision += _valueOr(operation.provision, Decimal(0))

        if self._result.investmentStart is None:
            self._result.investmentStart = operation.date

        return breakdown

    def _sell(self, operation):
        breakdown = self.Result.Breakdown()
        quantity = operation.quantity

        assert self._running.quantity - operation.quantity == operation.finalQuantity

        breakdown.profit = operation.price - self._running.partPrice(quantity)
        breakdown.netProfit =  operation.price * _valueOr(operation.currencyConversion, Decimal(1)) - self._running.partNetPrice(quantity)
        breakdown.provisions = _valueOr(operation.provision, Decimal(0)) + self._running.partProvision(quantity)

        self._running.scaleTo(operation.finalQuantity)

        if operation.finalQuantity == 0:
            self._result.investmentStart = None

        return breakdown

    def _earning(self, operation, assetType):
        breakdown = self.Result.Breakdown()

        if assetType == 'Deposit':
            assert self._running.quantity + operation.quantity == operation.finalQuantity

            self._running.quantity = operation.finalQuantity
        else:
            assert self._running.quantity == operation.finalQuantity

        breakdown.profit = operation.price
        breakdown.netProfit =  operation.price * _valueOr(operation.currencyConversion, Decimal(1))
        breakdown.provisions = _valueOr(operation.provision, Decimal(0))

        if self._result.investmentStart is None:
            self._result.investmentStart = operation.date

        return breakdown
