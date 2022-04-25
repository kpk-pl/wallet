from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from decimal import Decimal
from flaskr import model


class ParametrizedQuoting:
    @dataclass
    class KeyPoint:
        timestamp: datetime
        multiplier: Decimal


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
            percentage = self.interest().fixed.percentage
            if not self.isPartial():
                return percentage

            passedDays = (self._quoting.finalDate - self.timePoint).days
            periodDays = (self.nextTimePoint - self.timePoint).days
            return percentage * Decimal(passedDays) / Decimal(periodDays)

        def derivedGrowth(self):
            thisInterest = self.interest().derived
            quoteTimestamp = datetime(self.nextTimePoint.year, self.nextTimePoint.month, self.nextTimePoint.day)

            if thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.year:
                intervalDelta = relativedelta(years=1)
                quoteTimestamp = quoteTimestamp.replace(day=1, month=1) + relativedelta(years=thisInterest.sample.intervalOffset)
            elif thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.month:
                intervalDelta = relativedelta(months=1)
                quoteTimestamp = quoteTimestamp.replace(day=1) + relativedelta(months=thisInterest.sample.intervalOffset)
            elif thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.day:
                intervalDelta = relativedelta(days=1)
                quoteTimestamp += relativedelta(days=thisInterest.sample.intervalOffset)

            self._quoting._pricingCtx.loadQuotes(thisInterest.quoteId)

            if thisInterest.sample.choose == model.assetPricing.AsserPricingParametrizedInterestItemDerivedSampleChoose.last:
                result = self._quoting._pricingCtx.getPreviousById(thisInterest.quoteId, quoteTimestamp)
            elif thisInterest.sample.choose == model.AssetPricing.AsserPricingParametrizedInterestItemDerivedSampleChoose.first:
                result = self._quoting._pricingCtx.getNextById(thisInterest.quoteId, quoteTimestamp - intervalDelta)

            if result is None:
                return result

            result *= thisInterest.sample.multiplier
            result = max(thisInterest.sample.clampBelow, result)

            return result


    def __init__(self, pricingParameters, startDate, pricingCtx):
        self._params = pricingParameters
        self._pricingCtx = pricingCtx

        self.startDate = startDate
        self.finalDate = pricingCtx.finalDate

        if self._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.day:
            self.interestPeriod = relativedelta(days=self._params.length.multiplier)
        elif self._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.month:
            self.interestPeriod = relativedelta(months=self._params.length.multiplier)
        elif self._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.year:
            self.interestPeriod = relativedelta(years=self._params.length.multiplier)

    def getKeyPoints(self):
        keyPoints = [self.KeyPoint(self.startDate, Decimal(1))]
        ctx = self.Context(self)

        while ctx.timePoint < self.finalDate:
            interest = ctx.interest()
            growth = Decimal(0)

            if interest.fixed:
                growth += ctx.fixedGrowth()
            if interest.derived:
                derivedGrowth = ctx.derivedGrowth()
                if derivedGrowth is None:
                    return []

                growth += derivedGrowth

            multiplier = keyPoints[-1].multiplier * (Decimal(1) + growth)
            keyPoints.append(self.KeyPoint(ctx.nextTimePoint, multiplier));
            ctx.advance()

        return keyPoints
