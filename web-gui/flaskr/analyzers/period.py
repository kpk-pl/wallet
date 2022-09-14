from flaskr.pricing import Pricing, Context
from flaskr.model import Asset, AssetOperation
from flaskr import typing
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass, field
from typing import Optional
from decimal import Decimal
from datetime import datetime
from .profits import Profits


# The Period analyzer calculates cumulative results in a set period of time based on the profits
# results from the Profits analyzer as well as market data
#
# The Period analyzer returns provisions and netProfit accumulated over the given period of time. Net profit minus
# provisions is the cash money out of the investment in the given period of time.
# Additionally totalNetProfit is calculated which accounts for initial and final market value of the investment
# as well as any changes in the invested ammount. Total net profit minus provisions is a theoretical capital gain
# on the investment in a given time period.
# The Period analyzer returns additionally initial and final market value of the asset, as well as initial
# and final quantity.

class Period(object):
    @dataclass
    class Result:
        @dataclass
        class Profits:
            # Asset value change within the selected timeframe with new investments deduced and cash profits added
            # That in general is finalNetValue - initialNetValue + totalNetProfit - totalNewInvestments
            # So final value with all new investments deduced, all new profits added and initial value substracted
            totalNetProfit: Decimal = field(default_factory=Decimal)
            # Total net profit from all operations in the defined time range
            netProfit: Decimal = field(default_factory=Decimal)
            # Total provisions in the defined time range
            provisions: Decimal = field(default_factory=Decimal)

            def isZero(self):
                return self.totalNetProfit == Decimal(0) and self.netProfit == Decimal(0) and self.provisions == Decimal(0)

        # Will be set to true when there is an error pricing an asset on startDate or finalDate
        error: bool = False

        initialNetValue: Optional[Decimal] = None
        initialQuantity: Optional[Decimal] = None

        finalNetValue: Optional[Decimal] = None
        finalQuantity: Optional[Decimal] = None

        profits: Profits = field(default_factory=Profits)


    def __init__(self, startDate:datetime, finalDate:datetime, db=None):
        super(Period, self).__init__()

        self.startDate = startDate
        self.finalDate = finalDate

        self._pricingStart = Pricing(ctx=Context(finalDate=startDate, db=db))
        self._pricingEnd = Pricing(ctx=Context(finalDate=finalDate, db=db))

    def __call__(self, asset:Asset, profitInfo:Profits, debug=None):
        self._result = self.Result()
        self._debug = debug if isinstance(debug, dict) else None

        self._initialConditions(asset)
        self._finalConditions(asset)

        if self._result.initialNetValue is None or self._result.finalNetValue is None:
            self._result.error = True
            return self._result

        self._result.profits.totalNetProfit = self._result.finalNetValue - self._result.initialNetValue

        initialNetInvestment = Decimal(0)
        finalNetInvestment = None
        for operation, operationProfit in zip(asset.operations, profitInfo.breakdown):
            if operation.date < self.startDate:
                initialNetInvestment = operationProfit.netInvestment
            elif operation.date >= self.startDate and operation.date < self.finalDate:
                # Only operations in scope
                self._operationToProfit(operation, operationProfit)
                finalNetInvestment = operationProfit.netInvestment
            else:
                pass

        if finalNetInvestment is None:
            # there was no operation in scope
            finalNetInvestment = initialNetInvestment

        self._result.profits.totalNetProfit -= (finalNetInvestment - initialNetInvestment)

        if self._debug is not None:
            self._debug['initialNetInvestment'] = initialNetInvestment
            self._debug['finalNetInvestment'] = finalNetInvestment

            from dataclasses import asdict
            self._debug['result'] = asdict(self._result)

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

    def _operationToProfit(self, operation:AssetOperation, operationProfit:Profits.Result.Breakdown):
        self._result.profits.netProfit += operationProfit.netProfit
        self._result.profits.provisions += operation.provision
        self._result.profits.totalNetProfit += operationProfit.netProfit
