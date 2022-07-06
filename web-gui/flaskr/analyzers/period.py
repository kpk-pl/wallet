from flaskr.pricing import Pricing, Context
from flaskr import typing
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, field
from typing import Optional
from decimal import Decimal


class Period(object):
    @dataclass
    class Result:
        @dataclass
        class Profits:
            total: Decimal = field(default_factory=Decimal)
            netValue: Decimal = field(default_factory=Decimal)
            provisions: Decimal = field(default_factory=Decimal)

        error: bool = False

        initialNetValue: Optional[Decimal] = None
        initialQuantity: Optional[Decimal] = None

        finalNetValue: Optional[Decimal] = None
        finalQuantity: Optional[Decimal] = None

        profits: Profits = field(default_factory=Profits)


    def __init__(self, startDate, finalDate):
        super(Period, self).__init__()

        self.startDate = startDate
        self.finalDate = finalDate

        self._pricingStart = Pricing(ctx=Context(finalDate=startDate))
        self._pricingEnd = Pricing(ctx=Context(finalDate=finalDate))

    def __call__(self, asset, profitInfo, debug=None):
        self._result = self.Result()
        self._debug = debug if isinstance(debug, dict) else None

        self._initialConditions(asset)
        self._finalConditions(asset)

        if self._result.initialNetValue is None or self._result.finalNetValue is None:
            self._result.error = True
            return self._result

        self._result.profits.total = self._result.finalNetValue - self._result.initialNetValue

        operationScope = [(op,info) for op, info in zip(asset.operations, profitInfo.breakdown) \
                          if op.date >= self.startDate and op.date <= self.finalDate]
        for operation, operationProfit in operationScope:
            self._operationToProfit(operation, operationProfit)

        return self._result

    def _initialConditions(self, asset):
        if self._debug is not None:
            self._debug['initialConditions'] = {}

        debug = self._debug['initialConditions'] if self._debug else None
        self._result.initialNetValue, self._result.initialQuantity = self._pricingStart(asset, debug=debug)

    def _finalConditions(self, asset):
        if self._debug is not None:
            self._debug['finalConditions'] = {}

        debug = self._debug['finalConditions'] if self._debug else None
        self._result.finalNetValue, self._result.finalQuantity = self._pricingEnd(asset, debug=debug)

    def _operationToProfit(self, operation, operationProfit):
        def _operationNetValue(operation):
            if operation.currencyConversion:
                return operation.price * operation.currencyConversion
            return operation.price

        if operation.type == typing.Operation.Type.buy:
            self._result.profits.total -= _operationNetValue(operation)
        elif operation.type == typing.Operation.Type.sell:
            self._result.profits.total += _operationNetValue(operation)
        elif operation.type == typing.Operation.Type.receive:
            self._result.profits.total += _operationNetValue(operation)
        elif operation.type == typing.Operation.Type.earning:
            self._result.profits.total += _operationNetValue(operation)
        else:
            raise NotImplementedError("Did not implement period for operation type {}" % (operation.type))

        self._result.profits.netValue += operationProfit.netProfit
        self._result.profits.provisions += operationProfit.provisions

