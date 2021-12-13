from datetime import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass


class ParametrizedQuoting:
    SupportedLengthSpecs = ['day', 'month', 'year']

    class SpecError(RuntimeError):
        def __init__(self, err):
            super(SpecError, self).__init__("ParametrizedQuoting error: " + err)


    @dataclass
    class KeyPoint:
        timestamp: datetime
        multiplier: float


    def __init__(self, desc, startDate, finalDate = None):
        self.startDate = startDate
        self.finalDate = finalDate if finalDate != None else datetime.now();

        if 'interest' not in desc:
            raise self.SpecError("No interest specification")
        if len(desc['interest']) == 0:
            raise self.SpecError("Incorrect interest specification")

        self._interestDesc = desc['interest']
        self._initPeriods(desc)

    def _initPeriods(self, desc):
        if 'length' not in desc:
            raise self.SpecError("No length specified")
        if 'name' not in desc['length'] or desc['length']['name'] not in self.SupportedLengthSpecs:
            raise self.SpecError("Incorrect length specification")

        self._length = desc['length']['name']
        self._lengthMultiplier = desc['length']['multiplier'] if 'multiplier' in desc['length'] else 1

        if self._length == 'day':
            self._interestPeriod = relativedelta(days=self._lengthMultiplier)
        elif self._length == 'month':
            self._interestPeriod = relativedelta(months=self._lengthMultiplier)
        elif self._length == 'year':
            self._interestPeriod = relativedelta(years=self._lengthMultiplier)

    def getKeyPoints(self):
        keyPoints = [self.KeyPoint(self.startDate, 1.0)]

        timePoint = self.startDate
        nextTimePoint = timePoint + self._interestPeriod
        interestIdx = 0

        while timePoint < self.finalDate:
            partialPeriod = (nextTimePoint > self.finalDate)
            interest = self._interestDesc[interestIdx]
            growth = 0.0

            if 'fixed' in interest:
                if not partialPeriod:
                    growth += interest['fixed']
                else:
                    growth += interest['fixed'] * (self.finalDate - timePoint).days / (nextTimePoint - timePoint).days
            if 'derived' in interest:
                raise NotImplementedError("Did not implement calculating passed periods with derived pricing")

            timePoint = nextTimePoint
            nextTimePoint += self._interestPeriod
            interestIdx = min(interestIdx + 1, len(self._interestDesc) - 1)

            keyPoints.append(self.KeyPoint(timePoint, keyPoints[-1].multiplier * (1.0 + growth)));

        return keyPoints
