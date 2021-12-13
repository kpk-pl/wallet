from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass


class ParametrizedQuoting:
    SupportedLengthSpecs = ['day', 'month', 'year']


    class SpecError(RuntimeError):
        def __init__(self, err):
            super(SpecError, self).__init__("ParametrizedQuoting error: " + err)


    @staticmethod
    def _mustGet(desc, *keys):
        for key in keys:
            if key not in desc:
                raise ParametrizedQuoting.SpecError(f"No {key} specification")
            desc = desc[key]
        return desc


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
            return self._quoting._interestDesc[self.interestIdx]

        def advance(self):
            self.timePoint = self.nextTimePoint
            self.nextTimePoint += self._quoting.interestPeriod
            self.interestIdx = min(self.interestIdx + 1, len(self._quoting._interestDesc) - 1)

        def fixedGrowth(self):
            percentage = ParametrizedQuoting._mustGet(self.interest(), 'fixed', 'percentage')
            if not self.isPartial():
                return percentage

            return percentage * (self._quoting.finalDate - self.timePoint).days / (self.nextTimePoint - self.timePoint).days

        def derivedGrowth(self):
            quoteId = ParametrizedQuoting._mustGet(self.interest(), 'derived', 'quoteId')
            sample = ParametrizedQuoting._mustGet(self.interest(), 'derived', 'sample')
            interval = ParametrizedQuoting._mustGet(sample, 'interval')
            intervalOffset = sample['intervalOffset'] if 'intervalOffset' in sample else 0
            choose = ParametrizedQuoting._mustGet(sample, 'choose')
            clampBelow = sample['clampBelow'] if 'clampBelow' in sample else None


    def __init__(self, desc, startDate, finalDate = None):
        self.startDate = startDate
        self.finalDate = finalDate if finalDate != None else datetime.now();

        self._interestDesc = self._mustGet(desc, 'interest')
        if len(self._interestDesc) == 0:
            raise self.SpecError("Incorrect interest specification")

        if self._mustGet(desc, 'profitDistribution') != 'accumulating':
            raise NotImplementedError("Not implemented profitDistribution other than accumulating")

        self._initPeriods(desc)

    def _initPeriods(self, desc):
        self._length = self._mustGet(desc, 'length', 'name')
        if self._length not in self.SupportedLengthSpecs:
            raise self.SpecError("Incorrect length specification")
        self._lengthMultiplier = desc['length']['multiplier'] if 'multiplier' in desc['length'] else 1

        if self._length == 'day':
            self.interestPeriod = relativedelta(days=self._lengthMultiplier)
        elif self._length == 'month':
            self.interestPeriod = relativedelta(months=self._lengthMultiplier)
        elif self._length == 'year':
            self.interestPeriod = relativedelta(years=self._lengthMultiplier)

    def getKeyPoints(self):
        keyPoints = [self.KeyPoint(self.startDate, 1.0)]
        ctx = self.Context(self)

        while ctx.timePoint < self.finalDate:
            interest = ctx.interest()
            growth = 0.0

            if 'fixed' in interest:
                growth += ctx.fixedGrowth()
            if 'derived' in interest:
                growth += ctx.derivedGrowth()
                raise NotImplementedError("Did not implement calculating passed periods with derived pricing")

            keyPoints.append(self.KeyPoint(ctx.nextTimePoint, keyPoints[-1].multiplier * (1.0 + growth)));
            ctx.advance()

        return keyPoints
