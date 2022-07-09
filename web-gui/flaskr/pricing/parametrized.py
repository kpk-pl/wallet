from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from decimal import Decimal
from flaskr import model


class ParametrizedQuoting:
    @dataclass
    class KeyPoint:
        timestamp: datetime
        multiplier: Decimal = Decimal(1)


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

        def partialMultiplier(self):
            periodDays = Decimal((self.nextTimePoint - self.timePoint).days)
            daysInYear = Decimal("365") # does not account for leap years but is good enough

            if not self.isPartial():
                if self._quoting._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.year:
                    return Decimal(1)
                else:
                    return periodDays / daysInYear

            passedDays = Decimal((self._quoting.finalDate - self.timePoint).days)
            if self._quoting._params.length.name == model.assetPricing.AssetPricingParametrizedLengthName.year:
                return passedDays / periodDays
            else:
                return passedDays / daysInYear

        def fixedGrowth(self):
            if not self.interest().fixed:
                return None

            return self.interest().fixed.percentage * self.partialMultiplier()

        def derivedIntervalDelta(self):
            thisInterest = self.interest().derived
            assert thisInterest is not None

            if thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.year:
                return relativedelta(years=1)
            elif thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.month:
                return relativedelta(months=1)
            elif thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.day:
                return relativedelta(days=1)
            else:
                return None

        def derivedQuoteTimestamp(self):
            thisInterest = self.interest().derived
            assert thisInterest is not None

            quoteTimestamp = datetime(self.timePoint.year, self.timePoint.month, self.timePoint.day)

            if thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.year:
                return quoteTimestamp.replace(day=1, month=1) + relativedelta(years=thisInterest.sample.intervalOffset)
            elif thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.month:
                return quoteTimestamp.replace(day=1) + relativedelta(months=thisInterest.sample.intervalOffset)
            elif thisInterest.sample.interval == model.assetPricing.AssetPricingParametrizedLengthName.day:
                return quoteTimestamp + relativedelta(days=thisInterest.sample.intervalOffset)
            else:
                return None

        def derivedPercentageForTimestamp(self, quoteTimestamp):
            thisInterest = self.interest().derived
            assert thisInterest is not None

            self._quoting._pricingCtx.loadQuotes(thisInterest.quoteId)
            derivedIntervalDelta = self.derivedIntervalDelta()

            if thisInterest.sample.choose == model.assetPricing.AssetPricingParametrizedInterestItemDerivedSampleChoose.last:
                percentage, timestamp = self._quoting._pricingCtx.getPreviousById(thisInterest.quoteId,
                                                                                  quoteTimestamp + derivedIntervalDelta,
                                                                                  withTimestamp=True)
            elif thisInterest.sample.choose == model.assetPricing.AssetPricingParametrizedInterestItemDerivedSampleChoose.first:
                percentage, timestamp = self._quoting._pricingCtx.getNextById(thisInterest.quoteId,
                                                                              quoteTimestamp,
                                                                              withTimestamp=True)
            else:
                return None

            # If retrieved quote is objectively too old (or to new somehow)
            if timestamp < quoteTimestamp - derivedIntervalDelta or timestamp > quoteTimestamp + derivedIntervalDelta:
                return None

            percentage *= thisInterest.sample.multiplier
            if thisInterest.sample.clampBelow:
                percentage = max(thisInterest.sample.clampBelow, percentage)
            return percentage

        def derivedGrowth(self):
            if not self.interest().derived:
                return None

            thisInterest = self.interest().derived
            quoteTimestamp = self.derivedQuoteTimestamp()
            percentage = self.derivedPercentageForTimestamp(quoteTimestamp)
            if percentage is None:
                return None

            return percentage * self.partialMultiplier()


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

        self.finalDate = min(self.finalDate, self.startDate + self.interestPeriod * self._params.length.count)

    def getKeyPoints(self):
        keyPoints = [self.KeyPoint(self.startDate)]
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

            if self._params.profitDistribution == model.assetPricing.AssetPricingParametrizedProfitDistribution.accumulating:
                multiplier = keyPoints[-1].multiplier * (Decimal(1) + growth)
            elif self._params.profitDistribution == model.assetPricing.AssetPricingParametrizedProfitDistribution.distributing:
                multiplier = keyPoints[-1].multiplier + growth

            keyPoints.append(self.KeyPoint(
                min(ctx.nextTimePoint, self.finalDate),
                multiplier
            ));
            ctx.advance()

        return keyPoints
