# The profits analyzer takes an asset and its operations to calculate profits taken from each of them.
# If a BUY operation is followed by a SELL operation, this means that there is profit taken proportional to the
# quantity bought and sold and its prices. The EARNING and RECEIVE operations are also taken into account


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
    quantity: Decimal = Decimal(0)
    price: Decimal = Decimal(0)
    netPrice: Decimal = Decimal(0)
    investment: Decimal = Decimal(0)
    provision: Decimal = Decimal(0)

    def avgPrice(self) -> Decimal:
        return self.price / self.quantity if self.quantity else Decimal(0)

    def avgNetPrice(self) -> Decimal:
        return self.netPrice / self.quantity if self.quantity else Decimal(0)

    def avgProvision(self) -> Decimal:
        return self.provision / self.quantity if self.quantity else Decimal(0)

    def partPrice(self, quantity) -> Decimal:
        return self.price * quantity / self.quantity

    def partNetPrice(self, quantity) -> Decimal:
        return self.netPrice * quantity / self.quantity

    def partProvision(self, quantity) -> Decimal:
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
            @dataclass
            class MatchingOpenPosition:
                operation: model.AssetOperation = field()
                quantity: Decimal = field(default_factory=Decimal)

            # Profit taken on a single operation, in native currency
            profit: Decimal = field(default_factory=Decimal)
            # Profit taken on a single operation adjusted with currency conversion rate, in default currency
            netProfit: Decimal = field(default_factory=Decimal)
            # Provisions realised with the profit taken, in default currency. For SELL operation this will be the operation provisions summed with previous BUY provision for the sold quantity
            provisions: Decimal = field(default_factory=Decimal)
            # Current average price up to this operation, in native currency
            avgPrice: Decimal = field(default_factory=Decimal)
            # Current average price up to this operation adjusted with currency conversion rate, in default currency
            avgNetPrice: Decimal = field(default_factory=Decimal)
            # Current investment up to this operation, in default currency
            netInvestment: Decimal = field(default_factory=Decimal)
            # Current quantity up to this operation
            quantity: Decimal = field(default_factory=Decimal)
            # Remaining open quantity, for this operation only. If a BUY was completely matched by SELL, this will be 0
            # For some types of operation there is no remaining open quantity, in which case this is None
            remainingOpenQuantity: Optional[Decimal] = None
            # Matching open positions. For SELL operations this will list all open positions that were closed due to this operation
            matchingOpenPositions: List[MatchingOpenPosition] = field(default_factory=list)

        # Datetime when last time quantity increased from 0 to some value
        # Is None when the current quantity is 0
        investmentStart: Optional[datetime] = None
        # Number of days since investmentStart
        holdingDays: Optional[int] = None

        breakdown: List[Breakdown] = field(default_factory=list)

        # Total profit taken on the asset in native currency
        profit: Decimal = field(default_factory=Decimal)
        # Total net profit (profit adjusted with currency conversion) taken on an asset in default currency
        netProfit: Decimal = field(default_factory=Decimal)
        # Total provisions from all operations
        provisions: Decimal = field(default_factory=Decimal)

        # Last average price in native currency. Average price multiplied by last quantity yields current investment
        avgPrice: Optional[Decimal] = None
        # Last average price in default currency
        avgNetPrice: Optional[Decimal] = None
        # Last quantity
        quantity: Decimal = field(default_factory=Decimal)

    def __init__(self, currentDate = datetime.now()):
        self._currentDate = currentDate

    def __call__(self, asset:model.Asset, debug=None):
        self._result = self.Result()
        self._running = RunningTotals()
        self._operations = asset.operations
        self._debug = debug if isinstance(debug, dict) else None
        # if isinstance(debug, dict):
            # debug.update(asdict(self._data))

        if self._debug is not None:
            self._debug["running"] = []

        for operation in asset.operations:
            if operation.type is model.AssetOperationType.buy:
                breakdown = self._buy(operation, asset.type)
            elif operation.type is model.AssetOperationType.sell:
                breakdown = self._sell(operation, asset.type)
            elif operation.type is model.AssetOperationType.receive:
                breakdown = self._receive(operation, asset.type)
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
            self._result.holdingDays = (self._currentDate - self._result.investmentStart).days

        if self._debug is not None:
            self._debug["result"] = asdict(self._result)

        return self._result

    def _buy(self, operation:model.AssetOperation, assetType:model.AssetType):
        breakdown = self.Result.Breakdown()

        assert isinstance(operation.quantity, Decimal)
        assert self._running.quantity + operation.quantity == operation.finalQuantity

        self._running.quantity = operation.finalQuantity
        self._running.price += operation.price
        self._running.netPrice += operation.price * _valueOr(operation.currencyConversion, Decimal(1))
        self._running.investment += operation.price * _valueOr(operation.currencyConversion, Decimal(1))

        if assetType == model.AssetType.deposit:
            breakdown.provisions = _valueOr(operation.provision, Decimal(0))
        else:
            self._running.provision += _valueOr(operation.provision, Decimal(0))

        breakdown.remainingOpenQuantity = operation.quantity

        if self._result.investmentStart is None:
            self._result.investmentStart = operation.date

        return breakdown

    # a RECEIVE is essentially a BUY with a price 0
    def _receive(self, operation:model.AssetOperation, assetType:model.AssetType):
        breakdown = self.Result.Breakdown()

        assert assetType != model.AssetType.deposit
        assert isinstance(operation.quantity, Decimal)
        assert self._running.quantity + operation.quantity == operation.finalQuantity

        self._running.quantity = operation.finalQuantity
        self._running.provision += _valueOr(operation.provision, Decimal(0))

        breakdown.remainingOpenQuantity = operation.quantity

        if self._result.investmentStart is None:
            self._result.investmentStart = operation.date

        return breakdown

    def _sell(self, operation:model.AssetOperation, assetType:model.AssetType):
        breakdown = self.Result.Breakdown()
        quantity = operation.quantity

        assert isinstance(quantity, Decimal)
        assert self._running.quantity - quantity == operation.finalQuantity

        breakdown.profit = operation.price - self._running.partPrice(quantity)
        breakdown.netProfit =  operation.price * _valueOr(operation.currencyConversion, Decimal(1)) - self._running.partNetPrice(quantity)
        breakdown.provisions = _valueOr(operation.provision, Decimal(0)) + self._running.partProvision(quantity)

        self._running.scaleTo(operation.finalQuantity)

        for precedingBreakdown, precedingOperation in zip(self._result.breakdown, self._operations):
            if precedingBreakdown.remainingOpenQuantity is not None:
                closingQuantity = min(precedingBreakdown.remainingOpenQuantity, quantity)
                if closingQuantity > 0:
                    breakdown.matchingOpenPositions.append(self.Result.Breakdown.MatchingOpenPosition(operation=precedingOperation, quantity=closingQuantity))
                    precedingBreakdown.remainingOpenQuantity -= closingQuantity
                    quantity -= closingQuantity
                    if quantity == Decimal(0):
                        break

        assert quantity == Decimal(0)

        if operation.finalQuantity == 0:
            self._result.investmentStart = None

        return breakdown

    def _earning(self, operation:model.AssetOperation, assetType:model.AssetType):
        breakdown = self.Result.Breakdown()

        if assetType == model.AssetType.deposit:
            assert isinstance(operation.quantity, Decimal)
            assert self._running.quantity + operation.quantity == operation.finalQuantity

            self._running.quantity = operation.finalQuantity
            self._running.price += operation.price
            self._running.netPrice += operation.price * _valueOr(operation.currencyConversion, Decimal(1))
            self._running.investment += operation.price * _valueOr(operation.currencyConversion, Decimal(1))

            breakdown.remainingOpenQuantity = operation.price
        else:
            assert self._running.quantity == operation.finalQuantity

        breakdown.profit = operation.price
        breakdown.netProfit =  operation.price * _valueOr(operation.currencyConversion, Decimal(1))
        breakdown.provisions = _valueOr(operation.provision, Decimal(0))

        if self._result.investmentStart is None:
            self._result.investmentStart = operation.date

        return breakdown
