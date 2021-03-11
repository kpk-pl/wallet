import math


def _valueOr(dictionary, key, default):
    return dictionary[key] if key in dictionary else default

def _operationNetValue(operation):
    return operation['price'] * _valueOr(operation, 'currencyConversion', 1.0)

class Analyzer(object):
    def __init__(self, assetData):
        super(Analyzer, self).__init__()
        self.data = assetData

        self._realisedGains = []
        self._calculateRolling()
        self._calculateSums()

    def f(self, name):
        return self.data[name] if name in self.data else None

    def investmentStartEnd(self):
        self.data['_investmentStart'] = self.data['operations'][0]['date']
        self.data['_investmentEnd'] = self.data['operations'][-1]['date'] if self.data['finalQuantity'] != 0 else None

    def addCurrentQuoteInfo(self, currencies):
        if _valueOr(self.data, 'lastQuote', None) is not None:
            self.data['_netValue'] = self.data['finalQuantity'] * self.data['lastQuote']['quote']
        else:
            self.data['_netValue'] = self.data['_stillInvestedValue']

        if self.data['currency'] != 'PLN':
            currencyConv = currencies[self.data['currency']]['quote']
            self.data['_netValue'] *= currencyConv

    def _findQuote(assetQuotes, timepoint):
        return None

    def _findValueFromQuotes(self, timepoint, currencyQuotes):
        value = Analyzer._findQuote(self.data['quoteHistory'], timepoint)
        if not value:
            self.data['_periodStats']['errors'].append({
                'type': 'asset',
                'id': self.data['_id'],
                'timestamp': timepoint
            })
            return None

        if self.data['currency'] != 'PLN':
            conversion = Analyzer._findQuote(currencyQuotes[self.data['currency']], timepoint)
            if not conversion:
                self.data['_periodsStats']['errors'].append({
                    'type': 'currency',
                    'id': currencyQuotes[self.data['currency']]['_id'],
                    'timestamp': timestamp
                })
                return None
            value *= conversion

        return value

    def addPeriodInfo(self, periodFrom, periodTo, currencyQuotes):
        fromOperationId = -1
        while fromOperationId < len(self.data['operations'])-1:
            if self.data['operations'][fromOperationId + 1]['date'] > periodFrom:
                break
            fromOperationId += 1

        self.data['_periodStats'] = {
            'firstOperation': fromOperationId + 1,
            'errors': []
        }

        if fromOperationId < 0:  # asset has been initialized in the checked period, so it is a new asset
            self.data['_periodStats']['initialQuantity'] = 0
            self.data['_periodStats']['initialNetValue'] = 0
        else:  # asset existed before the checked period
            self.data['_periodStats']['initialQuantity'] = self.data['operations'][fromOperationId]['finalQuantity']
            self.data['_periodStats']['initialNetValue'] = self._findValueFromQuotes(periodFrom, currencyQuotes)

        self.data['_periodStats']['finalQuantity'] = self.data['operations'][-1]['finalQuantity']
        if self.data['_periodStats']['finalQuantity'] == 0:
            self.data['_periodStats']['finalNetValue'] = 0
        else:
            self.data['_periodStats']['finalNetValue'] = self._findValueFromQuotes(periodTo, currencyQuotes)

        self.data['_periodStats']['profits'] = {
            'netValue': 0,
            'provisions': 0
        }

        for operation in self.data['operations'][self.data['_periodStats']['firstOperation']:]:
            if 'profits' in operation['_stats']:
                self.data['_periodStats']['profits']['netValue'] += operation['_stats']['profits']['netValue']
                self.data['_periodStats']['profits']['provisions'] += operation['_stats']['profits']['provisions']

        from bson.json_util import dumps
        print(dumps(self.data, indent=2))

    def _calculateRolling(self):
        firstStillInvestedBuyId = 0
        for operationId in range(len(self.data['operations'])):
            operation = self.data['operations'][operationId]
            operation['_stats'] = {}
            if operation['type'] == 'BUY':
                operation['_stats']['stillInvestedQuantity'] = operation['quantity']
            elif operation['type'] == 'SELL':
                operation['_stats']['profits'] = {
                    'netValue': _operationNetValue(operation),
                    'provisions': _valueOr(operation, 'provision', 0.0)
                }

                firstStillInvestedBuyId = self._processRollingSell(operationId, firstStillInvestedBuyId)

    def _processRollingSell(self, sellOperationId, firstStillInvestedBuyId = 0):
        operation = self.data['operations'][sellOperationId]
        remainingQuantity = operation['quantity']

        for investedBuyId in range(firstStillInvestedBuyId, sellOperationId):
            investedBuyOperation = self.data['operations'][investedBuyId]
            if investedBuyOperation['type'] != 'BUY':
                firstStillInvestedBuyId += 1
                continue

            sellingQuantity = min(remainingQuantity, investedBuyOperation['_stats']['stillInvestedQuantity'])
            remainingQuantity -= sellingQuantity
            investedBuyOperation['_stats']['stillInvestedQuantity'] -= sellingQuantity
            if investedBuyOperation['_stats']['stillInvestedQuantity'] == 0:
                firstStillInvestedBuyId += 1

            buyPartial = sellingQuantity / investedBuyOperation['quantity']
            operation['_stats']['profits']['netValue'] -= _operationNetValue(investedBuyOperation) * buyPartial
            operation['_stats']['profits']['provisions'] += _valueOr(investedBuyOperation, 'provision', 0.0) * buyPartial

            if math.isclose(remainingQuantity, 0, abs_tol=1e-12):
                return firstStillInvestedBuyId

        raise RuntimeError("Not enough bought quantity to sell")

    def _calculateSums(self):
        self.data['_stillInvestedValue'] = 0.0
        self.data['_totalProfits'] = {
            'netValue': 0.0,
            'provisions': 0.0
        }

        for operation in self.data['operations']:
            quantity = _valueOr(operation['_stats'], 'stillInvestedQuantity', 0)
            if not math.isclose(quantity, 0, abs_tol=1e-12):
                self.data['_stillInvestedValue'] += operation['price'] * (quantity / operation['quantity']) * _valueOr(operation, 'currencyConversion', 1.0)

            profits = _valueOr(operation['_stats'], 'profits', None)
            if profits is not None:
                self.data['_totalProfits']['netValue'] += profits['netValue']
                self.data['_totalProfits']['provisions'] += profits['provisions']
