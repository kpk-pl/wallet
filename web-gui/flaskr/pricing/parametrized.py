from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from flaskr import model


class ParametrizedQuoting:
    @dataclass
    class KeyPoint:
        timestamp: datetime
        multiplier: float


    @dataclass
    class Context:
        timePoint: datetime
        nextTimePoint: datetime
        interestIdx: int

        def __init__(self, quoting):
            self._quoting = quoting

            self.timePoint = quoting.startDate
            self.nextTimePoint = self.timePoint + self._quoting.interestPeriod
            self.interestIdx = 0

        def isPartial(self):
            return self.nextTimePoint > self._quoting.finalDate

        def interest(self):
            return self._quoting._params.interest[self.interestIdx]

        def advance(self):
            self.timePoint = self.nextTimePoint
            self.nextTimePoint += self._quoting.interestPeriod
            self.interestIdx = min(self.interestIdx + 1, len(self._quoting._params.interest) - 1)

        def fixedGrowth(self):
            percentage = float(self.interest().fixed.percentage)
            if not self.isPartial():
                return percentage

            return percentage * ((self._quoting.finalDate - self.timePoint).days / (self.nextTimePoint - self.timePoint).days)

        def derivedGrowth(self):
            pass


    def __init__(self, pricingParameters, startDate, finalDate = None):
        self.startDate = startDate
        self.finalDate = finalDate if finalDate != None else datetime.now();
        self._params = pricingParameters

        self._initPeriods()

    def _initPeriods(self):
        if self._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.day:
            self.interestPeriod = relativedelta(days=self._params.length.multiplier)
        elif self._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.month:
            self.interestPeriod = relativedelta(months=self._params.length.multiplier)
        elif self._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.year:
            self.interestPeriod = relativedelta(years=self._params.length.multiplier)

    def getKeyPoints(self):
        keyPoints = [self.KeyPoint(self.startDate, 1.0)]
        ctx = self.Context(self)

        while ctx.timePoint < self.finalDate:
            interest = ctx.interest()
            growth = 0.0

            if interest.fixed:
                growth += ctx.fixedGrowth()
            if interest.derived:
                growth += ctx.derivedGrowth()
                raise NotImplementedError("Did not implement calculating passed periods with derived pricing")

            keyPoints.append(self.KeyPoint(ctx.nextTimePoint, keyPoints[-1].multiplier * (1.0 + growth)));
            ctx.advance()

        return keyPoints
