from datetime import datetime, timedelta


def _yearsBetween(lhs, rhs):
    yearDiff = rhs.year - lhs.year

    adjustedLhs = lhs.replace(year = rhs.year)
    if adjustedLhs > rhs:
        yearDiff -= 1

    return yearDiff


class Pricing(object):
    def __init__(self, pricingDef):
        super(Pricing, self).__init__()
        self._def = pricingDef

    def priceAsset(self, operations, finalDate = datetime.now()):
        value = 0

        for operation in operations:
            if operation['type'] == 'BUY':
                value += self.priceOperation(operation['date'], operation['price'], finalDate)
            elif operation['type'] == 'SELL':
                raise NotImplementedError("Did not implement SELL operation")

        return value

    def priceOperation(self, initDate, initValue, finalDate = datetime.now()):
        value = initValue

        if self._def['length']['periodName'] != 'year':
            raise NotImplementedError("Periods other than year are not implemented")

        passedPeriods = _yearsBetween(initDate, finalDate)
        if passedPeriods > 0:
            raise NotImplementedError("Did not implement calculating passed periods")

        interestDef = self._def['interest'][0]
        if 'derived' in interestDef:
            raise NotImplementedError("Did not implement calculating derived pricing")

        if 'fixed' in interestDef:
            percentage = interestDef['fixed']
            daysInLastPeriod = (finalDate - initDate).days
            value *= (1 + percentage * (daysInLastPeriod / 365))

        return value
